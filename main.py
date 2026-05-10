# Design Ref: §3, §4 — Option C (Pragmatic Balance): main.py 한 파일에 3개 순수 함수
# + main() 오케스트레이터. Phase 2 확장 시 build_message 시그니처에 extra_blocks 추가.
"""morning-us-index — 미국 증시 일일 종가 슬랙 발송 스크립트.

매일 KST 06:00 (UTC 21:00) GitHub Actions cron에서 실행.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
import yfinance as yf

from config import (
    HTTP_CONNECT_TIMEOUT_SEC,
    HTTP_READ_TIMEOUT_SEC,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_SEC,
    STALE_THRESHOLD_DAYS,
    TICKERS,
    TIMEZONE_KST,
    YFINANCE_PERIOD,
    load_slack_webhook_url,
)


@dataclass(frozen=True)
class IndexQuote:
    """단일 지수의 직전 거래일/그 이전 거래일 종가 스냅샷.

    `is_stale=True` 의 정의: 발송 시점(KST) 기준으로 last_date가
    STALE_THRESHOLD_DAYS(=2) 일 이상 과거. 즉 미 증시 휴장 다음 날.
    """

    ticker: str
    label: str
    last_close: float
    prev_close: float
    last_date: date
    is_stale: bool


# ─────────────────────────────────────────────────────────────
# fetch
# ─────────────────────────────────────────────────────────────

def fetch_indices() -> list[IndexQuote]:
    """yfinance로 TICKERS의 직전 2거래일 종가를 조회하여 IndexQuote 리스트 반환.

    Plan SC-2: 종가/변동률 정확도 100%
    Plan SC-3: 휴장일 표기 정확도

    Raises:
        RuntimeError: 데이터 부족(거래일 < 2) 또는 yfinance 호출 실패.
    """
    now_kst = datetime.now(ZoneInfo(TIMEZONE_KST)).date()
    quotes: list[IndexQuote] = []

    for ticker_symbol, label in TICKERS:
        try:
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(period=YFINANCE_PERIOD, auto_adjust=True, actions=False)
        except Exception as e:
            raise RuntimeError(
                f"yfinance 조회 실패 ({ticker_symbol}): {type(e).__name__}: {e}"
            ) from e

        df = df.dropna(subset=["Close"])
        if df.empty or len(df) < 2:
            raise RuntimeError(
                f"yfinance 데이터 부족 ({ticker_symbol}): "
                f"거래일 행 {len(df)}개 (최소 2 필요)"
            )

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        last_date = df.index[-1].date()

        is_stale = (now_kst - last_date).days >= STALE_THRESHOLD_DAYS

        quotes.append(
            IndexQuote(
                ticker=ticker_symbol,
                label=label,
                last_close=float(last_row["Close"]),
                prev_close=float(prev_row["Close"]),
                last_date=last_date,
                is_stale=is_stale,
            )
        )

    return quotes


# ─────────────────────────────────────────────────────────────
# format
# ─────────────────────────────────────────────────────────────

def _format_quote_line(q: IndexQuote) -> str:
    delta = q.last_close - q.prev_close
    pct = (delta / q.prev_close) * 100.0 if q.prev_close != 0 else 0.0

    if pct > 0:
        arrow, emoji = "▲", "🟢"
    elif pct < 0:
        arrow, emoji = "▼", "🔴"
    else:
        arrow, emoji = "■", "⚪"

    return (
        f"• {q.label} {q.ticker}: "
        f"{q.last_close:,.2f}  "
        f"{arrow} {delta:+.2f} ({pct:+.2f}%) {emoji}"
    )


def build_message(
    quotes: list[IndexQuote],
    extra_blocks: list[str] | None = None,
) -> str:
    """Slack 마크다운 본문 빌드. 순수 함수 (외부 호출/I/O 없음).

    Plan NFR-06: Phase 2(AI/뉴스) 시 ``extra_blocks``에 마크다운 라인 리스트를
    전달하면 헤더 + 지수 라인 다음에 부가됨. 기본값 ``None``이라 Phase 1
    호환성에 영향이 없음.
    """
    if not quotes:
        raise RuntimeError("build_message: quotes 리스트가 비어있습니다.")

    now_kst = datetime.now(ZoneInfo(TIMEZONE_KST))
    header_date = now_kst.strftime("%Y-%m-%d")
    last_trading_date = max(q.last_date for q in quotes)
    any_stale = any(q.is_stale for q in quotes)

    if any_stale:
        header = (
            f"[{header_date} KST 06:00 발송] "
            f"직전 거래일: {last_trading_date.isoformat()} "
            f"(미 증시 휴장 / 마지막 거래일)"
        )
    else:
        header = (
            f"[{header_date} KST 06:00 발송] "
            f"직전 거래일: {last_trading_date.isoformat()}"
        )

    lines = [header] + [_format_quote_line(q) for q in quotes]
    if extra_blocks:
        lines.extend(extra_blocks)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# notify
# ─────────────────────────────────────────────────────────────

def post_slack(webhook_url: str, message: str) -> None:
    """Slack Incoming Webhook으로 POST. 5xx/429만 재시도, 4xx는 즉시 실패.

    Plan FR-07, FR-08: 3회 지수 백오프(30s/60s/120s).
    """
    payload = {"text": message}
    timeout = (HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC)
    last_error: str = ""

    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = requests.post(webhook_url, json=payload, timeout=timeout)
            if response.status_code == 200:
                return

            body_excerpt = response.text[:200] if response.text else ""
            if response.status_code == 429 or 500 <= response.status_code < 600:
                last_error = f"HTTP {response.status_code}: {body_excerpt}"
            else:
                raise RuntimeError(
                    f"Slack 발송 실패 (재시도 무의미, HTTP {response.status_code}): "
                    f"{body_excerpt}"
                )
        except requests.exceptions.Timeout as e:
            last_error = f"Timeout: {e}"
        except requests.exceptions.ConnectionError as e:
            last_error = f"ConnectionError: {e}"

        if attempt < RETRY_ATTEMPTS - 1:
            wait_sec = (
                RETRY_BACKOFF_SEC[attempt]
                if attempt < len(RETRY_BACKOFF_SEC)
                else RETRY_BACKOFF_SEC[-1]
            )
            time.sleep(wait_sec)

    raise RuntimeError(
        f"Slack 발송 실패 ({RETRY_ATTEMPTS}회 재시도 후): {last_error}"
    )


# ─────────────────────────────────────────────────────────────
# orchestration
# ─────────────────────────────────────────────────────────────

def main() -> int:
    """오케스트레이터: fetch → build → post. 실패 시 best-effort 슬랙 에러 알림.

    Returns:
        int: 0 = 성공, 1 = 실패 (GitHub Actions에 fail로 전달).
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        webhook_url = load_slack_webhook_url()
        quotes = fetch_indices()
        message = build_message(quotes)
        post_slack(webhook_url, message)
        print("[OK] morning-us-index 발송 완료")
        return 0
    except Exception as e:
        error_text = f"[ERROR] {type(e).__name__}: {e}"
        sys.stderr.write(error_text + "\n")

        # best-effort: 에러도 슬랙으로 통지 (실패해도 swallow)
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
        if webhook_url:
            try:
                requests.post(
                    webhook_url,
                    json={"text": f"⚠️ morning-us-index 실행 실패\n```{error_text}```"},
                    timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC),
                )
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
