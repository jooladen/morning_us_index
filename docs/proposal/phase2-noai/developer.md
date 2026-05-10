# 🔵 Phase 2-NoAI 제안 (Developer)

> News + Earnings + Insider analysis WITHOUT LLM API. yfinance + vaderSentiment lexicon.

생성: 2026-05-11 · 상태: Plan-only proposal

---

## TL;DR

**3 features 채택** (5 후보 중 선별):

| # | 기능 | 데이터 소스 | 비고 |
|---|---|---|---|
| **F1** | Top 1 headline + VADER compound per 단타 후보 | `yfinance.Ticker.news` + `vaderSentiment` | lexicon-based, no ML |
| **F2** | Earnings badge (≤7d) inline in stock lines | `yfinance.Ticker.earnings_dates` | 종목 줄 끝에 `📅3d` |
| **F3** | Insider buying spike (7d sum ≥ $1M) | `yfinance.Ticker.insider_purchases` | 별도 섹션, 발화 시만 |

**제외**: 14 종목 전체 헤드라인 (signal-to-noise ↓), 거시 캘린더 (하드코딩 부패).

---

## Architecture (Option C — Phase 1.5 회귀 0)

핵심 결정: **`Quote` dataclass 미수정**, 별도 `dict[ticker, NewsSnapshot]`로 전달.

```
data.py          → 변경 없음 (Quote frozen, Phase 1.5 71 테스트 그대로)
signals.py       → 변경 없음
news.py          🆕 NewsSnapshot dataclass + fetch_news_all() (ThreadPoolExecutor)
config.py        → +12 줄 (NEWS_TOP_K=1, EARNINGS_LOOKAHEAD_DAYS=7,
                            INSIDER_BUY_USD_THRESHOLD=1_000_000, ENABLE_NEWS=True)
main.py          → build_v15_message(quotes, signals, news_map=None)
                    default None → Phase 1.5 호환성 보장
                  + main() 흐름에 news.fetch_news_all() (try/except fail-open)
requirements.txt → +1 줄: vaderSentiment>=3.3.2
```

---

## NewsSnapshot dataclass

```python
@dataclass(frozen=True)
class NewsSnapshot:
    ticker: str
    top_headline: tuple[str, str, float] | None  # (title, source, vader_compound -1..+1)
    next_earnings_date: date | None
    days_to_earnings: int | None
    insider_net_buy_usd_7d: float | None  # 양수=순매수
```

---

## Critical Files (수정/생성)

| 파일 | 액션 | 라인 |
|---|---|---:|
| `news.py` | **신규** | ~220 |
| `tests/test_news.py` | **신규** | ~250 |
| `main.py` | 수정 (build_v15_message + 단타 후보 + 인사이더 섹션) | +40 |
| `tests/test_v15_message.py` | 수정 (news_map 케이스 추가) | +60 |
| `config.py` | 수정 (4 상수 추가) | +12 |
| `requirements.txt` | 수정 (vaderSentiment 추가) | +1 |
| **합계** | | **~580** |

---

## 메시지 통합 출력 예시

```
[2026-05-12 KST 06:00 발송] 직전 거래일: 2026-05-11

📈 [지수] ... (기존 그대로)

🏭 [반도체]
• 엔비디아 NVDA: 142.30  ▲ +2.10 (+1.50%) 🟢 🔥 📅3d   ← F2
• 인텔 INTC: 32.15  ▲ +3.95 (+13.96%) 🟢 🎯🔥
... (기존)

🚨 [오늘 단타 후보 (신호 2개 이상)]
• 엔비디아 NVDA — 🔥🎯 (거래량 + 갭)
  └ 📰 +0.74 "Nvidia beats Q3 estimates, raises guidance" (Reuters)   ← F1
• 인텔 INTC — 🎯🔥 (갭 + 거래량)
  └ 📰 -0.12 "Intel reorganization sparks investor concern" (Bloomberg)

💼 [내부자 매수 급증 7일 (≥$1M)]   ← F3 (해당 종목 있을 때만)
• TSLA 테슬라: 임원 4명 +$3.2M 매수
```

---

## Existing Functions/Utilities to Reuse

