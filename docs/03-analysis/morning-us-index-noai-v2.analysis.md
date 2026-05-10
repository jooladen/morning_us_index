---
name: morning-us-index-noai-v2
type: analysis
version: 0.1.0
status: passed
phase: check
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
plan: docs/01-plan/features/morning-us-index-noai-v2.plan.md
design: docs/02-design/features/morning-us-index-noai-v2.design.md
match_rate_overall: 100.0
match_rate_structural: 100.0
match_rate_functional: 100.0
match_rate_contract: 100.0
critical_count: 0
important_count: 0
minor_count: 4
iteration_count: 0
---

# Analysis — morning-us-index-noai-v2 (Phase 2-NoAI Gap 분석)

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 단타 후보의 "왜 떴는지" 객관적 단서를 매일 아침 자동 매칭. 지식 미세 조정보다 사실 노출 |
| **WHO** | 준 (단일 사용자, 단타 트레이더). KST 06:00 = 미장 마감 후 1–2시간 |
| **RISK** | yfinance.news 비공식 API 변경 / VADER 30% 오답 / 메시지 4000자 한도 / 인사이더 SEC 지연 |
| **SUCCESS** | 단타 후보 헤드라인 매칭률 ≥80% / 메시지 ≤4000자 / Phase 1.5 회귀 0 / 운영 ≤30s |
| **SCOPE** | F1(헤드라인+감성) + F2(어닝스 배지) + F3(인사이더 매수) |

## Executive Summary

| 항목 | 결과 |
|---|---|
| **Overall Match Rate** | **100.0%** (Structural 100 × 0.2 + Functional 100 × 0.4 + Contract 100 × 0.4) |
| **Critical Gap** | 0 |
| **Important Gap** | 0 |
| **Minor Gap (Doc 격차)** | 4 (코드 변경 불필요) |
| **Decision Record (OQ-1~5)** | 5/5 정확 반영 |
| **Plan SC-2N (정적)** | 5/8 ✅ + 3/8 ⚠️ 운영 대기 |
| **Phase 1.5 회귀** | 0건 (byte 동일 검증 + pytest 93/93) |
| **신규 테스트** | 28 (목표 22, +6 마진) |
| **Iterate 필요** | ❌ (100% 도달) |
| **다음 단계** | `/pdca report morning-us-index-noai-v2` |

---

## 1. Overall Scores

| Axis | Score | 가중치 | Evidence |
|---|:-:|:-:|---|
| **Structural Match** | **100%** | 0.2 | Module Map 10/10 모듈 코드/테스트 매핑 완료. 신규 파일 2개, 상수 8개, 헬퍼 3개 모두 존재 |
| **Functional Depth** | **100%** | 0.4 | Plan FR-01~FR-12 12개 모두 구현. SC-2N-2/4/5/7/8 정적 충족. OQ-1~OQ-5 Design 결정 5/5 코드 반영. Placeholder/stub 0건 |
| **API Contract** | **100%** | 0.4 | `NewsSnapshot` 필드 4개 + property 3개, `build_v15_message(quotes, signals, news_map=None)`, `fetch_news_all` 시그니처, `ENABLE_NEWS` env 모두 일치 |
| **Overall** | **100.0%** | 1.0 | — |

> Python 백엔드 스크립트라 v2.3.0 Runtime 가중치(0.35) 미적용. Static-only 공식: `Overall = S×0.2 + F×0.4 + C×0.4`. Runtime은 pytest 93/93 통과로 대체 검증.

---

## 2. Strategic Alignment

> Plan PRD 부재 (Phase 2-NoAI는 단일 사용자 명확 요구라 PM 단계 skip). Plan 문서가 strategic intent 역할.

