#!/usr/bin/env python3
"""slack-mobile-preview — Galaxy S23+ viewport HTML mock + screenshot.

Design Ref: §2.1, §4.1 (Option C — Pragmatic Balance).
Plan SC: SC-MP-1 (screenshot 100%), SC-MP-3 (<=10s), SC-MP-5 (main.py isolation).

Isolated tool — does NOT import main.py / news.py / config.py.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPTS_DIR / "templates"
OUTPUT_DIR = SCRIPTS_DIR / "output"

# Galaxy S23+ viewport (Plan FR-04, OQ-4 resolved — user device).
GALAXY_S23_PLUS_VIEWPORT = {
    "width": 384,
    "height": 854,
}
GALAXY_S23_PLUS_DPR = 3
GALAXY_S23_PLUS_UA = (
    "Mozilla/5.0 (Linux; Android 14; SM-S916N) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)

# Sentinel uses NUL bytes (\x00) — guaranteed absent from Slack text messages.
# Design Ref §4.1 used "___CODE_BLOCK_N___" but that risks collision with user text.
# NUL-based sentinel is safer (impossible to appear in legit Slack mrkdwn).
_SENTINEL_CB_PREFIX = "\x00\x01CB"
_SENTINEL_CB_SUFFIX = "\x01\x00"
_SENTINEL_IC_PREFIX = "\x00\x01IC"
_SENTINEL_IC_SUFFIX = "\x01\x00"


# ---------------------------------------------------------------------------
# Slack mrkdwn -> HTML  (Plan FR-02, Design §4.1)
# ---------------------------------------------------------------------------

def slack_mrkdwn_to_html(text: str) -> str:
    """Convert Slack mrkdwn core syntax to HTML.

    Supported:
      ```code block```       ->  <pre class="code-block">...</pre>
      `inline code`          ->  <code class="inline-code">...</code>
      *bold*                 ->  <strong>...</strong>
      newline \\n            ->  <br>
      HTML specials escaped  ->  &lt; &gt; &amp; (XSS prevention)

    Order:
      1. extract code blocks (replace with NUL-sentinel)
      2. extract inline code (replace with NUL-sentinel)
      3. HTML-escape the remainder
      4. *bold* -> <strong>
      5. \\n -> <br>
      6. restore sentinels with escaped content
    """
    # 1. ```...``` code block (multiline, non-greedy).
    code_blocks: list[str] = []

    def _extract_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"{_SENTINEL_CB_PREFIX}{len(code_blocks) - 1}{_SENTINEL_CB_SUFFIX}"

    text = re.sub(r"```\n?(.*?)\n?```", _extract_code_block, text, flags=re.DOTALL)

    # 2. `...` inline code.
    inline_codes: list[str] = []

    def _extract_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"{_SENTINEL_IC_PREFIX}{len(inline_codes) - 1}{_SENTINEL_IC_SUFFIX}"

    text = re.sub(r"`([^`\n]+)`", _extract_inline_code, text)

    # 3. HTML escape the remainder.
    text = html.escape(text)

    # 4. *bold* (Slack: single asterisk, no newline inside).
    text = re.sub(r"\*([^*\n]+)\*", r"<strong>\1</strong>", text)

    # 5. newline -> <br>.
    # NOTE: do NOT append "\n" after <br>. CSS `white-space: pre-wrap` on the
    # message container treats the literal \n as another line break, so
    # "<br>\n" doubles the gap and turns every single newline into a visual
    # blank-line. Slack mobile preserves single \n as a tight break with no
    # extra spacing (line-height alone), only \n\n produces a blank line
    # (= "<br><br>" here). Calibrated against준's Galaxy S23+ screenshot.
    text = text.replace("\n", "<br>")

    # 6. restore sentinels (escape content first).
    # html.escape() preserves NUL bytes, so sentinels still match.
    for i, code in enumerate(code_blocks):
        escaped = html.escape(code)
        text = text.replace(
            f"{_SENTINEL_CB_PREFIX}{i}{_SENTINEL_CB_SUFFIX}",
            f'<pre class="code-block">{escaped}</pre>',
        )
    for i, code in enumerate(inline_codes):
        escaped = html.escape(code)
        text = text.replace(
            f"{_SENTINEL_IC_PREFIX}{i}{_SENTINEL_IC_SUFFIX}",
            f'<code class="inline-code">{escaped}</code>',
        )

    return text


# ---------------------------------------------------------------------------
# Input sources (Plan FR-06, Design §4.1)
# ---------------------------------------------------------------------------

FIXTURE_MESSAGE = """\
📅 2026-05-11 KST 06:00
직전 거래일: 2026-05-08
📊 상승 8 / 하락 0 / VIX 17.19 (안정)

