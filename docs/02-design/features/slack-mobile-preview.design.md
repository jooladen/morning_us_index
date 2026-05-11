---
name: slack-mobile-preview
type: design
version: 0.1.3
status: approved
phase: design
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
approved_at: 2026-05-11
approved_by: jooladen (Checkpoint 3 — Architecture Selection)
plan: docs/01-plan/features/slack-mobile-preview.plan.md
architecture: option-c-pragmatic-jinja2-template
target_device: Galaxy S23+ (384×854, DPR=3)
---

# Design — slack-mobile-preview (Ally 시각 검증 도구)

> **Summary**: `scripts/preview_mobile.py` 단일 entry + `scripts/templates/slack_mobile.html.j2` Jinja2 외부 템플릿. Playwright headless로 Galaxy S23+ 모바일 viewport 렌더 → PNG 저장. Ally가 멀티모달로 이미지 직접 분석. 메인 프로그램(main.py) 의존성 0.
>
> **Project**: morning-us-index (도구 사이클)
> **Version**: slack-mobile-preview 0.1.0
> **Author**: jooladen
> **Date**: 2026-05-11
> **Status**: Draft
> **Planning Doc**: [slack-mobile-preview.plan.md](../../01-plan/features/slack-mobile-preview.plan.md)

---

## Context Anchor

> Plan 문서 §Context Anchor 그대로 복사.

| 키 | 값 |
|---|---|
| **WHY** | v5~v10 누적 페인포인트 (스크린샷 5회 요구) 해소 + Ally 텍스트 추정 한계 극복 |
| **WHO** | 준 (1인 운영자, Galaxy S23+) |
| **RISK** | Playwright 50MB 의존성 / 슬랙 모바일 100% 재현 불가 (90-95% 시뮬) / Jinja2 추가 |
| **SUCCESS** | 향후 사이클에서 사용자 스크린샷 요청 0회 / 자동 줄바꿈 정확도 ≥90% (Galaxy 기준) |
| **SCOPE** | 슬랙 + Galaxy S23+. 카카오톡/iPhone은 Phase 2 |

---

## 1. Overview

### 1.1 Design Goals

- preview_mobile.py 실행 시 fixture/stdin/Actions log 메시지를 Galaxy S23+ viewport(384×854)에서 렌더 → PNG 저장
- Ally가 이미지 파일 Read로 직접 분석 (멀티모달)
- 메인 프로그램(main.py + tests/) 의존성 0 — scripts/ 격리
- 향후 메신저(카카오톡 등) 확장은 templates/ 디렉토리에 새 .j2 파일만 추가

### 1.2 Design Principles

- **Isolation** — `scripts/` 외 프로젝트 파일 변경 0
- **Template separation** — HTML 구조는 Jinja2 템플릿, 데이터 변환은 Python
- **Fail-fast** — Playwright 실패 시 명확한 에러 메시지 (chromium 미설치 등)
- **Galaxy first** — iOS 시뮬레이션은 Phase 2

### 1.3 Plan OQ 해소

| Open Q (Plan §11) | Design 결정 | 근거 |
|---|---|---|
| **OQ-1** Playwright vs Puppeteer vs Selenium | **Playwright (Python)** | 모바일 viewport 1급 시민, async/sync 둘 다, chromium 자동 다운로드 |
| **OQ-2** Jinja2 vs f-string 템플릿 | **Jinja2** | 향후 메신저 확장 시 템플릿만 추가, 로직과 HTML 분리 깔끔 |
| **OQ-3** 출력 파일명 규칙 | **`preview-{label}-{YYYYMMDD-HHMMSS}.png`** | label="fixture"/"stdin"/"actions-{run-id}" |
| **OQ-4** viewport 표준 | **Galaxy S23+ 384×854 DPR=3** (Plan 이미 결정됨) | 사용자 디바이스 |
| **OQ-5** 이모지 변환 사전 | **운영 중 발견된 케이스만 매핑 (Do 단계)** | YAGNI — 모든 슬랙 이모지 변환 사전 X |

---

## 2. Architecture Options

### 2.0 Architecture Comparison

3 옵션 평가. 사용자 선택: **Option C — Pragmatic Balance**.