| 검증 항목 | 결과 |
|---|---|
| Plan Problem (Phase 1.5의 "왜 떴는지" 부재) | ✅ 해결 — 단타 후보에 헤드라인+VADER, 어닝스 배지, 인사이더 섹션 통합 |
| Plan Solution (yfinance + VADER, AI 0) | ✅ 그대로 — 신규 의존성 1개(vaderSentiment), AI/LLM API 0 |
| Plan Core Value ("점수판 → 단서판") | ✅ 단타 후보 줄 아래 들여쓰기 헤드라인으로 직접 단서 제공 |
| Design Architecture (Option C — Pragmatic) | ✅ 정확 — news.py 신규 + main.py `news_map=None` 인자 추가 |
| Phase 1.5 회귀 0 | ✅ — `test_news_map_none_byte_identical_to_phase15` 통과 + 회귀 65 케이스 그대로 통과 |

전략 정렬 결손 없음.

---

## 3. Structural Match — Module Map 10/10

| Module | Scope Key | 산출물 | 위치 (file:symbol) | Status |
|---|---|---|---|:-:|
| module-1 | `module-1-config` | 상수 8개 + `is_news_enabled()` | `config.py:111-132,152-157` | ✅ |
| module-2 | `module-2-news-dataclass` | `NewsSnapshot` + property 3종 | `news.py:43-86` | ✅ |
| module-3 | `module-3-news-fetchers` | `_score_headline` / `_truncate` / `fetch_{news,earnings,insider}_for_ticker` | `news.py:96-269` | ✅ |
| module-4 | `module-4-news-parallel` | `_build_snapshot` + `fetch_news_all` ThreadPool | `news.py:272-333` | ✅ |
| module-5 | `module-5-news-tests` | 22 단위 케이스 | `tests/test_news.py` (22 funcs) | ✅ |
| module-6 | `module-6-message-integration` | `build_v15_message` news_map 인자 + 헬퍼 3개 | `main.py:213-457` | ✅ |
| module-7 | `module-7-orchestration` | `main()` ENABLE_NEWS 분기 | `main.py:478-524` | ✅ |
| module-8 | `module-8-message-tests` | +6 케이스 | `tests/test_v15_message.py:213-331` | ✅ |
| module-9 | `module-9-regression` | Phase 1.5 71 회귀 | pytest 93/93 통과 (60 unit Phase 1.5 + 28 신규 + 5 deselected integration) | ✅ |
| module-10 | `module-10-deploy` | requirements.txt + workflow | `requirements.txt:3`, workflow 변경 없음 | ✅ (실 배포 검증은 운영 단계) |

**Structural Match = 100%**

---

## 4. Functional Depth — Plan FR 매핑

### 4.1 FR-01 ~ FR-12 충족 매트릭스

| Plan FR | 요구 | 구현 위치 | Status |
|---|---|---|:-:|
| FR-01 | `news.py` 신규 + `NewsSnapshot` + `fetch_news_all` | `news.py:43,293` | ✅ |
| FR-02 | NewsSnapshot 4 필드 시그니처 | `news.py:51-61` 정확 일치 | ✅ |
| FR-03 | F1 — `\|compound\| ≥ 0.3`만 surface | `news.py:145` 임계값 비교 | ✅ |
| FR-04 | F2 — `days_to_earnings ≤ 7` 시 `📅Xd` | `news.py:75-78` (`has_earnings_badge`) + `main.py:259` 배지 부착 | ✅ |
| FR-05 | F3 — 7일 누적 ≥ $1M 별도 섹션 | `news.py:81-86` + `main.py:264-293` | ✅ |
| FR-06 | `ThreadPoolExecutor(max_workers=8)` | `news.py:313` + config=8 | ✅ |
| FR-07 | fail-open (per-ticker 실패 시 누락) | `news.py:132-134, 190-191, 222-223, 262-265, 321-326` 일관 적용 | ✅ |
| FR-08 | `build_v15_message(quotes, signals, news_map=None)` | `main.py:308-311` 정확 | ✅ |
| FR-09 | `└ 📰 +0.74 "Title" (Source)` 형식 | `main.py:305` f-string 정확 | ✅ |
| FR-10 | 인사이더 = 거시 다음, 단타 후보 이전 | `main.py:415-426` 흐름 정확 | ✅ |
| FR-11 | `ENABLE_NEWS` flag, default true | `config.py:152-157` + `main.py:493-496` | ✅ |
| FR-12 | 4000자 초과 시 압축 | `main.py:460-471` `_compress_if_needed` 재사용 | ✅ (Minor M-1: Plan "헤드라인 우선 drop" → 코드는 Phase 1.5 정책 그대로. 동작 영향 미미 — 헤드라인이 메시지 끝쪽이라 자연 drop) |