[신호]
```
🔥 거래량

🎯 갭

🆙 신고가

📊 시간외

⚡ VIX 급등

★  사상최고
```

[지수]
```
나스닥   26,247 +1.71% ★ 🆙

S&P 500   7,399 +0.84% ★ 🆙

다우     49,609 +0.02%
```

[오늘 단타 후보]
• 마이크론 MU 🎯+4.6% 🆙신고 📊+1.4%
  📰 +0.48 "AI 랠리에 마이크론 메모리 수요 급증" (Reuters)
"""


_GH_LINE_PREFIX_RE = re.compile(r"^[^\t]*\t[^\t]*\t[0-9T:.\-]*Z (.*)$")


def fetch_message_from_actions_log(run_id: str) -> str:
    """Extract MSG-DUMP block from GitHub Actions log via gh CLI.

    Design Ref §4.1: requires gh CLI; raises CalledProcessError on missing tool
    or non-zero exit; raises RuntimeError if MSG-DUMP markers absent.

    gh logs prepend each line with "<job>\\t<step>\\t<timestamp>Z " — the
    BEGIN/END markers therefore appear *inside* prefixed lines, not on their
    own. So we locate the marker lines first, slice the body, then strip
    prefixes line-by-line.
    """
    result = subprocess.run(
        ["gh", "run", "view", run_id, "--log"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.splitlines()
    begin_idx = next(
        (i for i, ln in enumerate(lines) if "===MSG-DUMP-BEGIN===" in ln),
        None,
    )
    end_idx = next(
        (i for i, ln in enumerate(lines) if "===MSG-DUMP-END===" in ln),
        None,
    )
    if begin_idx is None or end_idx is None or end_idx <= begin_idx:
        raise RuntimeError(f"MSG-DUMP not found in Actions log run-id={run_id}")

    body_lines = lines[begin_idx + 1 : end_idx]
    cleaned: list[str] = []
    for ln in body_lines:
        m = _GH_LINE_PREFIX_RE.match(ln)
        cleaned.append(m.group(1) if m else ln)
    return "\n".join(cleaned)


def resolve_message(source: str, run_id: str | None) -> tuple[str, str]:
    """Dispatch by source -> (text, label)."""
    if source == "fixture":
        return (FIXTURE_MESSAGE, "fixture")
    if source == "stdin":
        return (sys.stdin.read(), "stdin")
    if source == "actions-log":
        if not run_id:
            raise SystemExit("--source actions-log requires --run-id")
        return (fetch_message_from_actions_log(run_id), f"actions-{run_id}")
    raise SystemExit(f"unknown source: {source}")


# ---------------------------------------------------------------------------
# Render (Plan FR-03/04/05, Design §4.1)
# ---------------------------------------------------------------------------

def render_html(message_text: str) -> str:
    """Inject mrkdwn->HTML output into Jinja2 template."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=False,  # we escape manually in slack_mrkdwn_to_html
    )
    template = env.get_template("slack_mobile.html.j2")
    content = slack_mrkdwn_to_html(message_text)
    return template.render(content=content, timestamp=datetime.now().isoformat())


def screenshot_mobile(html_content: str, output_path: Path) -> None:
    """Render HTML in Galaxy S23+ viewport and save full-page PNG."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport=GALAXY_S23_PLUS_VIEWPORT,
                device_scale_factor=GALAXY_S23_PLUS_DPR,
                is_mobile=True,
                user_agent=GALAXY_S23_PLUS_UA,
            )
            page = context.new_page()
            page.set_content(html_content, wait_until="networkidle")
            page.screenshot(path=str(output_path), full_page=True)
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# CLI entry (Plan FR-01/06)
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Slack mobile preview (Galaxy S23+ simulation)"
    )
    parser.add_argument(
        "--source",
        choices=["fixture", "stdin", "actions-log"],
        default="fixture",
    )
    parser.add_argument("--run-id", help="Actions run-id (when --source actions-log)")
    parser.add_argument(
        "--output",
        help="Override output path (default: scripts/output/preview-*.png)",
    )
    args = parser.parse_args()

    message, label = resolve_message(args.source, args.run_id)
    html_content = render_html(message)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = OUTPUT_DIR / f"preview-{label}-{ts}.png"

    print(f"[PREVIEW] rendering {len(message)} chars -> {output_path}")
    screenshot_mobile(html_content, output_path)
    print(f"[OK] saved: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
