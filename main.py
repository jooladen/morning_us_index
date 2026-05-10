# Design Ref: §3, §4 — Option C (Pragmatic Balance): main.py 한 파일에 3개 순수 함수
# + main() 오케스트레이터. Phase 2 확장 시 build_message 시그니처에 extra_blocks 추가.
"""morning-us-index — 미국 증시 일일 종가 슬랙 발송 스크립트.

매일 KST 06:00 (UTC 21:00) GitHub Actions cron에서 실행.
"""

from __future__ import annotations

import os
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
import yfinance as yf

from config import (
    DAYTRADE_CANDIDATE_MIN_SIGNALS,
    FOOTER_BEGINNER_GUIDE,
    HTTP_CONNECT_TIMEOUT_SEC,
    HTTP_READ_TIMEOUT_SEC,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_SEC,
    SLACK_MESSAGE_MAX_CHARS,
    STALE_THRESHOLD_DAYS,
    TICKERS,
    TIMEZONE_KST,
    VIX_LABEL_CAUTION_MAX,
    VIX_LABEL_STABLE_MAX,
    YFINANCE_PERIOD,
    is_news_enabled,
    load_slack_webhook_url,
)
from data import Quote, fetch_all
from news import NewsSnapshot, fetch_news_all
from signals import Signal, compute_signals


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
# Phase 1.5 — v15 message builder
# Design Ref: §4.4, §4.5
# ─────────────────────────────────────────────────────────────

def _format_v15_quote_line(q: Quote, sig: Signal) -> str:
    """Phase 1.5 종목 라인 — 신호 마크 + ★ 포함.

    FR-19 (v3): 절대 변동 (예: ``+100.18``) 생략, 변동률만 표시 (괄호 제거).
    좁은 모바일 슬랙 가독성 ↑.
    """
    delta = q.last_close - q.prev_close
    pct = (delta / q.prev_close) * 100.0 if q.prev_close else 0.0

    if pct > 0:
        arrow, emoji = "▲", "🟢"
    elif pct < 0:
        arrow, emoji = "▼", "🔴"
    else:
        arrow, emoji = "■", "⚪"

    star = " ★" if sig.is_all_time_high else ""
    marks = sig.emoji_marks
    marks_str = f" {marks}" if marks else ""

    return (
        f"• {q.label} {q.ticker}: "
        f"{q.last_close:,.2f} "
        f"{arrow} {pct:+.2f}% {emoji}{star}{marks_str}"
    )


def _format_compact_line(q: Quote) -> str:
    """신호 없는 종목 1줄 압축 (라벨 + 변동률만)."""
    pct = ((q.last_close - q.prev_close) / q.prev_close * 100.0) if q.prev_close else 0.0
    return f"• {q.label}: {pct:+.2f}%"


# ─────────────────────────────────────────────────────────────
# Phase 2-NoAI v3 — UX 개선 헬퍼 (FR-15/16/17/19/20)
# ─────────────────────────────────────────────────────────────

def _pct_change(q: Quote) -> float:
    """단순 변동률 % (소수)."""
    if not q.prev_close:
        return 0.0
    return (q.last_close - q.prev_close) / q.prev_close * 100.0


def _vix_context_label(vix_quote: Quote | None) -> str:
    """FR-20: VIX 컨텍스트 라벨 — 안정 / 경계 / 공포.

    임계: <20 안정 / 20–25 경계 / >=25 공포 (CBOE 일반 가이드).
    """
    if vix_quote is None or not vix_quote.last_close:
        return ""
    v = vix_quote.last_close
    if v < VIX_LABEL_STABLE_MAX:
        return "안정"
    if v < VIX_LABEL_CAUTION_MAX:
        return "경계"
    return "공포"