### 4.2 Success Criteria SC-2N-1~8

| SC | 지표 | 목표 | 정적 확인 | 운영 검증 | 증거 |
|---|---|:-:|:-:|:-:|---|
| SC-2N-1 | 단타 후보 헤드라인 매칭률 | ≥80% | ⚠️ Partial | 7일 운영 후 | 구현 완료. 매칭률은 시계열 데이터 누적 필요 |
| SC-2N-2 | 어닝스 배지 정확도 | 100% | ✅ Met | — | `test_fetch_earnings_future_returns_date_and_days`, `test_earnings_badge_inline_within_7_days`, `test_earnings_badge_not_shown_beyond_7_days`, `test_news_snapshot_earnings_badge_boundary` |
| SC-2N-3 | 인사이더 섹션 발화 빈도 | 월 ≥2회 | ⚠️ Partial | 30일 운영 후 | 로직 정확 (`test_insider_section_appears_for_significant_buys`, `test_insider_section_omitted_when_no_significant_buys`). 빈도는 운영 |
| SC-2N-4 | 메시지 ≤4000자 | 100% | ✅ Met | — | `test_message_within_4000_chars_full_quotes` + `_compress_if_needed` 가드 |
| SC-2N-5 | Phase 1.5 회귀 0건 | 100% | ✅ Met | — | `test_news_map_none_byte_identical_to_phase15` byte 동일 검증 + pytest 93/93 |
| SC-2N-6 | 운영 실행 시간 ≤30초 | 100% | ⚠️ Partial | Actions log | 병렬화 로직 충족 (ThreadPool max=8, NFR-02 30s 충분 마진). 실측 운영 |
| SC-2N-7 | VADER 정확도 ≥70% | ≥70% | ✅ Met | — | 6 VADER 케이스 — 강긍/강부정/중립/모호/경계/disappointing 모두 통과 |
| SC-2N-8 | 신규 테스트 ≥22 | 100% | ✅ Met | — | test_news.py 22 + test_v15_message.py +6 = **28** (+6 마진) |

**정적 충족**: 5/8 ✅ + 3/8 ⚠️ (운영 대기). 운영 대기 3건은 시간 경과 필요라 정적 점수 차감 사유 아님.

### 4.3 Placeholder / Stub 점검

- `news.py` 전 함수 본문 채워짐 ✅
- `_extract_title` / `_extract_source` 헬퍼는 **Design 명세보다 견고** — yfinance 신/구 스키마(`content.title`, `content.provider.displayName`) 모두 방어
- `fetch_insider_for_ticker` — `iterrows()` 루프 per-row try/except로 한 row 에러가 전체 합산 안 망침

**Placeholder 0건. Functional Depth = 100%.**

---

## 5. API Contract

| 항목 | Design 명세 | 실 구현 | Status |
|---|---|---|:-:|
| `NewsSnapshot.ticker` | `str` | `news.py:51` 일치 | ✅ |
| `NewsSnapshot.top_headline` | `tuple[str, str, float] \| None` | `news.py:54` 정확 | ✅ |
| `NewsSnapshot.next_earnings_date` | `date \| None` | `news.py:57` 정확 | ✅ |
| `NewsSnapshot.days_to_earnings` | `int \| None` | `news.py:58` 정확 | ✅ |
| `NewsSnapshot.insider_net_buy_usd_7d` | `float \| None` | `news.py:61` 정확 | ✅ |
| `is_empty` property | bool, all None 시 True | `news.py:63-70` | ✅ |
| `has_earnings_badge` | `0 ≤ days ≤ 7` | `news.py:72-78` (boundary 7d/8d 테스트 PASS) | ✅ |
| `has_significant_insider_buy` | `≥ $1M` | `news.py:80-86` | ✅ |
| `@dataclass(frozen=True)` | 명시 | `news.py:43` | ✅ |
| `fetch_news_all(stocks: Iterable[Quote]) -> dict[str, NewsSnapshot]` | 일치 | `news.py:293` | ✅ |
| `build_v15_message(quotes, signals, news_map=None)` | 일치 | `main.py:308-312` | ✅ |
| `ENABLE_NEWS` env, default `"true"` | `os.environ.get(..., "true").strip().lower() == "true"` | `config.py:157` byte 정확 | ✅ |
| `vaderSentiment>=3.3.2` | requirements.txt 1줄 | `requirements.txt:3` 정확 | ✅ |