| 기준 | A: Minimal | B: Clean | C: Pragmatic ✅ |
|---|:-:|:-:|:-:|
| **접근** | 단일 파일 인라인 HTML | 패키지 + 계층 분리 | 단일 entry + Jinja2 외부 템플릿 |
| **신규 파일** | 2 | 6+ | **3** |
| **신규 의존성** | 1 (playwright) | 2 (playwright + jinja2) | **2** (playwright + jinja2) |
| **복잡도** | Low | High | **Medium** |
| **확장성 (다른 메신저)** | Low (코드 수정) | High (계층별 추가) | **High (템플릿만 추가)** |
| **작업 시간** | 3h | 1d | **반나절** |
| **YAGNI** | OK | 과잉 (1인 도구) | **균형** |

**Selected**: **Option C — Pragmatic Balance**
**Rationale**: 1인 운영 도구 + 향후 다른 메신저로 확장 가능성 = 단일 entry 파일로 단순하게 + 템플릿만 분리로 확장 여지. Option B는 1 사이클 도구에 4 파일 분리 = YAGNI 위반.

### 2.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  scripts/preview_mobile.py (entry, ~200 lines)                   │
│                                                                  │
│   parse_args                                                     │
│        ↓                                                         │
│   ┌────────────────────────────────────────────────────┐         │
│   │  source 결정:                                       │         │
│   │  --source fixture       → fixture_message()        │         │
│   │  --source stdin         → sys.stdin.read()         │         │
│   │  --source actions-log <id> → gh CLI fetch          │         │
│   └────────────────┬───────────────────────────────────┘         │
│                    ↓                                             │
│   ┌────────────────────────────────────────────────────┐         │
│   │  slack_mrkdwn_to_html(text)                        │         │
│   │    - ```code block``` → <pre>                      │         │
│   │    - `inline code` → <code>                        │         │
│   │    - *bold* → <strong>                             │         │
│   │    - 줄바꿈 → <br>                                 │         │
│   │    - HTML escape (XSS 회피)                         │         │
│   └────────────────┬───────────────────────────────────┘         │
│                    ↓ html_content (str)                          │
│   ┌────────────────────────────────────────────────────┐         │
│   │  Jinja2.render(slack_mobile.html.j2,               │         │
│   │                content=html_content, timestamp=…)  │         │
│   └────────────────┬───────────────────────────────────┘         │
│                    ↓ rendered_html (str)                         │
│   ┌────────────────────────────────────────────────────┐         │
│   │  Playwright sync_api:                              │         │
│   │   p.chromium.launch(headless=True)                 │         │
│   │   context = browser.new_context(                   │         │
│   │     viewport={"width": 384, "height": 854},        │         │
│   │     device_scale_factor=3,                         │         │
│   │     is_mobile=True,                                │         │
│   │     user_agent="...Android Chrome..."              │         │
│   │   )                                                │         │
│   │   page.set_content(rendered_html)                  │         │
│   │   page.screenshot(path=output_path, full_page=True)│         │
│   └────────────────┬───────────────────────────────────┘         │
│                    ↓                                             │
│            scripts/output/preview-*.png                          │
└──────────────────────────────────────────────────────────────────┘

       Ally가 Read 도구로 PNG 분석 (멀티모달)
       → 자동 줄바꿈 / 이모지 / 컬럼 정렬 / 라인 잘림 직접 확인
```

### 2.2 Data Flow

```
입력:
  fixture mode  → 내장 샘플 (FIXTURE_MESSAGE 상수)
  stdin mode    → echo "msg" | python preview_mobile.py --source stdin
  actions-log   → gh run view <id> --log | grep MSG-DUMP

       ↓ (text: str)

mrkdwn → HTML 변환:
  ```                  →  <pre class="code-block">
  code block content       code block content
  ```                      </pre>
  *bold*               →  <strong>bold</strong>
  `code`               →  <code>code</code>
  \n                   →  <br>

       ↓ (html_content: str)