def _format_market_mood_line(quotes: list[Quote]) -> str:
    """FR-15: 시장 동향 한 줄 — 상승/하락 카운트 + VIX 라벨.

    예: ``📊 상승 8 / 하락 6 / VIX 17.19 (안정)``.
    """
    stock_pcts = [_pct_change(q) for q in quotes if q.category == "stock"]
    up_count = sum(1 for p in stock_pcts if p > 0)
    down_count = sum(1 for p in stock_pcts if p < 0)

    vix_quote = next((q for q in quotes if q.ticker == "^VIX"), None)
    if vix_quote is not None and vix_quote.last_close:
        label = _vix_context_label(vix_quote)
        vix_text = (
            f"VIX {vix_quote.last_close:.2f} ({label})" if label
            else f"VIX {vix_quote.last_close:.2f}"
        )
    else:
        vix_text = "VIX N/A"

    return f"📊 상승 {up_count} / 하락 {down_count} / {vix_text}"


def _format_candidate_reasons(q: Quote, sig: Signal) -> str:
    """FR-17/22 (v5): 단타 후보 사유 — 이모지 + 숫자만 한 줄 압축.

    예 입력 → 출력:
        sig(volume×8.5, gap+13.96%, AH+1.5%, 52w) → "🔥8.5× 🎯+12.9% 🆙신고 📊+1.4%"

    모바일 한 줄 30폭 이하 목표. 한글 단어 최소화.
    """
    parts: list[str] = []
    if sig.is_volume_spike:
        if q.volume_today and q.volume_avg_20d:
            ratio = q.volume_today / q.volume_avg_20d
            parts.append(f"🔥{ratio:.1f}×")
        else:
            parts.append("🔥")
    if sig.is_gap:
        if q.open_today and q.prev_close:
            gap = (q.open_today - q.prev_close) / q.prev_close * 100.0
            parts.append(f"🎯{gap:+.1f}%")
        else:
            parts.append("🎯")
    if sig.is_vix_spike:
        parts.append("⚡VIX")
    if sig.is_52w_near_high:
        parts.append("🆙신고")
    if sig.is_afterhours_move:
        if q.afterhours_close and q.last_close:
            ah = (q.afterhours_close - q.last_close) / q.last_close * 100.0
            parts.append(f"📊{ah:+.1f}%")
        else:
            parts.append("📊")
    return " ".join(parts)


def _candidate_sort_key(candidate: tuple[Quote, Signal]) -> tuple[int, float]:
    """FR-16: 단타 후보 정렬 키 — 신호 수 내림차순, 변동률 절댓값 내림차순."""
    q, sig = candidate
    return (-sig.signal_count, -abs(_pct_change(q)))


# ─────────────────────────────────────────────────────────────
# Phase 2-NoAI v4 — 표 형식 (Slack code block + monospace 컬럼 정렬)
# FR-21: 모바일 슬랙 한 줄 표시 (글자 큼 → 라인 잘림 회피)
# ─────────────────────────────────────────────────────────────

def _display_width(text: str) -> int:
    """Slack monospace 폰트 표시 폭 추정 (CJK 2폭, 기타 1폭).

    이모지는 east_asian_width='N'이나 실제 2폭 차지 — 별도 처리.
    """
    width = 0
    for ch in text:
        ea = unicodedata.east_asian_width(ch)
        if ea in ("W", "F"):  # Wide / Fullwidth (CJK)
            width += 2
        elif ord(ch) >= 0x1F300:  # 이모지 영역 (대략)
            width += 2
        else:
            width += 1
    return width


def _pad_right(text: str, target_width: int) -> str:
    """target_width까지 우측 공백 padding (좌측 정렬)."""
    current = _display_width(text)
    if current >= target_width:
        return text
    return text + " " * (target_width - current)


def _pad_left(text: str, target_width: int) -> str:
    """target_width까지 좌측 공백 padding (우측 정렬, 숫자용)."""
    current = _display_width(text)
    if current >= target_width:
        return text
    return " " * (target_width - current) + text