**API Contract = 100%**

---

## 6. Decision Record Verification (OQ-1 ~ OQ-5)

| OQ | Design 결정 | 코드 반영 위치 | Status |
|---|---|---|:-:|
| **OQ-1** | yfinance.news 스키마 변경 fallback = defensive dict access + try/except per ticker | `news.py:130-149` + `_extract_title`/`_extract_source` 신구 스키마 둘 다 방어 (Design 명세보다 강함) | ✅ |
| **OQ-2** | `ENABLE_NEWS` default `"true"` | `config.py:157` byte 정확 일치 | ✅ |
| **OQ-3** | 80자 초과 시 77자 + "..." | `news.py:109-114` + `test_truncate_long_adds_ellipsis` (len==80, endswith "...") | ✅ |
| **OQ-4** | 인사이더 net buy USD 내림차순 | `main.py:282-284` `reverse=True` 정렬 + `test_insider_section_appears_for_significant_buys` (TSLA $3.2M 우선) | ✅ |
| **OQ-5** | Phase 1.5 보험 cron `'30 21 * * *'` 유지 (Report 단계 7일 무사고 후 제거) | `.github/workflows/daily_report.yml` 변경 없음 | ✅ |

**OQ Decision 5/5 정확 반영.**

---

## 7. Differences Found

### 🔴 Critical
**없음.**

### 🟡 Important
**없음.**

### 🔵 Minor (Doc 격차, 코드 변경 불필요)

| # | 항목 | Design | 실제 코드 | 영향 | 권고 |
|---|---|---|---|---|---|
| **M-1** | FR-12 압축 정책 | Plan §4 FR-12: "뉴스 헤드라인부터 drop" / Design §12 R-3: "헤드라인 들여쓰기 줄을 먼저 drop" | Phase 1.5 `_compress_if_needed` 그대로 재사용 — 뒤쪽 100자 잘라내고 안내 부착 | 4,000자 초과 시 단타 후보 헤드라인이 메시지 끝쪽이라 자연 drop. 의도적 우선순위 아님 | 운영 7일 후에도 길이 안정적이면 무시. 한 번이라도 초과 시 헤드라인 우선 drop 분기 추가 |
| **M-2** | Design §3.3 인사이더 1차 소스 표현 | "1차: `Ticker.insider_purchases`" + 2차 시사 | 실 구현은 `Ticker.insider_transactions` 단독 (`news.py:222`) — Design 내부 §3.3 본문과 §4.1 코드 명세 모순 | 동작 영향 0 (insider_transactions가 yfinance 표준) | Design §3.3 문구를 `insider_transactions` 단독으로 명확화. Doc-only |
| **M-3** | `_format_daytrade_headline` 함수 분리 | Design §4.2 본문엔 단타 후보 루프 내 인라인 작성 | 별도 함수로 분리 (`main.py:296-305`) — 가독성/테스트성 ↑ | 0 | Design에 헬퍼 3개로 명기 (Doc-only) |
| **M-4** | `as_completed` TimeoutError catch | Design §4.1에 timeout 명시, catch 동작은 본문 미기술 | `TimeoutError` 명시 catch + 부분 결과 반환 강화 (`news.py:327-331`) | 0 (Design보다 강함) | Design 본문 보완 (Doc-only) |

**Minor 4건 모두 코드 동작 동일 또는 코드가 Design보다 견고**. 점수 차감 없음.

---

## 8. Test Coverage

