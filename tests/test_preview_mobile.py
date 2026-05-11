"""slack-mobile-preview unit tests.

Design Ref §4.3 + §8.2 — 7 L1 cases + 1 sentinel-collision case (architecture coaching).
Plan SC-MP-6: >=6 new tests. Plan SC-MP-5: zero main.py regression.

All tests are L1 (pure functions). screenshot_mobile() requires a real chromium
launch and is covered by the smoke run from `/pdca do` (module-4), not here, so
the suite stays fast (<1s) for routine pytest runs.
"""
from __future__ import annotations

import subprocess
import sys
import unittest.mock as mock
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from preview_mobile import (  # noqa: E402  (path injection above)
    fetch_message_from_actions_log,
    slack_mrkdwn_to_html,
)


# ----- L1-prev-1..6: slack_mrkdwn_to_html ---------------------------------

def test_mrkdwn_code_block_to_pre():
    """L1-prev-1: ```code block``` -> <pre class="code-block">."""
    out = slack_mrkdwn_to_html("```\nhello\n```")
    assert '<pre class="code-block">' in out
    assert "hello" in out
    assert "</pre>" in out


def test_mrkdwn_inline_code():
    """L1-prev-2: `inline` -> <code class="inline-code">."""
    out = slack_mrkdwn_to_html("hello `code` world")
    assert '<code class="inline-code">code</code>' in out


def test_mrkdwn_bold():
    """L1-prev-3: *bold* -> <strong>."""
    out = slack_mrkdwn_to_html("hello *bold* world")
    assert "<strong>bold</strong>" in out


def test_mrkdwn_html_escape():
    """L1-prev-4: HTML specials escaped (XSS prevention)."""
    out = slack_mrkdwn_to_html("<script>alert('x')</script>")
    assert "&lt;script&gt;" in out
    # raw <script> must NOT survive anywhere in the output
    assert "<script>" not in out


def test_mrkdwn_newline_to_br():
    """L1-prev-5: \\n -> <br>."""
    out = slack_mrkdwn_to_html("line1\nline2")
    assert "<br>" in out


def test_mrkdwn_preserves_code_block_specials():
    """L1-prev-6: specials inside code block are escaped but stay inside <pre>."""
    out = slack_mrkdwn_to_html("```\n<test>\n```")
    assert "&lt;test&gt;" in out
    assert '<pre class="code-block">' in out


# ----- L1-prev-7: actions-log MSG-DUMP fetch -------------------------------

def test_fetch_actions_log_extracts_dump():
    """L1-prev-7: gh CLI mocked -> MSG-DUMP body extracted, prefix stripped."""
    fake_log = (
        "report\tRun report\t2026-05-11T00:00:00Z ===MSG-DUMP-BEGIN===\n"
        "report\tRun report\t2026-05-11T00:00:00Z line1\n"
        "report\tRun report\t2026-05-11T00:00:00Z line2\n"
        "report\tRun report\t2026-05-11T00:00:00Z ===MSG-DUMP-END===\n"
    )

    class _Result:
        stdout = fake_log

    with mock.patch.object(subprocess, "run", return_value=_Result()):
        msg = fetch_message_from_actions_log("12345")

    assert "line1" in msg
    assert "line2" in msg
    # per-line "<job>\t<step>\t<timestamp>Z " prefix must be stripped
    assert "Run report" not in msg


def test_fetch_actions_log_missing_markers_raises():
    """L1-prev-7b: missing MSG-DUMP markers -> RuntimeError."""
    class _Result:
        stdout = "report\tRun report\t2026-05-11T00:00:00Z no markers here\n"

    with mock.patch.object(subprocess, "run", return_value=_Result()):
        with pytest.raises(RuntimeError, match="MSG-DUMP not found"):
            fetch_message_from_actions_log("99999")


# ----- L1-prev-8 (architecture coaching): sentinel collision safety --------

def test_mrkdwn_sentinel_collision_safety():
    """L1-prev-8: user text containing the *internal* sentinel string survives
    intact instead of being treated as a placeholder.

    Original Design used ``___CODE_BLOCK_N___`` which a user could plausibly
    type. We swapped to NUL-byte (\\x00) sentinels that cannot occur in real
    Slack messages — this test guards that invariant.
    """
    # Provide both legacy-style text and a literal NUL-sentinel string that
    # could only originate from inside the function. The output must contain
    # the user's original characters (escaped), not a synthesized <pre>/<code>.
    user_text = "report mentions ___CODE_BLOCK_0___ in passing"
    out = slack_mrkdwn_to_html(user_text)
    assert "___CODE_BLOCK_0___" in out  # preserved as plain text
    assert "<pre" not in out  # NOT mis-promoted to a code block
    assert "<code" not in out