def _build_table_block(rows: list[list[str]], aligns: list[str] | None = None) -> list[str]:
    """rows를 컬럼별 자동 폭 정렬 + ```code block```으로 감싸기.

    Args:
        rows: 각 row = 컬럼 문자열 리스트
        aligns: ["left", "right", ...] 컬럼별 정렬. 기본 left.

    Returns:
        ["```", "row1...", "row2...", "```"] 형태 라인 리스트.
    """
    if not rows:
        return []
    n_cols = max(len(r) for r in rows)
    aligns = aligns or ["left"] * n_cols

    # 컬럼별 max width
    col_widths = [0] * n_cols
    for row in rows:
        for i, cell in enumerate(row):
            w = _display_width(str(cell))
            if w > col_widths[i]:
                col_widths[i] = w

    out = ["```"]
    for row in rows:
        parts = []
        for i, cell in enumerate(row):
            if i >= n_cols:
                break
            if aligns[i] == "right":
                parts.append(_pad_left(str(cell), col_widths[i]))
            else:
                parts.append(_pad_right(str(cell), col_widths[i]))
        out.append("  ".join(parts).rstrip())
    out.append("```")
    return out


# ─────────────────────────────────────────────────────────────
# FR-26 (v7): 표 형식 — code block + 컬럼 정렬
# 컬럼: [label, ticker, price, "+1.50%", marks/star/badge]
# ─────────────────────────────────────────────────────────────

def _quote_to_row(q: Quote, sig: Signal, news: NewsSnapshot | None) -> list[str]:
    """Quote → 표 row (4 컬럼, ticker 제외).

    FR-30 (v9): ticker 컬럼 제거 — 모바일 한 줄 폭 단축 (22 → 15폭).
    컬럼: [label, price, pct, extras]
    """
    pct = _pct_change(q)
    if q.last_close >= 100:
        price_str = f"{q.last_close:,.0f}"
    elif q.last_close >= 1:
        price_str = f"{q.last_close:,.1f}"
    else:
        price_str = f"{q.last_close:.2f}"

    pct_str = f"{pct:+.2f}%"
    star = "★" if sig.is_all_time_high else ""
    marks = sig.emoji_marks
    badge = ""
    if news is not None and news.has_earnings_badge:
        badge = f"📅{news.days_to_earnings}d"

    vix_label = ""
    if q.ticker == "^VIX":
        label = _vix_context_label(q)
        if label:
            vix_label = f"({label})"

    extras = " ".join(filter(None, [star, marks, badge, vix_label]))
    return [q.label, price_str, pct_str, extras]


def _build_compact_table(rows: list[list[str]]) -> list[str]:
    """rows를 ```code block``` + 컬럼 자동 폭 정렬.

    FR-31 (v9): row 사이 구분선 제거 — 모바일에서 자동 줄바꿈으로 어수선.
    Aligns: [left, right, left, left] (4 컬럼: label, price, pct, extras)
    """
    if not rows:
        return []
    aligns = ["left", "right", "left", "left"]
    n_cols = max(len(r) for r in rows)
    col_widths = [0] * n_cols
    for r in rows:
        for i in range(n_cols):
            cell = r[i] if i < len(r) else ""
            w = _display_width(str(cell))
            if w > col_widths[i]:
                col_widths[i] = w

    out = ["```"]
    for r in rows:
        parts = []
        for i in range(n_cols):
            cell = str(r[i]) if i < len(r) else ""
            if not cell and i == n_cols - 1:
                continue  # 마지막 컬럼이 비어있으면 trailing space 제거
            align = aligns[i] if i < len(aligns) else "left"
            if align == "right":
                parts.append(_pad_left(cell, col_widths[i]))
            else:
                parts.append(_pad_right(cell, col_widths[i]))
        out.append(" ".join(parts).rstrip())
    out.append("```")
    return out