Jinja2 템플릿 적용:
  <!DOCTYPE html>
  <html>
   <head>
    <style>
      body { font: 16px 'Noto Sans KR', 'Roboto', sans-serif; }
      .slack-msg { padding: 16px; background: #fff; }
      pre.code-block { font: 14px 'Courier New', monospace; … }
      .emoji { font-family: 'Noto Color Emoji'; }
    </style>
   </head>
   <body><div class="slack-msg">{{ content|safe }}</div></body>
  </html>

       ↓ (rendered_html: str)

Playwright Galaxy S23+ 시뮬:
  viewport: 384 x 854
  DPR: 3
  isMobile: true
  user_agent: Mozilla/5.0 (Linux; Android 14; SM-S916N) ...

       ↓

scripts/output/preview-{label}-{ts}.png (PNG, full_page=True)
```

### 2.3 Dependencies

| Component | Depends On | Purpose |
|---|---|---|
| `preview_mobile.py` | `playwright`, `jinja2`, stdlib | entry + 변환 + 렌더 |
| `slack_mobile.html.j2` | Jinja2 syntax | HTML 구조 + 슬랙 스타일 CSS |
| `test_preview_mobile.py` | `pytest`, `preview_mobile` | 단위 테스트 |

**main.py 영향**: **0** — preview_mobile.py는 main.py를 import하지 않음. main.py도 preview_mobile.py를 import하지 않음. 양방향 격리.

---

## 3. Data Model

### 3.1 입력 메시지 형식

Slack mrkdwn 텍스트 (main.py의 `build_v15_message()` 반환과 동일 형식):

```
📅 2026-05-11 KST 06:00
직전 거래일: 2026-05-10

[지수]
```
나스닥   26,247 +1.71% ★ 🆙
...
```

[오늘 단타 후보]
• 마이크론 MU 🎯+4.6% 🆙신고
  📰 +0.48 "..." (Reuters)
```

### 3.2 출력 파일

```
scripts/output/preview-{label}-{YYYYMMDD-HHMMSS}.png
```

예시:
- `preview-fixture-20260511-074500.png`
- `preview-stdin-20260511-074800.png`
- `preview-actions-25643273607-20260511-074900.png`

---

## 4. Module Design

### 4.1 `scripts/preview_mobile.py` (신규, ~200 lines)

```python
#!/usr/bin/env python3
"""slack-mobile-preview — Galaxy S23+ viewport HTML mock + 스크린샷.

Design Ref: §2.1, §4.2 (Option C — Pragmatic Balance).
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

# Galaxy S23+ viewport (FR-04)
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


# ─────────────────────────────────────────────────────────────
# Slack mrkdwn → HTML (FR-02)
# ─────────────────────────────────────────────────────────────

def slack_mrkdwn_to_html(text: str) -> str:
    """Slack mrkdwn 핵심 문법을 HTML로 변환.

    지원:
      ```code block```       →  <pre class="code-block">…</pre>
      `inline code`          →  <code class="inline-code">…</code>
      *bold*                 →  <strong>…</strong>
      줄바꿈 \n              →  <br>
      HTML 특수문자 escape   →  &lt; &gt; &amp; (XSS 방지)

    Order matters:
      1. code block 먼저 추출 (NUL-byte sentinel)
      2. inline code 추출 (NUL-byte sentinel)
      3. HTML escape
      4. *bold* → <strong>
      5. \n → <br>
      6. sentinel 복원

    v0.1.2 — Architecture Coaching: sentinel을 NUL-byte 기반(\x00\x01CB...)으로 사용.
    이전 v0.1.1까지 ___CODE_BLOCK_N___ 텍스트 sentinel은 사용자 메시지에 우연히
    같은 문자열이 등장하면 충돌 가능 (예: 코드 리뷰 댓글). NUL byte는 슬랙 mrkdwn
    메시지에 절대 등장하지 않으므로 충돌 0. test_mrkdwn_sentinel_collision_safety
    회귀 가드 포함.
    """
    # 1. ```...``` code block 추출 (multiline). sentinel = "\x00\x01CB{idx}\x01\x00"
    code_blocks: list[str] = []
    def _extract_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00\x01CB{len(code_blocks)-1}\x01\x00"
    text = re.sub(r"```\n?(.*?)\n?```", _extract_code_block, text, flags=re.DOTALL)

    # 2. `...` inline code 추출. sentinel = "\x00\x01IC{idx}\x01\x00"
    inline_codes: list[str] = []
    def _extract_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00\x01IC{len(inline_codes)-1}\x01\x00"
    text = re.sub(r"`([^`\n]+)`", _extract_inline_code, text)

    # 3. HTML escape (html.escape는 NUL 보존 → sentinel 안전)
    text = html.escape(text)

    # 4. *bold* (Slack 스타일: 단어 경계 + asterisk)
    text = re.sub(r"\*([^*\n]+)\*", r"<strong>\1</strong>", text)

    # 5. \n → <br>
    # v0.1.3 — 사용자 폰 캘리브레이션: "<br>\n" 더블 카운트 버그 수정.
    # CSS `white-space: pre-wrap` 컨테이너 안에서 literal \n도 줄바꿈으로
    # 재처리되므로 "<br>\n"은 시각적 빈 줄 효과 → fixture의 단일 \n이 모두
    # 빈 줄로 보임. 슬랙 모바일 실측: 단일 \n은 좁은 줄바꿈,
    # \n\n만 빈 줄. 따라서 "<br>"만 출력.
    text = text.replace("\n", "<br>")

    # 6. sentinel 복원
    for i, code in enumerate(code_blocks):
        escaped = html.escape(code)
        text = text.replace(
            f"\x00\x01CB{i}\x01\x00",
            f'<pre class="code-block">{escaped}</pre>',
        )
    for i, code in enumerate(inline_codes):
        escaped = html.escape(code)
        text = text.replace(
            f"\x00\x01IC{i}\x01\x00",
            f'<code class="inline-code">{escaped}</code>',
        )

    return text


# ─────────────────────────────────────────────────────────────
# Input sources (FR-06)
# ─────────────────────────────────────────────────────────────

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
    """gh CLI로 Actions log에서 MSG-DUMP 추출.

    v0.1.2 — 버그 수정: line-based 슬라이싱으로 교체.
    이전 v0.1.1까지 regex `===MSG-DUMP-BEGIN===\\n(.*?)\\n===MSG-DUMP-END===`
    는 gh CLI 로그 포맷과 맞지 않음. gh는 모든 라인에 "<job>\\t<step>\\t<timestamp>Z "
    prefix를 붙이므로 BEGIN/END 마커가 *prefix 안에* 끼어 들어가
    multiline regex의 \\n 매칭이 실패한다. 결과: 정상 로그에서도 RuntimeError.
    → 마커가 포함된 라인 인덱스를 먼저 찾고 그 사이를 슬라이싱한 뒤
       라인별로 prefix를 제거하는 방식이 정확.
    """
    result = subprocess.run(
        ["gh", "run", "view", run_id, "--log"],
        capture_output=True, text=True, check=True,
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
    """input source 처리 → (text, label)."""
    if source == "fixture":
        return (FIXTURE_MESSAGE, "fixture")
    if source == "stdin":
        return (sys.stdin.read(), "stdin")
    if source == "actions-log":
        if not run_id:
            raise SystemExit("--source actions-log requires --run-id")
        return (fetch_message_from_actions_log(run_id), f"actions-{run_id}")
    raise SystemExit(f"unknown source: {source}")


# ─────────────────────────────────────────────────────────────
# Render (FR-03, FR-04, FR-05)
# ─────────────────────────────────────────────────────────────

def render_html(message_text: str) -> str:
    """Jinja2 템플릿에 변환된 HTML 주입."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=False,  # 우리가 직접 escape 함
    )
    template = env.get_template("slack_mobile.html.j2")
    content = slack_mrkdwn_to_html(message_text)
    return template.render(content=content, timestamp=datetime.now().isoformat())


