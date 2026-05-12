# Design Ref: §4.3 — Phase 1.5 단타 신호 5종 + 사상최고 + 섹터 분류
"""morning-us-index-v15 신호 계산 모듈 (순수 함수).

5종 단타 신호:
    🔥 거래량 spike   (volume / 20일 평균 ≥ 2.0)
    🎯 갭             (|open - prev_close| / prev_close ≥ 1.5%)
    ⚡ VIX 급등       (^VIX 일중 변동 ≥ 5%)
    🆙 52주 신고가    (last_close ≥ 52w high × 0.99)
    📊 시간외 변동    (afterhours / regular close ≥ 1%)

별도:
    ★ 사상최고        (last_close ≥ 52w high × 0.999)
"""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    SECTOR_MAP,
    SIGNAL_52W_HIGH_STAR_RATIO,
    SIGNAL_52W_HIGH_THRESHOLD_RATIO,
    SIGNAL_AFTERHOURS_THRESHOLD_PCT,
    SIGNAL_GAP_THRESHOLD_PCT,
    SIGNAL_VIX_CHANGE_THRESHOLD_PCT,
    SIGNAL_VOLUME_RATIO_THRESHOLD,
)
from data import Quote


@dataclass(frozen=True)
class Signal:
    """단타 신호 5종 + 사상최고 결과."""

    ticker: str
    is_volume_spike: bool       # 🔥
    is_gap: bool                # 🎯
    is_vix_spike: bool          # ⚡  (^VIX ticker만)
    is_52w_near_high: bool      # 🆙
    is_all_time_high: bool      # ★  (52w_near_high의 더 엄격한 임계)
    is_afterhours_move: bool    # 📊

    @property
    def emoji_marks(self) -> str:
        """메시지 라인에 부착될 단타 신호 이모지 (★는 별도 처리)."""
        marks: list[str] = []
        if self.is_volume_spike:
            marks.append("🔥")
        if self.is_gap:
            marks.append("🎯")
        if self.is_vix_spike:
            marks.append("⚡")
        if self.is_52w_near_high:
            marks.append("🆙")
        if self.is_afterhours_move:
            marks.append("📊")
        return "".join(marks)

    @property
    def signal_count(self) -> int:
        """발생한 단타 신호 수 (★ 사상최고는 카운트 제외 — 추세 신호이지 단타 신호 아님).

        OQ-4: 단타 후보 자동 요약 임계 = 2 이상.
        """
        return sum(
            (
                self.is_volume_spike,
                self.is_gap,
                self.is_vix_spike,
                self.is_52w_near_high,
                self.is_afterhours_move,
            )
        )


def get_sector(ticker: str) -> str | None:
    """수동 섹터 매핑 조회. 매핑 없으면 ``None``."""
    return SECTOR_MAP.get(ticker)


def compute_signals(quotes: list[Quote]) -> dict[str, Signal]:
    """각 ``Quote``에 대해 5종 신호 + 사상최고 계산.

    Plan SC-1.5-2: 신호 정확도 ≥ 95% (단위 테스트로 검증).

    Returns:
        ``{ticker: Signal}`` dict.
    """
    # ^VIX 일중 변동률 (모든 종목의 is_vix_spike 계산용 — 실제로는 ^VIX 본인만 True)
    vix_quote = next((q for q in quotes if q.ticker == "^VIX"), None)
    vix_pct = 0.0
    if vix_quote is not None and vix_quote.prev_close:
        vix_pct = abs((vix_quote.last_close - vix_quote.prev_close) / vix_quote.prev_close * 100.0)

    signals: dict[str, Signal] = {}

    for q in quotes:
        # 🎯 갭 — VIX는 변동성 지수라 갭 개념이 무의미하므로 제외
        gap_pct = 0.0
        if q.ticker != "^VIX" and q.open_today is not None and q.prev_close:
            gap_pct = abs((q.open_today - q.prev_close) / q.prev_close * 100.0)

        # 🔥 거래량
        vol_ratio = 0.0
        if q.volume_today is not None and q.volume_avg_20d:
            vol_ratio = q.volume_today / q.volume_avg_20d

        # 📊 시간외
        ah_pct = 0.0
        if q.afterhours_close is not None and q.last_close:
            ah_pct = abs((q.afterhours_close - q.last_close) / q.last_close * 100.0)

        # 🆙 / ★ 52주 비율
        ratio_to_52w = 0.0
        if q.high_52w:
            ratio_to_52w = q.last_close / q.high_52w

        signals[q.ticker] = Signal(
            ticker=q.ticker,
            is_volume_spike=vol_ratio >= SIGNAL_VOLUME_RATIO_THRESHOLD,
            is_gap=gap_pct >= SIGNAL_GAP_THRESHOLD_PCT,
            is_vix_spike=(
                q.ticker == "^VIX" and vix_pct >= SIGNAL_VIX_CHANGE_THRESHOLD_PCT
            ),
            is_52w_near_high=ratio_to_52w >= SIGNAL_52W_HIGH_THRESHOLD_RATIO,
            is_all_time_high=ratio_to_52w >= SIGNAL_52W_HIGH_STAR_RATIO,
            is_afterhours_move=ah_pct >= SIGNAL_AFTERHOURS_THRESHOLD_PCT,
        )

    return signals