def _format_compact_quote(q: Quote, sig: Signal, news: NewsSnapshot | None) -> str:
    """FR-22 (v5): 모바일 한 줄 압축 형식.

    예: ``• 엔비디아 NVDA 142 +1.50% 🔥``

    설계 결정:
    - 가격 정수만 (소수점 제거) — 변동률이 정보 가치 ↑
    - 색상 이모지 🟢🔴 제거 — 변동률 부호로 대체
    - ▲▼ 부호 제거 — `+`/`-` 부호로 대체
    - 단타 신호 마크 + ★ + 📅 배지는 유지 (단타 결정에 필수)
    - VIX는 (안정/경계/공포) 라벨 inline
    """
    pct = _pct_change(q)
    # 가격: 정수만 (천 단위 콤마 유지). 1 이하는 소수점 2자리 (환율/원자재용)
    if q.last_close >= 100:
        price_str = f"{q.last_close:,.0f}"
    elif q.last_close >= 1:
        price_str = f"{q.last_close:,.1f}"
    else:
        price_str = f"{q.last_close:.2f}"

    pct_str = f"{pct:+.2f}%"
    star = "★" if sig.is_all_time_high else ""
    marks = sig.emoji_marks
    badge = ""
    if news is not None and news.has_earnings_badge:
        badge = f"📅{news.days_to_earnings}d"

    # VIX 라벨 (FR-20)
    vix_label = ""
    if q.ticker == "^VIX":
        label = _vix_context_label(q)
        if label:
            vix_label = f"({label})"

    extras = " ".join(filter(None, [star, marks, badge, vix_label]))
    extras_part = f" {extras}" if extras else ""

    return f"• {q.label} {q.ticker} {price_str} {pct_str}{extras_part}"


# ─────────────────────────────────────────────────────────────
# Phase 2-NoAI — Design Ref: §4.2
# build_v15_message news_map 통합 헬퍼 (F2 어닝스 배지, F3 인사이더 섹션)
# ─────────────────────────────────────────────────────────────

def _format_v15_quote_line_with_earnings(
    q: Quote,
    sig: Signal,
    news: NewsSnapshot | None,
) -> str:
    """기존 _format_v15_quote_line + 📅Xd 배지 inline (F2).

    Plan FR-04: ``has_earnings_badge`` 충족 시만 배지 부착.
    """
    base = _format_v15_quote_line(q, sig)
    if news is not None and news.has_earnings_badge:
        return f"{base} 📅{news.days_to_earnings}d"
    return base


def _format_insider_section(
    news_map: dict[str, NewsSnapshot],
    quotes: list[Quote],
) -> list[str]:
    """💼 [내부자 매수 급증 7일 (≥$1M)] 섹션 라인 (F3).

    Plan FR-05: ``has_significant_insider_buy`` 종목만 표시.
    OQ-4: net buy USD 내림차순 정렬.

    Returns:
        섹션 라인 리스트 (헤더 + 종목 라인들 + 빈 줄). 발화 종목 0이면 [].
    """
    label_by_ticker = {q.ticker: q.label for q in quotes}
    significant = [
        ns for ns in news_map.values() if ns.has_significant_insider_buy
    ]
    if not significant:
        return []
    significant.sort(
        key=lambda ns: ns.insider_net_buy_usd_7d or 0.0, reverse=True
    )

    lines = ["[내부자 매수 급증 7일 (≥$1M)]"]
    for ns in significant:
        label = label_by_ticker.get(ns.ticker, ns.ticker)
        usd = ns.insider_net_buy_usd_7d or 0.0
        usd_m = usd / 1_000_000.0
        lines.append(f"• {ns.ticker} {label}: 임원 +${usd_m:,.1f}M 매수")
    lines.append("")
    return lines


def _format_daytrade_headline(news: NewsSnapshot | None) -> str | None:
    """단타 후보 줄 아래 들여쓰기 헤드라인 라인 (F1).

    Plan FR-09: ``  └ 📰 {compound:+.2f} "{title}" ({source})``.
    헤드라인 없으면 None.
    """
    if news is None or news.top_headline is None:
        return None
    title, source, compound = news.top_headline
    return f"  └ 📰 {compound:+.2f} \"{title}\" ({source})"