def screenshot_mobile(html_content: str, output_path: Path) -> None:
    """Playwright Galaxy S23+ viewport로 HTML 렌더 + PNG 저장."""
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


# ─────────────────────────────────────────────────────────────
# CLI entry (FR-01, FR-06)
# ─────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Slack mobile preview (Galaxy S23+ simulation)"
    )
    parser.add_argument(
        "--source", choices=["fixture", "stdin", "actions-log"], default="fixture"
    )
    parser.add_argument("--run-id", help="Actions run-id (when --source actions-log)")
    parser.add_argument(
        "--output", help="Override output path (default: scripts/output/preview-*.png)"
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

    print(f"[PREVIEW] rendering {len(message)} chars → {output_path}")
    screenshot_mobile(html_content, output_path)
    print(f"[OK] saved: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 4.2 `scripts/templates/slack_mobile.html.j2` (신규)

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Slack Mobile Preview ({{ timestamp }})</title>
  <!-- Galaxy S23+ font stack — Samsung One UI/Noto Sans KR fallback -->
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&family=Noto+Color+Emoji&family=Roboto:wght@400;700&family=Roboto+Mono&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; }
    html, body {
      margin: 0; padding: 0;
      background: #f4f4f4;
      font-family: 'Noto Sans KR', 'Roboto', sans-serif;
      font-size: 15px;  /* 슬랙 Android 기본 약 15-16px */
      line-height: 1.45;
      color: #1d1c1d;
    }
    /* 이모지는 Noto Color Emoji fallback */
    body { font-family: 'Noto Sans KR', 'Roboto', 'Noto Color Emoji', sans-serif; }

    .slack-channel {
      background: #fff;
      padding: 12px 14px;
      min-height: 100vh;
    }
    .channel-header {
      font-size: 13px;
      color: #616061;
      border-bottom: 1px solid #e1e1e1;
      padding-bottom: 8px;
      margin-bottom: 12px;
    }
    .message {
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: anywhere;
    }
    pre.code-block {
      background: #f8f8f8;
      border: 1px solid #e1e1e1;
      border-radius: 4px;
      padding: 8px 10px;
      margin: 6px 0;
      font-family: 'Roboto Mono', 'Courier New', monospace;
      font-size: 13px;
      white-space: pre;
      overflow-x: auto;
    }
    code.inline-code {
      background: #f8f8f8;
      border: 1px solid #e1e1e1;
      border-radius: 3px;
      padding: 1px 4px;
      font-family: 'Roboto Mono', monospace;
      font-size: 13px;
    }
    strong { font-weight: 700; }
  </style>
</head>
<body>
  <div class="slack-channel">
    <div class="channel-header"># 미증시지수 ▾</div>
    <div class="message">{{ content|safe }}</div>
  </div>
</body>
</html>
```

### 4.3 `tests/test_preview_mobile.py` (신규, ~120 lines, 6+ 케이스)

```python
"""slack-mobile-preview 단위 테스트.

L1 단위:
  - mrkdwn → HTML 변환 (5 케이스)
  - render_html (Jinja2 통합 1 케이스)
  - actions-log 추출 (mocked 1 케이스)
  - screenshot_mobile은 통합 테스트 (마크 integration, slow)
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from preview_mobile import slack_mrkdwn_to_html, fetch_message_from_actions_log


def test_mrkdwn_code_block_to_pre():
    """L1-prev-1: ```code block``` → <pre class="code-block">"""
    html = slack_mrkdwn_to_html("```\nhello\n```")
    assert '<pre class="code-block">' in html
    assert "hello" in html
    assert "</pre>" in html


def test_mrkdwn_inline_code():
    """L1-prev-2: `inline` → <code class="inline-code">"""
    html = slack_mrkdwn_to_html("hello `code` world")
    assert '<code class="inline-code">code</code>' in html


def test_mrkdwn_bold():
    """L1-prev-3: *bold* → <strong>"""
    html = slack_mrkdwn_to_html("hello *bold* world")
    assert "<strong>bold</strong>" in html


def test_mrkdwn_html_escape():
    """L1-prev-4: HTML 특수문자 escape (XSS 방지)"""
    html = slack_mrkdwn_to_html("<script>alert('x')</script>")
    assert "&lt;script&gt;" in html
    assert "<script>" not in html  # 원본 그대로 등장 X


def test_mrkdwn_newline_to_br():
    """L1-prev-5: \n → <br>"""
    html = slack_mrkdwn_to_html("line1\nline2")
    assert "<br>" in html


def test_mrkdwn_preserves_code_block_content():
    """L1-prev-6: code block 안 특수문자는 escape 되지만 <pre>로 보존"""
    html = slack_mrkdwn_to_html("```\n<test>\n```")
    assert "&lt;test&gt;" in html
    assert '<pre class="code-block">' in html


def test_fetch_actions_log_extracts_dump(monkeypatch):
    """L1-prev-7: gh CLI mock → MSG-DUMP 추출 성공"""
    import subprocess

    fake_log = (
        "report\tRun report\t2026-05-11T00:00:00Z ===MSG-DUMP-BEGIN===\n"
        "report\tRun report\t2026-05-11T00:00:00Z line1\n"
        "report\tRun report\t2026-05-11T00:00:00Z line2\n"
        "report\tRun report\t2026-05-11T00:00:00Z ===MSG-DUMP-END===\n"
    )

    class _Result:
        stdout = fake_log

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _Result())
    msg = fetch_message_from_actions_log("12345")
    assert "line1" in msg
    assert "line2" in msg
    assert "Run report" not in msg  # prefix 제거됨
```

---

## 5. UI/UX Design

**N/A** — 백엔드 개발 도구. UI 없음. 출력은 PNG 파일.

---

## 6. Error Handling

| 단계 | 실패 종류 | 대응 |
|---|---|---|
| `playwright` import | 미설치 | 명확한 메시지: `pip install playwright && playwright install chromium` |
| `chromium` 미다운로드 | 첫 실행 | Playwright 자동 안내 또는 `RuntimeError` |
| `gh CLI` 미설치 (actions-log 모드) | gh 명령 실패 | `CalledProcessError` → 명확한 메시지 |
| MSG-DUMP 마커 없음 | run-id 잘못 또는 dump 코드 미배포 | `RuntimeError("MSG-DUMP not found")` |
| `templates/slack_mobile.html.j2` 누락 | 파일 삭제 | Jinja2 `TemplateNotFound` |
| `OUTPUT_DIR` 쓰기 권한 X | 디스크 풀 | `OSError` → 사용자 에러 |
| 메시지 길이 0 | 빈 입력 | 빈 PNG 생성 (정상 동작 — 디버깅용) |

---

## 7. Configuration & Secrets

**변경 0** — secrets 추가 없음. `SLACK_WEBHOOK_URL` 등 운영 secret과 무관.

새 환경변수 (선택):
- 없음 (CLI 인자로 모두 처리)

---

## 8. Test Plan (L1 단위 ~7 케이스)

### 8.1 Test Scope

| Type | Target | Tool | Phase |
|---|---|---|---|
| **L1: Unit** | mrkdwn → HTML 변환, actions-log fetch | pytest + unittest.mock | Do |
| **L1: Integration** | screenshot_mobile (실 Playwright + chromium) | pytest -m integration | Do (선택) |

### 8.2 `tests/test_preview_mobile.py` (9 케이스)

| # | 항목 | 통과 기준 |
|---|---|---|
| L1-prev-1 | code block → `<pre>` | `<pre class="code-block">` 등장 |
| L1-prev-2 | inline code → `<code>` | `<code class="inline-code">` 등장 |
| L1-prev-3 | *bold* → `<strong>` | `<strong>` 등장 |
| L1-prev-4 | HTML escape (XSS) | `<script>` 미등장, `&lt;script&gt;` 등장 |
| L1-prev-5 | 줄바꿈 → `<br>` | `<br>` 등장 |
| L1-prev-6 | code block 안 특수문자 escape | code block + escape 모두 등장 |
| L1-prev-7 | actions-log MSG-DUMP 추출 | 메시지 본문 추출, prefix 제거 |
| L1-prev-7b (v0.1.2) | 마커 없는 로그 → RuntimeError | `pytest.raises(RuntimeError, match="MSG-DUMP not found")` |
| L1-prev-8 (v0.1.2) | sentinel collision safety | 사용자 텍스트가 옛 ___CODE_BLOCK_0___ 같은 문자열을 포함해도 `<pre>` 변환 안 됨 |

**L1-prev-Smoke (integration)**: screenshot_mobile 실 호출 → 단위 테스트 대신 `/pdca do` smoke run으로 검증 (Design intent 유지, fast 단위 0.15s 보존).

### 8.3 main.py 회귀 검증

이번 사이클은 main.py 변경 0 → 회귀 자동 보장.

`pytest -m "not integration"` 전체 실행 시:
- 이전 110 케이스 + 신규 9 케이스 = **119 단위 케이스** (integration 6건 deselected)

---

## 9. Clean Architecture

이 도구는 메인 프로젝트와 격리된 단일 스크립트. 다층 구조 N/A.

### 9.1 격리 원칙

- `scripts/preview_mobile.py` → **main.py를 import 하지 않음**
- `main.py` → **scripts/를 import 하지 않음**
- 양방향 단절 → 도구 실패가 운영 영향 0

### 9.2 의존성 방향

```
scripts/preview_mobile.py
   ↓ depends on
playwright, jinja2 (외부)
templates/slack_mobile.html.j2 (자체)

(main.py, config.py 등 운영 코드와 무관)
```

---

## 10. Coding Convention Reference

### 10.1 명명

| 대상 | 규칙 | 예시 |
|---|---|---|
| 모듈 | snake_case.py | `preview_mobile.py` |
| 함수 | snake_case | `slack_mrkdwn_to_html`, `screenshot_mobile` |
| 상수 | UPPER_SNAKE_CASE | `GALAXY_S23_PLUS_VIEWPORT`, `FIXTURE_MESSAGE` |
| 내부 헬퍼 | `_` prefix | `_extract_code_block` |

### 10.2 Import 순서 (PEP 8)

```python
from __future__ import annotations

# stdlib
import argparse
import html
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# third-party
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
```

### 10.3 환경변수

**없음** (CLI 인자로 모두 처리)

---

## 11. Implementation Guide

### 11.1 File Structure

```
morning_us_index/
├── main.py                         (변경 없음)
├── news.py                         (변경 없음)
├── config.py                       (변경 없음)
├── requirements.txt                (변경 없음 — 별도 dev 의존성)
├── requirements-dev.txt            🆕 (선택, playwright + jinja2)
├── scripts/
│   ├── preview_fixture.py          (v6 기존)
│   ├── preview_mobile.py           🆕 (이번 사이클)
│   ├── templates/                  🆕
│   │   └── slack_mobile.html.j2    🆕
│   └── output/                     🆕 (gitignore, PNG 저장)
├── tests/
│   └── test_preview_mobile.py      🆕 (7 케이스)
└── .gitignore                      (수정 — scripts/output/ 추가)
```

### 11.2 Implementation Order (10 단계)

| # | 항목 | 산출물 | DoD |
|---|---|---|---|
| 1 | `requirements-dev.txt` 신규 (playwright + jinja2) | 신규 | `pip install -r requirements-dev.txt` 성공 |
| 2 | `playwright install chromium` 실행 | (1회) | chromium binary 캐시됨 (~50MB) |
| 3 | `scripts/preview_mobile.py` 신규 — slack_mrkdwn_to_html | 신규 | 단위 테스트 5개(L1-prev-1~5) 통과 |
| 4 | preview_mobile.py — resolve_message / fetch_actions_log | 채움 | L1-prev-7 mocked 통과 |
| 5 | preview_mobile.py — render_html / screenshot_mobile | 채움 | fixture 모드 실행 시 PNG 생성 |
| 6 | preview_mobile.py — main() argparse | 채움 | `--source fixture` 실행 OK |
| 7 | `scripts/templates/slack_mobile.html.j2` 신규 | 신규 | Jinja2 render 성공, HTML 정상 |
| 8 | `tests/test_preview_mobile.py` — 7 케이스 작성 | 신규 | 7 passed |
| 9 | `.gitignore` 갱신 (`scripts/output/*.png`) | 수정 | git status에 PNG 제외 |
| 10 | 실 사용 검증 — `python scripts/preview_mobile.py --source actions-log <run-id>` | 운영 | 실 Actions log → PNG 생성, Ally Read로 분석 가능 |

### 11.3 Session Guide

#### Module Map

| Module | Scope Key | Description | 11.2 # |
|---|---|---|---|
| **module-1-deps** | `module-1-deps` | requirements-dev.txt + playwright install | 1, 2 |
| **module-2-mrkdwn** | `module-2-mrkdwn` | slack_mrkdwn_to_html 변환 함수 | 3 |
| **module-3-sources** | `module-3-sources` | resolve_message + actions-log fetch | 4 |
| **module-4-render** | `module-4-render` | render_html + screenshot_mobile + main() | 5, 6 |
| **module-5-template** | `module-5-template` | slack_mobile.html.j2 + Galaxy S23+ CSS | 7 |
| **module-6-tests** | `module-6-tests` | test_preview_mobile.py 7 케이스 | 8 |
| **module-7-deploy** | `module-7-deploy` | gitignore + 실 사용 검증 | 9, 10 |

#### Recommended Session Plan

| 세션 | 범위 | DoD | 시간 |
|---|---|---|---|
| **S1 — Foundation** | module-1, 2, 5 | playwright/jinja2 설치 + mrkdwn 변환 + 템플릿 작성 | 1.5h |
| **S2 — Render + Test** | module-3, 4, 6 | actions-log fetch + Playwright 렌더 + 7 테스트 통과 | 2h |
| **S3 — Deploy** | module-7 | .gitignore + 실 Actions log fetch → PNG → Ally 분석 | 30분 |

또는 단일 세션:
```bash
/pdca do slack-mobile-preview
```

반나절 작업이라 단일 세션 권장.

---

## 12. Risks Update (Plan §8 보완)

| Plan ID | Design 단계 추가 대응 |
|---|---|
| **R-1** Playwright chromium 다운로드 실패 | install 1회 + 캐시. Actions에서는 CI step에 `playwright install chromium` 추가 (현재 사이클 외) |
| **R-2** HTML mock과 실 슬랙 렌더링 차이 | font-family: 'Noto Sans KR', 'Roboto', 'Noto Color Emoji' 정확 매칭. line-height 1.45. 첫 실행 후 사용자 폰 비교로 미세 조정 |
| **R-3** 이모지 변환 시뮬레이션 한계 | Phase 1: 시뮬레이션 안 함 (이모지 그대로 표시). Phase 2: 알려진 변환(예: 🆙 → "UP!" 박스) 사전 매핑 |
| **R-4** scripts/ 의존성 main.py에 누출 | preview_mobile.py가 main.py를 절대 import하지 않음. 단위 테스트에서 확인 |
| **R-5** 스크린샷 파일 누적 | .gitignore `scripts/output/*.png`. 또는 정기 cleanup script (Phase 2) |
| **R-6** gh CLI 의존 (actions-log 모드) | fixture 모드 fallback이 기본값. --source actions-log는 옵션 |
| **R-7 (신규)** Jinja2 autoescape vs 우리 직접 escape 충돌 | `autoescape=False` 명시 + slack_mrkdwn_to_html에서 직접 escape (placeholder 트릭으로 code block 보존) |

---

## 13. Out of Scope (Phase 2-MobilePreview+)

(Plan §9 그대로)

- Phase 2: 카카오톡 / 텔레그램 / 이메일 HTML 템플릿
- Phase 2: 이모지 변환 사전 (🆙 → "UP!")
- Phase 2: Actions artifact 자동 업로드
- Phase 3: Android Emulator + ADB screenshot (99% 정확도)
- Phase 3: A/B 시안 비교

---

## 14. Deployment

**프로덕션 영향 0** — 도구는 로컬/개발 사용. `.github/workflows/daily_report.yml` 변경 없음.

| 항목 | 변경 |
|---|---|
| `requirements.txt` (운영) | 0 |
| `main.py` / `news.py` / `config.py` | 0 |
| Workflow yaml | 0 |
| Secrets | 0 |
| 신규 `requirements-dev.txt` | + (playwright + jinja2) |
| 신규 `scripts/preview_mobile.py` + templates | + |
| `.gitignore` | scripts/output/*.png 추가 |

---

## 15. References

- Plan: `docs/01-plan/features/slack-mobile-preview.plan.md`
- 사용자 디바이스 메모리: `~/.claude/projects/.../memory/user_device.md`
- Playwright Python sync API: https://playwright.dev/python/docs/api/class-page#page-screenshot
- Jinja2 docs: https://jinja.palletsprojects.com/
- Slack mrkdwn 문법: https://api.slack.com/reference/surfaces/formatting
- Google Fonts (Noto Sans KR + Noto Color Emoji + Roboto Mono): https://fonts.google.com
- Galaxy S23+ 사양: 6.6" 2340×1080 FHD+, Android 14 One UI 6

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 0.1 | 2026-05-11 | Initial draft. Option C(Pragmatic) 선택. Plan OQ-1~OQ-5 5개 모두 해소. Galaxy S23+ 384×854 DPR=3 viewport. 7 신규 테스트. | jooladen (with Ally) |
| 0.1.1 | 2026-05-11 | Status: draft → approved (Checkpoint 3 통과, 변경 사항 없음 — 기존 v0.1.0 그대로 승격). | jooladen |
| 0.1.2 | 2026-05-11 | Check phase Match Rate 100% 달성 후 후행 동기화. (a) §4.1 slack_mrkdwn_to_html sentinel: ___CODE_BLOCK_N___ → NUL-byte (\\x00\\x01CB) — 사용자 텍스트 충돌 방지 (Architecture coaching). (b) §4.1 fetch_message_from_actions_log: regex → line-based slicing — gh log 포맷 multiline 매칭 버그 수정. (c) §8.2 테스트 7 → 9 (L1-prev-7b: missing markers, L1-prev-8: sentinel collision 추가). (d) §8.3 117 → 119 단위 케이스. | jooladen (with Ally + bkit:gap-detector) |
| 0.1.3 | 2026-05-11 | **첫 사용자 폰 캘리브레이션 (SC-MP-2 정량 측정)**. 준의 실 Galaxy S23+ 다크 모드 스크린샷 1:1 비교로 줄간격 버그 발견 + 수정. §4.1 slack_mrkdwn_to_html step 5: `text.replace("\\n", "<br>\\n")` → `text.replace("\\n", "<br>")`. 원인: CSS white-space pre-wrap 컨테이너에서 literal \\n이 추가 줄바꿈으로 재처리 → 모든 단일 \\n이 빈 줄처럼 보임. 수정 후 헤더 3줄 + 단타 후보 종목+뉴스 빽빽 1:1 일치 (2/2 핵심 항목 = 100%). 9 단위 테스트 회귀 0. | jooladen (with Ally, Galaxy S23+ 실측) |

---

**다음 단계**: `/pdca do slack-mobile-preview` (반나절 단일 세션 권장)
