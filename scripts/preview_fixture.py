"""Phase 2-NoAI v6 — fixture 기반 메시지 미리보기 (네트워크 호출 없음).

사용:
    python scripts/preview_fixture.py

목적:
    - yfinance/번역 호출 없이 build_v15_message 출력 형식만 빠르게 검증
    - 매번 슬랙 모바일 스크린샷 안 찍어도 메시지 모양 확인 가능
    - 폭 진단 출력으로 모바일 줄바꿈 위험 라인 자동 경고

FR-23 (Plan/Design 후속).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Repo root을 import path에 추가
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Windows 콘솔 UTF-8 강제
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from data import Quote  # noqa: E402
from signals import compute_signals  # noqa: E402
from main import (  # noqa: E402
    build_v15_message,
    _print_message_dump,
    _print_width_diagnostics,
)
from news import NewsSnapshot  # noqa: E402


def _q(
    ticker: str,
    label: str,
    category: str,
    sector: str | None,
    last: float,
    prev: float,
    *,
    open_today: float | None = None,
    volume_today: float | None = None,
    volume_avg_20d: float | None = None,
    high_52w: float | None = None,
    afterhours_close: float | None = None,
) -> Quote:
    return Quote(
        ticker=ticker,
        label=label,
        category=category,  # type: ignore[arg-type]
        sector=sector,
        last_close=last,
        prev_close=prev,
        last_date=date(2026, 5, 8),
        is_stale=False,
        open_today=open_today,
        volume_today=volume_today,
        volume_avg_20d=volume_avg_20d,
        high_52w=high_52w,
        afterhours_close=afterhours_close,
    )


# 실 운영과 유사한 fixture (강한 단타 신호 포함)
FIXTURE_QUOTES = [
    _q("^IXIC", "나스닥", "index", None, 26247.08, 25806.20),
    _q("^GSPC", "S&P 500", "index", None, 7398.93, 7337.11),
    _q("^DJI", "다우", "index", None, 49609.16, 49596.97),
    _q("^RUT", "러셀2000", "index", None, 2861.21, 2839.63),
    _q("^VIX", "VIX", "index", None, 17.19, 17.08),
    _q("ES=F", "S&P 미니", "future", None, 7401.50, 7419.42),
    _q("NQ=F", "나스닥 미니", "future", None, 29277.50, 29333.71),
    _q("YM=F", "다우 미니", "future", None, 49555, 49721),
    _q("NVDA", "엔비디아", "stock", "반도체", 142.30, 140.20,
       volume_today=2_500_000, volume_avg_20d=1_000_000, open_today=141, high_52w=200),
    _q("AMD", "AMD", "stock", "반도체", 455.19, 408.46,
       volume_today=8_000_000, volume_avg_20d=1_500_000, open_today=410,
       high_52w=456, afterhours_close=461),
    _q("MU", "마이크론", "stock", "반도체", 746.81, 646.63,
       volume_today=80_000_000, volume_avg_20d=10_000_000, open_today=730,
       high_52w=747, afterhours_close=757),
    _q("INTC", "인텔", "stock", "반도체", 124.92, 109.62),
    _q("AAPL", "애플", "stock", "빅테크", 293.32, 287.44),
    _q("MSFT", "마이크로소프트", "stock", "빅테크", 425.80, 431.58),
    _q("GOOGL", "구글", "stock", "빅테크", 400.80, 397.99),
    _q("AMZN", "아마존", "stock", "빅테크", 245.30, 244.00),
    _q("META", "메타", "stock", "빅테크", 612.40, 619.60),
    _q("TSLA", "테슬라", "stock", "EV/암호", 312.40, 300.33),
    _q("COIN", "코인베이스", "stock", "EV/암호", 201.16, 192.96),
    _q("USDKRW=X", "원/달러", "macro", None, 1461.43, 1454.79),
    _q("CL=F", "WTI", "macro", None, 97.94, 95.42),
    _q("GC=F", "금", "macro", None, 4700.10, 4720.40),
    _q("BTC-USD", "비트코인", "macro", None, 81926.29, 80664.37),
]

FIXTURE_NEWS = {
    "MU": NewsSnapshot(
        "MU",
        ("AI 랠리에 마이크론 메모리 수요 급증", "Reuters", 0.64),
        None, 3, None,
    ),
    "AMD": NewsSnapshot(
        "AMD",
        ("AMD 신규 AI 가속기 출시, 시장 점유율 ↑", "Bloomberg", 0.52),
        None, None, 1_400_000.0,  # 인사이더 발화
    ),
    "TSLA": NewsSnapshot(
        "TSLA",
        None, None, None,
        3_200_000.0,  # 인사이더만
    ),
}


def main() -> int:
    signals = compute_signals(FIXTURE_QUOTES)
    message = build_v15_message(FIXTURE_QUOTES, signals, news_map=FIXTURE_NEWS)
    _print_message_dump(message)
    _print_width_diagnostics(message)
    print(f"\n[PREVIEW-FIXTURE] {len(message)} chars, {len(message.splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