def build_v15_message(
    quotes: list[Quote],
    signals: dict[str, Signal],
    news_map: dict[str, NewsSnapshot] | None = None,
) -> str:
    """Phase 1.5 + Phase 2-NoAI 슬랙 메시지 빌드.

    섹션 구조:
        - 헤더 (날짜 + 휴장 여부)
        - 📈 [지수]
        - 🎯 [단타 핵심: 선물 + 시간외]
        - 🏭 [반도체] / 📱 [빅테크] / 🚗 [EV/암호]
            └ news_map 있을 때 📅Xd 배지 inline (F2)
        - 💰 [거시]
        - 💼 [내부자 매수 급증 7일 (≥$1M)]   ← Phase 2-NoAI F3 (발화 시만)
        - 🚨 [오늘 단타 후보] (신호 ≥ 2개 종목)
            └ news_map 있을 때 헤드라인 들여쓰기 (F1)

    Plan SC-1.5-4: 단타 후보 자동 요약
    Plan NFR-01: ≤ 4,000자 (압축 정책 자동 적용)
    Plan NFR-07: ``news_map=None`` 시 Phase 1.5와 byte 단위 동일 출력 (회귀 안전).
    """
    if not quotes:
        raise RuntimeError("build_v15_message: quotes 리스트가 비어있습니다.")

    # news_map=None 일 때 헬퍼 접근을 위해 정규화 (Phase 1.5 경로 보존)
    _news_map: dict[str, NewsSnapshot] = news_map or {}

    now_kst = datetime.now(ZoneInfo(TIMEZONE_KST))
    header_date = now_kst.strftime("%Y-%m-%d")
    last_trading_date = max(q.last_date for q in quotes)
    any_stale = any(q.is_stale for q in quotes)

    # FR-21 (v4): 헤더 2줄 분리 — 모바일 한 줄 잘림 방지
    if any_stale:
        header_line1 = f"📅 {header_date} KST 06:00"
        header_line2 = (
            f"직전 거래일: {last_trading_date.isoformat()} "
            f"(미 증시 휴장)"
        )
    else:
        header_line1 = f"📅 {header_date} KST 06:00"
        header_line2 = f"직전 거래일: {last_trading_date.isoformat()}"

    # FR-15: 시장 동향 한 줄
    mood_line = _format_market_mood_line(quotes)

    lines: list[str] = [header_line1, header_line2, mood_line, ""]

    # 카테고리별 분류
    indices = [q for q in quotes if q.category == "index"]
    futures = [q for q in quotes if q.category == "future"]
    stocks = [q for q in quotes if q.category == "stock"]
    macros = [q for q in quotes if q.category == "macro"]

    # FR-29 (v9): 범례 라인 복원 — 💡 prefix는 제거 (사용자 요청)
    lines.append(FOOTER_BEGINNER_GUIDE)
    lines.append("")

    # [지수]
    if indices:
        lines.append("[지수]")
        rows = [_quote_to_row(q, signals[q.ticker], _news_map.get(q.ticker))
                for q in indices if signals.get(q.ticker)]
        lines.extend(_build_compact_table(rows))
        lines.append("")

    # [단타 핵심: 선물 + 시간외]
    has_ahrs = any(
        signals.get(q.ticker) and signals[q.ticker].is_afterhours_move
        for q in stocks
    )
    if futures or has_ahrs:
        lines.append("[단타 핵심: 선물 + 시간외]")
        rows = []
        for q in futures:
            sig = signals.get(q.ticker)
            if sig is not None:
                rows.append(_quote_to_row(q, sig, _news_map.get(q.ticker)))
        for q in stocks:
            sig = signals.get(q.ticker)
            if sig is not None and sig.is_afterhours_move and q.afterhours_close and q.last_close:
                ah_pct = (q.afterhours_close - q.last_close) / q.last_close * 100.0
                # v9: 4 컬럼 (label, price='', pct, extras)
                rows.append([f"AHRS {q.ticker}", "", f"{ah_pct:+.1f}%", "📊"])
        lines.extend(_build_compact_table(rows))
        lines.append("")

    # 섹터별 stocks (반도체, 빅테크, EV/암호) — 헤더 이모지 제거
    sector_groups = [
        ("[반도체]", "반도체"),
        ("[빅테크]", "빅테크"),
        ("[EV/암호]", "EV/암호"),
    ]
    for header_label, sector_name in sector_groups:
        sector_stocks = [q for q in stocks if q.sector == sector_name]
        if not sector_stocks:
            continue
        lines.append(header_label)
        rows = [_quote_to_row(q, signals[q.ticker], _news_map.get(q.ticker))
                for q in sector_stocks if signals.get(q.ticker)]
        lines.extend(_build_compact_table(rows))
        lines.append("")

    # [거시]
    if macros:
        lines.append("[거시]")
        rows = [_quote_to_row(q, signals[q.ticker], _news_map.get(q.ticker))
                for q in macros if signals.get(q.ticker)]
        lines.extend(_build_compact_table(rows))
        lines.append("")

    # 💼 [내부자 매수 급증 7일 (≥$1M)] — Phase 2-NoAI F3 (Plan FR-05, FR-10)
    if _news_map:
        lines.extend(_format_insider_section(_news_map, quotes))

    # 🚨 [오늘 단타 후보 (신호 2개 이상)]
    candidates: list[tuple[Quote, Signal]] = []
    for q in quotes:
        sig = signals.get(q.ticker)
        if sig is not None and sig.signal_count >= DAYTRADE_CANDIDATE_MIN_SIGNALS:
            candidates.append((q, sig))

    # FR-16: 신호 수 내림차순, 변동률 절댓값 내림차순으로 정렬 (강한 신호 먼저)
    candidates.sort(key=_candidate_sort_key)

    if candidates:
        lines.append("[오늘 단타 후보]")
        for q, sig in candidates:
            # FR-22 (v5): 사유에 이모지 포함이라 종목 라인은 종목명+사유 한 줄로 통합
            reason_str = _format_candidate_reasons(q, sig)
            lines.append(f"• {q.label} {q.ticker} {reason_str}")
            # 헤드라인 줄바꿈 (F1) — 50자 truncate
            news = _news_map.get(q.ticker)
            if news is not None and news.top_headline is not None:
                title, source, compound = news.top_headline
                lines.append(f"  📰 {compound:+.2f} \"{title}\" ({source})")
        lines.append("")

    # FR-24 (v7): 푸터 제거 (범례는 상단으로 이동)
    msg = "\n".join(lines).rstrip()
    return _compress_if_needed(msg)