| 자원 | 위치 | 재사용 방식 |
|---|---|---|
| `_compress_if_needed()` | `main.py` | 4000자 초과 시 자동 압축 — 뉴스 섹션도 cover |
| `Signal.signal_count` | `signals.py:37-65` | 단타 후보 결정(≥2) — F1 매칭 종목 필터링 |
| `STOCKS` 리스트 | `config.py:48-62` | F1/F2/F3 모두 STOCKS만 대상 |
| `post_slack` retry | `main.py` | 변경 없음 |
| `pytest.ini` markers | `pytest.ini` | `@pytest.mark.integration` 그대로 사용 |
| `unittest.mock.patch` 패턴 | `tests/test_main.py` | `patch("news.requests.get")` 식 |

---

## Performance Budget

- Phase 1.5 통합 테스트 baseline: **9.3s**
- 신규 비용 추정:
  - 14 stocks × `Ticker.news` (~1s/each) = serial **14s** ❌
  - **`ThreadPoolExecutor(max_workers=8)` → ~3–4s** ✅
  - 어닝스 + 인사이더는 후보 종목만(≤5개 일반적) → +2s
- **총 운영 ~16s** — NFR-02(60s) 충분 마진
- 캐시 비활성: cron 1회/일, GitHub Actions FS 비영구

---

## VADER 정확도 노트

| 케이스 | VADER compound | 정확? |
|---|---|:---:|
| "Nvidia beats Q3 estimates, raises guidance" | +0.74 | ✅ |
| "Stock dwindles after disappointing earnings" | +0.10 | ❌ ("dwindles" 사전 누락) |
| "Company faces lawsuit" | -0.42 | ✅ |
| "Tesla shares surge on AI breakthrough" | +0.65 | ✅ |
| "Intel reorganization sparks investor concern" | -0.12 | ✅ |

→ **정확도 ~70%** (TextBlob 51% 대비 우수). `|compound| ≥ 0.3`만 surface하여 confidence 보강 (낮은 confidence는 색칠 안 함).

---

## Risks (ranked)

| # | 위험 | 영향 | 완화 |
|---|---|:---:|---|
| **R-1** | `yfinance.Ticker.news` 비공식 API — 스키마 변경 가능 | High | defensive dict access, fail-open (뉴스 없어도 메시지 발송) |
| **R-2** | 4000자 초과 — 단타 후보 5개 + 어닝스 + 인사이더 동시 발화 | Med | `_compress_if_needed`가 뉴스 헤드라인부터 drop |
| **R-3** | VADER 30% 오답 | Low | 점수만 노출, 사용자 판단; threshold `|compound| ≥ 0.3` |
| **R-4** | 인사이더 데이터 SEC 지연 1–2일 | Low | KST 06:00 = 포스트마켓이라 허용 |
| **R-5** | Phase 1.5 회귀 | Low | `news_map=None` default + try/except → 회귀 0 |

---

## Trade-offs vs Phase 2 (AI)

| 기준 | Phase 2 (AI) | **Phase 2-NoAI (이 안)** |
|---|---|---|
| 운영비 | $1–10/월 | **$0** |
| 의존성 | google-genai/anthropic + News API | **vaderSentiment 1개** |
| 작업량 | 1–2일 | **반나절** |
| Secrets 추가 | 2 | **0** |
| "왜 떴는지" 추론 | ✅ 자연어 종합 | ❌ raw 데이터 |
| 객관성 | 추론 의존 | **사실 그대로** |
| 유지보수 위험 | API 가격/정책 변경 | yfinance 변경만 |
| 단타 결정 직접성 | 추상적 | **구체적** |

---

## Verification

### 단계별 PR 분리 (안전 롤아웃)

| PR | 범위 | 검증 |
|---|---|---|
| **PR1** | `news.py` 골격 + `NewsSnapshot` + VADER 단위 테스트 (network mock) | `pytest tests/test_news.py` 통과 |
| **PR2** | `fetch_news_all()` ThreadPoolExecutor + mocked-network 테스트 | 성능: <5s mock 호출 |
| **PR3** | `main.py` wire-up + feature flag `ENABLE_NEWS=True` | 로컬 실 슬랙 발송 검증 |
| **PR4** | 어닝스 + 인사이더 (PR3가 운영 3일 안정 후) | 운영 KST 06:00 자동 발송 도착 확인 |

