# Design Ref: §8 Test Plan — L1-1 ~ L1-6 단위/통합 테스트
"""L1 단위·통합 테스트.

기본 실행 (네트워크 의존 제외):
    pytest

통합 테스트까지 포함:
    pytest -m "integration or not integration"

통합 테스트만:
    pytest -m integration
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import config
import main
from main import IndexQuote, _format_quote_line, build_message, post_slack


# ─────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────

def _q(
    ticker: str = "^IXIC",
    label: str = "나스닥",
    last: float = 17234.50,
    prev: float = 17089.18,
    last_date_: date = date(2026, 5, 10),
    is_stale: bool = False,
) -> IndexQuote:
    return IndexQuote(
        ticker=ticker,
        label=label,
        last_close=last,
        prev_close=prev,
        last_date=last_date_,
        is_stale=is_stale,
    )


# ─────────────────────────────────────────────────────────────
# L1-1 / L1-2 — build_message 포맷
# ─────────────────────────────────────────────────────────────

def test_l1_1_build_message_normal_format():
    """L1-1 (Design §8): 평상시 헤더 + 두 라인 + 상승🟢/하락🔴 동시 표시."""
    quotes = [
        _q(ticker="^IXIC", label="나스닥", last=17234.50, prev=17089.18),
        _q(ticker="^GSPC", label="S&P 500", last=5432.10, prev=5444.55),
    ]
    msg = build_message(quotes)

    assert "나스닥 ^IXIC" in msg
    assert "S&P 500 ^GSPC" in msg
    assert "🟢" in msg
    assert "🔴" in msg
    assert "직전 거래일: 2026-05-10" in msg
    assert "미 증시 휴장" not in msg


def test_l1_2_build_message_stale_format():
    """L1-2 (Design §8): is_stale=True → '(미 증시 휴장 / 마지막 거래일)' 부가."""
    quotes = [_q(is_stale=True, last_date_=date(2026, 5, 9))]
    msg = build_message(quotes)

    assert "미 증시 휴장 / 마지막 거래일" in msg
    assert "직전 거래일: 2026-05-09" in msg


# ─────────────────────────────────────────────────────────────
# L1-3 — 변동률 계산 정확도 + boundary
# ─────────────────────────────────────────────────────────────

def test_l1_3_pct_change_positive():
    """L1-3 (Design §8): (17234.50 − 17089.18) / 17089.18 × 100 ≈ +0.85%."""
    line = _format_quote_line(_q(last=17234.50, prev=17089.18))
    assert "+0.85%" in line
    assert "+145.32" in line
    assert "▲" in line
    assert "🟢" in line


def test_l1_3b_pct_change_negative():
    line = _format_quote_line(_q(last=5432.10, prev=5444.55))
    assert "-0.23%" in line
    assert "-12.45" in line
    assert "▼" in line
    assert "🔴" in line


def test_l1_3c_pct_change_zero_boundary():
    """0% 경계 — ⚪ + ■."""
    line = _format_quote_line(_q(last=100.00, prev=100.00))
    assert "+0.00%" in line
    assert "⚪" in line
    assert "■" in line


def test_l1_3d_prev_close_zero_no_division_error():
    """방어: prev_close=0 일 때 division-by-zero 발생 안 함."""
    line = _format_quote_line(_q(last=100.00, prev=0.0))
    assert "⚪" in line or "+0.00%" in line


# ─────────────────────────────────────────────────────────────
# Phase 2 확장점 — extra_blocks (Plan NFR-06)
# ─────────────────────────────────────────────────────────────

def test_extra_blocks_appended():
    """NFR-06: extra_blocks를 전달하면 헤더/지수 라인 뒤에 부가됨."""
    quotes = [_q()]
    msg = build_message(
        quotes,
        extra_blocks=["📰 시장 뉴스 헤드라인", "🤖 AI 브리핑 한 줄 요약"],
    )
    assert "📰 시장 뉴스 헤드라인" in msg
    assert "🤖 AI 브리핑 한 줄 요약" in msg

    # 부가 블록은 지수 라인 뒤에 와야 함
    idx_pos = msg.find("나스닥 ^IXIC")
    extra_pos = msg.find("📰")
    assert idx_pos != -1 and extra_pos != -1 and extra_pos > idx_pos


def test_extra_blocks_default_none_backwards_compatible():
    """기본값 None — 기존 호출과 결과 동일 (Phase 1 호환성)."""
    quotes = [_q()]
    assert build_message(quotes) == build_message(quotes, extra_blocks=None)


# ─────────────────────────────────────────────────────────────
# L1-5 — post_slack 재시도 / 4xx 즉시 실패
# ─────────────────────────────────────────────────────────────

@patch("main.time.sleep", return_value=None)
@patch("main.requests.post")
def test_l1_5_post_slack_5xx_retries_then_runtimeerror(mock_post, _mock_sleep):
    """L1-5 (Design §8): 5xx 응답 → RETRY_ATTEMPTS 회 호출 → RuntimeError."""
    mock_post.return_value = MagicMock(status_code=503, text="Service Unavailable")
    with pytest.raises(RuntimeError, match="재시도 후"):
        post_slack("https://hooks.slack.com/test", "msg")
    assert mock_post.call_count == config.RETRY_ATTEMPTS


@patch("main.time.sleep", return_value=None)
@patch("main.requests.post")
def test_l1_5b_post_slack_429_retries(mock_post, _mock_sleep):
    """429 (rate limit) 도 재시도 대상."""
    mock_post.return_value = MagicMock(status_code=429, text="rate_limited")
    with pytest.raises(RuntimeError):
        post_slack("https://hooks.slack.com/test", "msg")
    assert mock_post.call_count == config.RETRY_ATTEMPTS


@patch("main.time.sleep", return_value=None)
@patch("main.requests.post")
def test_l1_5c_post_slack_4xx_no_retry(mock_post, _mock_sleep):
    """L1-5 (Design §9): 4xx (예: 400 invalid_payload) 즉시 실패, 재시도 없음."""
    mock_post.return_value = MagicMock(status_code=400, text="invalid_payload")
    with pytest.raises(RuntimeError, match="재시도 무의미"):
        post_slack("https://hooks.slack.com/test", "msg")
    assert mock_post.call_count == 1


@patch("main.requests.post")
def test_post_slack_200_success(mock_post):
    """L1-6 정상 케이스(목): 200 응답 → 1회 호출 후 정상 종료."""
    mock_post.return_value = MagicMock(status_code=200, text="ok")
    post_slack("https://hooks.slack.com/test", "msg")
    assert mock_post.call_count == 1


# ─────────────────────────────────────────────────────────────
# config.load_slack_webhook_url — Plan SC-4
# ─────────────────────────────────────────────────────────────

def test_load_slack_webhook_url_missing_env_raises(monkeypatch):
    """SC-4: 환경변수 미설정 → RuntimeError."""
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with pytest.raises(RuntimeError, match="SLACK_WEBHOOK_URL"):
        config.load_slack_webhook_url()


def test_load_slack_webhook_url_set_returns_value(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/abc")
    assert config.load_slack_webhook_url() == "https://hooks.slack.com/services/abc"


def test_load_slack_webhook_url_blank_raises(monkeypatch):
    """공백만 있어도 미설정으로 처리."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "   ")
    with pytest.raises(RuntimeError):
        config.load_slack_webhook_url()


# ─────────────────────────────────────────────────────────────
# build_message 빈 입력 방어
# ─────────────────────────────────────────────────────────────

def test_build_message_empty_quotes_raises():
    with pytest.raises(RuntimeError, match="비어있"):
        build_message([])


# ─────────────────────────────────────────────────────────────
# L1-4 — fetch_indices 통합 (외부 API 의존, 기본 제외)
# ─────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_l1_4_fetch_indices_real_yfinance():
    """L1-4 (Design §8): 실제 Yahoo Finance 호출 — TICKERS 수만큼 IndexQuote 반환.

    네트워크/외부 API 의존이므로 ``pytest -m integration`` 으로만 실행.
    """
    quotes = main.fetch_indices()
    assert len(quotes) == len(config.TICKERS)
    for q in quotes:
        assert q.last_close > 0
        assert q.prev_close > 0
        assert q.ticker in {t for t, _ in config.TICKERS}