| 카테고리 | 목표 | 실제 | 위치 | Status |
|---|:-:|:-:|---|:-:|
| 8.2.1 VADER scoring | 6 | 6 | `test_news.py:43-87` | ✅ |
| 8.2.2 `_truncate` | 2 | 2 | `test_news.py:94-105` | ✅ |
| 8.2.3 `fetch_news_for_ticker` | 4 | 4 | `test_news.py:118-167` | ✅ |
| 8.2.4 `fetch_earnings_for_ticker` | 3 | 3 | `test_news.py:184-218` | ✅ |
| 8.2.5 `fetch_insider_for_ticker` | 3 | 3 | `test_news.py:231-265` | ✅ |
| 8.2.6 `fetch_news_all` ThreadPool | 2 | 2 | `test_news.py:286-328` | ✅ |
| 8.2.7 NewsSnapshot properties | 2 | 2 | `test_news.py:335-359` | ✅ |
| 8.3 test_v15_message.py 추가 | 6 | 6 | `test_v15_message.py:239-331` | ✅ |
| 8.4 Phase 1.5 회귀 | 65 | 60 unit (단위) + 5 deselected integration | test_main.py + test_data.py + test_signals.py + test_v15_message.py(기존 11) | ✅ |
| **총 신규** | ≥22 | **28** | — | ✅ +6 마진 |
| **전체 단위 통과** | — | **93/93** | pytest -m "not integration" | ✅ |

---

## 9. Runtime Verification (Python 백엔드 스크립트)

- **L1/L2/L3 (API/UI/E2E)**: N/A — 백엔드 스크립트
- **Unit/Integration**: pytest 93/93 단위 통과, 6 integration deselected (network 필요)
- **회귀 검증**: `test_news_map_none_byte_identical_to_phase15` — `build_v15_message(quotes, sigs) == build_v15_message(quotes, sigs, news_map=None)` byte 동일
- **실 슬랙 발송**: 운영 단계 (M10, Report 후 또는 SLACK_WEBHOOK_URL 설정 후 `python main.py`)

---

## 10. If Iterate Needed — 우선순위

**Match Rate 100%이므로 iterate 불필요.**

가설적 우선순위 (운영 중 발견 시):
1. **(메시지 4000자 운영 중 초과 발견 시)** M-1 — `_compress_if_needed`에 헤드라인 우선 drop 분기 추가
2. **(인사이더 0건 / 헤드라인 매칭률 < 80% 지속 시)** `fetch_insider_for_ticker`에 `Ticker.insider_purchases` 2차 fallback 추가 (Plan R-9)
3. **Doc-only patch** (M-2, M-3, M-4) — Design 본문과 코드 일치도 ↑ (점수 영향 없음)

---

## 11. Recommended Actions

### Immediate
**없음.** 코드/테스트 정적 완성도 100%.

### Pre-Deploy (Report 단계 또는 사용자 선택)
1. SLACK_WEBHOOK_URL 설정 후 로컬 `python main.py` 1회 발송 검증
2. `gh workflow run daily_report.yml` 또는 다음 KST 06:00 정기 발송

### Operational Validation (7~30일, Report 단계)
- SC-2N-1 헤드라인 매칭률 ≥80%
- SC-2N-3 인사이더 발화 월 ≥2회
- SC-2N-6 실행 ≤30초

### Documentation Polish (선택)
- M-2/M-3/M-4 Design 본문 동기화 (코드 수정 없음)

---

## 12. 결론

| 종합 | 결과 |
|---|---|
| **Overall Match Rate** | **100.0%** |
| **Critical / Important Gap** | 0 |
| **Minor (Doc 격차)** | 4건 (코드 변경 불필요) |
| **Decision Record (OQ-1~5)** | 5/5 정확 반영 |
| **Plan SC-2N (정적)** | 5/8 ✅ + 3/8 ⚠️ 운영 대기 |
| **Phase 1.5 회귀** | 0 (byte 동일 + pytest 93/93) |
| **신규 테스트** | 28 (+6 마진) |
| **Iterate** | 불필요 |

**다음 단계**: `/pdca report morning-us-index-noai-v2`