### End-to-end 검증 명령

```powershell
# 1. 단위 테스트 (회귀 0 확인)
cd C:\Users\jooladen\Desktop\stock\morning_us_index
pytest                                          # Phase 1.5 65 + news 22 = ~87 unit tests

# 2. 통합 테스트 (실 yfinance 호출)
pytest -m integration                           # Phase 1.5 6 + news 4 = 10

# 3. 로컬 실 발송 (Slack Webhook 필요)
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/..."
$env:ENABLE_NEWS = "true"
python main.py                                  # 슬랙 도착 — 단타 후보 + 헤드라인 / 어닝스 배지 / 인사이더 섹션

# 4. 운영 검증
gh workflow run "Daily US Index Report"         # 즉시 1회
gh run view --log                               # 실행 시간 ≤30s 목표
```

### 통과 기준

- ✅ Phase 1.5 71 테스트 모두 통과 (회귀 0)
- ✅ 신규 ~22 테스트 통과
- ✅ 로컬 실 발송에 (a) 단타 후보 헤드라인 (b) 어닝스 배지 (c) 인사이더 섹션 중 ≥1개 표시
- ✅ 메시지 ≤4000자
- ✅ 운영 실행 시간 ≤30s
- ✅ ENABLE_NEWS=False 시 Phase 1.5 메시지와 동일

---

## Test Plan (~22 신규)

### `tests/test_news.py` 신규 (~250줄)

| 분류 | 케이스 수 | 내용 |
|---|---:|---|
| VADER scoring on fixtures | 6 | positive/negative/neutral/sarcasm boundary/financial jargon |
| `fetch_news_for_ticker` mocked | 4 | success/empty/exception/schema-change |
| `next_earnings_within_days` | 4 | no data / today / 5d out / past date |
| Insider 집계 | 4 | no transactions / buys only / mixed / $-filter |
| 동시 fetch (ThreadPoolExecutor) | 2 | dict 키 ticker, partial failure 허용 |

### `tests/test_v15_message.py` +6 케이스

| ID | 항목 |
|---|---|
| 1 | news block render when present |
| 2 | news block omitted when news_map=None (Phase 1.5 호환) |
| 3 | 4000-char compression preserves core (드롭 우선순위: 뉴스 헤드라인 → 거시 → 시간외) |
| 4 | 어닝스 배지 format `📅3d` |
| 5 | 인사이더 섹션 헤더 |
| 6 | 단타 후보 0개 → 헤드라인 0개 (no orphan headlines) |

---

## Implementation Sequencing

```
[현재 Phase 1.5 100% 완료]
       ↓
[PR1] news.py 골격 + VADER 테스트 (mock only, no network)
       ↓
[PR2] fetch_news_all() ThreadPoolExecutor + perf test
       ↓
[PR3] main.py wire-up + feature flag (ENABLE_NEWS)
       ↓ deploy with flag OFF, validate locally, flip ON
[PR3 운영 3일 안정 확인]
       ↓
[PR4] 어닝스 + 인사이더 추가
       ↓
[/pdca analyze morning-us-index-noai-v2]
```

---

## 다음 단계

```
/pdca plan morning-us-index-noai-v2
```

PRD 단계는 단일 사용자 + 단일 채널이라 생략 가능. Plan부터 시작 권장.

---

## References

- yfinance Ticker.news / earnings_dates / insider_purchases: https://github.com/ranaroussi/yfinance
- vaderSentiment package: https://github.com/cjhutto/vaderSentiment
- VADER vs TextBlob 금융 정확도 연구: https://jds-online.org/journal/JDS/article/1441/info
- SEC EDGAR API: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- 본 프로젝트:
  - Phase 1.5 Plan: `docs/01-plan/features/morning-us-index-v15.plan.md`
  - Phase 1.5 Design: `docs/02-design/features/morning-us-index-v15.design.md`
  - Phase 1.5 Analysis: `docs/03-analysis/morning-us-index-v15.analysis.md`