def _compress_if_needed(msg: str) -> str:
    """4,000자 초과 시 truncate + warn (Plan NFR-01)."""
    if len(msg) <= SLACK_MESSAGE_MAX_CHARS:
        return msg
    truncated = (
        msg[: SLACK_MESSAGE_MAX_CHARS - 100]
        + "\n\n[메시지 길이 초과 — 일부 생략됨]"
    )
    sys.stderr.write(
        f"[WARN] 메시지 {len(msg)}자 → {SLACK_MESSAGE_MAX_CHARS}자로 압축\n"
    )
    return truncated


# ─────────────────────────────────────────────────────────────
# FR-23 (v6): 슬랙 발송 메시지 자동 dump + 폭 진단
# 사용자가 모바일 스크린샷 안 찍어도 Ally가 Actions log로 메시지 검증 가능.
# ─────────────────────────────────────────────────────────────

# 모바일 슬랙 한 줄 표시 가능 폭 추정 (한국어 wide 환산)
MOBILE_LINE_WIDTH_THRESHOLD: int = 25


def _print_message_dump(message: str) -> None:
    """메시지 본문을 stdout에 marker 감싸 출력 (Actions log/터미널용).

    Ally(또는 사용자)가 ``gh run view <id> --log``로 메시지 본문 추출 가능:
        gh run view <id> --log | sed -n '/===MSG-DUMP-BEGIN===/,/===MSG-DUMP-END===/p'
    """
    print("\n===MSG-DUMP-BEGIN===")
    print(message)
    print("===MSG-DUMP-END===\n")


def _print_width_diagnostics(message: str) -> None:
    """라인별 폭 측정 + 모바일 줄바꿈 위험 라인 경고 (FR-23).

    Output:
        ===WIDTH-DIAG-BEGIN===
        total: 1123 chars, 38 lines
        max line width: 26 (line 17: '...')
        lines exceeding 25 width: 2
          line 17 (w=26): '...'
          line 23 (w=28): '...'
        ===WIDTH-DIAG-END===
    """
    lines = message.split("\n")
    widths = [(i + 1, _display_width(ln), ln) for i, ln in enumerate(lines)]
    if not widths:
        return
    max_lineno, max_w, max_line = max(widths, key=lambda x: x[1])
    over = [(no, w, ln) for no, w, ln in widths if w > MOBILE_LINE_WIDTH_THRESHOLD]

    print("===WIDTH-DIAG-BEGIN===")
    print(f"total: {len(message)} chars, {len(lines)} lines")
    print(f"max line width: {max_w} (line {max_lineno})")
    print(f"  {max_line!r}")
    print(
        f"lines exceeding mobile threshold ({MOBILE_LINE_WIDTH_THRESHOLD} wide): {len(over)}"
    )
    for no, w, ln in over[:10]:  # 최대 10줄
        print(f"  line {no} (w={w}): {ln}")
    if len(over) > 10:
        print(f"  ... and {len(over) - 10} more")
    print("===WIDTH-DIAG-END===")


# ─────────────────────────────────────────────────────────────
# orchestration (Phase 1.5)
# ─────────────────────────────────────────────────────────────

def main() -> int:
    """오케스트레이터 — Phase 1.5: fetch_all → compute_signals → build_v15_message → post_slack.

    Args (sys.argv):
        --preview: 슬랙 발송 X, 메시지만 stdout 출력 + 폭 진단 (로컬 검증용)

    Returns:
        int: 0 = 성공, 1 = 실패 (GitHub Actions에 fail로 전달).
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    preview_mode = "--preview" in sys.argv

    try:
        # FR-23 (v6): preview 모드에서는 webhook URL 없어도 OK (발송 안 함)
        webhook_url = "" if preview_mode else load_slack_webhook_url()
        quotes = fetch_all()                                # data.py
        signals_map = compute_signals(quotes)               # signals.py

        # Phase 2-NoAI: ENABLE_NEWS=true(default) 시 news_map fetch (Plan FR-11)
        news_map = None
        if is_news_enabled():
            stock_quotes = [q for q in quotes if q.category == "stock"]
            news_map = fetch_news_all(stock_quotes)

        message = build_v15_message(quotes, signals_map, news_map=news_map)

        # FR-23: 메시지 본문 dump (Actions log + 로컬 콘솔용)
        _print_message_dump(message)
        _print_width_diagnostics(message)

        news_count = len(news_map) if news_map else 0
        if preview_mode:
            print(
                f"[PREVIEW] 슬랙 발송 SKIP "
                f"({len(quotes)} quotes, {news_count} news, {len(message)} chars)"
            )
            return 0

        post_slack(webhook_url, message)                    # 기존 그대로
        print(
            f"[OK] morning-us-index-noai-v2 발송 완료 "
            f"({len(quotes)} quotes, {news_count} news, {len(message)} chars)"
        )
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
                    json={
                        "text": f"⚠️ morning-us-index-noai-v2 실행 실패\n```{error_text}```"
                    },
                    timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC),
                )
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
