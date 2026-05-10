---
name: morning-us-index-noai-v2
type: plan
version: 0.1.0
status: draft
phase: plan
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
builds_on: morning-us-index-v15 (Phase 1.5, completed)
prd: null
proposal: docs/proposal/phase2-noai/{beginner,developer}.md
---

# Plan — morning-us-index-noai-v2 (Phase 2-NoAI: 뉴스/어닝스/인사이더 추가, AI 미사용)

## Executive Summary

| 관점 | 한 줄 요약 |
|---|---|
| **Problem** | Phase 1.5 메시지에 단타 신호(🔥🎯🆙)는 있지만 "왜 떴는지" 단서 없음. AI 추론은 비용·복잡도 증가. |
| **Solution** | yfinance(.news, .earnings_dates, .insider_purchases) + vaderSentiment lexicon으로 **뉴스 헤드라인 + 감성 점수 + 어닝스 임박 + 인사이더 매수**를 무료 추가. AI 0, 비용 0. |
| **Function · UX · Effect** | 단타 후보 옆에 📰 헤드라인 + ±점수 / 종목 줄 옆 📅3d 어닝스 배지 / 새 섹션 💼 인사이더 매수. 메시지 하나로 단타 결정 단서 자동 스크리닝. |
| **Core Value** | "**아침 슬랙 1통이 점수판 → 단서판으로 진화**" — AI 없이 사실 기반으로 단타 진입 결정에 직접적인 단서 제공. |

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 단타 후보의 "왜 떴는지" 객관적 단서를 매일 아침 자동 매칭. 지식 미세 조정보다 사실 노출 |
| **WHO** | 준 (단일 사용자, 단타 트레이더). KST 06:00 = 미장 마감 후 1–2시간 |
| **RISK** | yfinance.news 비공식 API 변경 / VADER 30% 오답 / 메시지 4000자 한도 / 인사이더 SEC 지연 |
| **SUCCESS** | 단타 후보에 헤드라인 매칭률 ≥80% / 메시지 ≤4000자 / Phase 1.5 회귀 0 / 운영 ≤30s |
| **SCOPE** | F1(헤드라인+감성) + F2(어닝스 배지) + F3(인사이더 매수). 14 종목 전체 헤드라인 X, 거시 캘린더 X |

---

## 1. Overview

Phase 1.5 (yfinance 풍부화 + 단타 신호 5종) 위에 **객관적 사실 데이터 3종**을 추가. AI/LLM API 없이 무료 라이브러리 1개(`vaderSentiment`)만 추가. Phase 1.5 코드 경로(Quote dataclass, fetch_all, compute_signals, build_v15_message)는 변경 0; 새 모듈 `news.py`만 추가하고 `build_v15_message` 시그니처를 `news_map=None` 옵션으로 확장.

**핵심 차별점**: AI는 "왜 시장이 이렇게 움직였나"를 추측해주지만, 무료 데이터 조합은 **사실 그 자체**(헤드라인/날짜/금액)를 노출. 단타 트레이더 입장에서 추론보다 사실이 더 직접적인 결정 단서.

## 2. Background & Problem

### 2.1 Phase 1.5의 정보 한계

현재 메시지 (Phase 1.5):
```
• 엔비디아 NVDA: 142.30  ▲ +2.10 (+1.50%) 🟢 🔥
• 인텔 INTC: 32.15  ▲ +3.95 (+13.96%) 🟢 🎯🔥

🚨 [오늘 단타 후보]
• 엔비디아 NVDA — 🔥🎯
```

부족:
- **"왜 떴는지" 모름** — 호재로 떴나? 단순 모멘텀? 인덱스 리밸런싱?
- **다음 어닝스 모름** — 오늘 사면 모레 실적 폭탄 가능성
- **임원 자금 흐름 모름** — 임원 매수 = 강한 confidence 신호인데 못 봄

### 2.2 단타(상한가 눌림목) 트레이딩 패턴 요구

준의 사용 시나리오: 매일 KST 06:00 슬랙 메시지로 30초 안에 "오늘 어떤 종목 볼지" 결정.

이 패턴에서 추가 가치 큰 데이터:
- **종목 뉴스 매칭** = 단타 후보의 진입 정당성 확인
- **어닝스 임박** = 사기 직전 폭탄 회피
- **인사이더 매수** = 임원이 "이 회사 잘 될 것" 베팅 — 강한 신호

→ Phase 2-NoAI 3 features = 위 3개 패턴을 자동 마크.

## 3. Goals & Non-Goals

### 3.1 Goals
- **G1.** 단타 후보(신호 ≥2) 종목별 Top 1 헤드라인 + VADER compound score (`|score| ≥ 0.3`만 surface)
- **G2.** 종목 줄 끝에 어닝스 임박 배지 (≤7일)
- **G3.** 인사이더 매수 7일 누적 ≥ $1M 종목 별도 섹션 자동 생성
- **G4.** Phase 1.5 회귀 **0건** (71 테스트 그대로 통과)
- **G5.** 메시지 길이 ≤ Slack 4,000자 (압축 정책 자동 적용)
- **G6.** 운영 실행 시간 ≤ 30초 (Phase 1.5 9.3s + news ~7s)
- **G7.** 신규 단위/통합 테스트 ≥ **22 케이스**

### 3.2 Non-Goals (이번 사이클에서 안 함)
- ❌ AI/LLM API 사용 (Phase 2-AI 별도)
- ❌ 14 종목 전체 헤드라인 — signal-to-noise 비율 붕괴
- ❌ 거시 이벤트 캘린더 (FOMC/CPI 하드코딩) — 부패 위험
- ❌ Reddit/WSB 트렌딩 (유료화로 ROI 낮음)
- ❌ 한국 시장 통합 (Phase 3)
- ❌ 멀티 채널 라우팅 / 차트 이미지 (Phase 3)
- ❌ 실시간 알림 (Phase 4)

## 4. Requirements

### 4.1 Functional Requirements

| ID | 요구사항 | 비고 |
|---|---|---|
| **FR-01** | `news.py` 신규 모듈 — `NewsSnapshot` dataclass + `fetch_news_all()` | Phase 1.5 `data.py`와 별개 |
| **FR-02** | `NewsSnapshot` dataclass 필드 | `top_headline: tuple[str, str, float] \| None` (title, source, vader_compound), `next_earnings_date: date \| None`, `days_to_earnings: int \| None`, `insider_net_buy_usd_7d: float \| None` |
| **FR-03** | F1 — 단타 후보 종목별 헤드라인 + 감성 | yfinance.Ticker.news 결과 중 첫 번째 적합 항목 + VADER compound. `\|compound\| ≥ 0.3`만 메시지에 surface |
| **FR-04** | F2 — 어닝스 배지 inline | yfinance.Ticker.earnings_dates 활용. days_to_earnings ≤ 7이면 종목 줄 끝에 `📅Xd` 배지 |
| **FR-05** | F3 — 인사이더 매수 섹션 | yfinance.Ticker.insider_purchases 7일 합산 net buy ≥ $1M 종목만 별도 섹션 `💼 [내부자 매수 급증 7일]` |
| **FR-06** | 호출 전략 — `ThreadPoolExecutor(max_workers=8)` 병렬 | 14 stocks × ~1s = serial 14s → 병렬 ~3–4s |
| **FR-07** | 부분 실패 허용 | 일부 ticker news/earnings/insider 실패 시 해당만 누락, 다른 종목은 정상 표시. fail-open |
| **FR-08** | `build_v15_message` 시그니처 확장 — `news_map: dict[str, NewsSnapshot] \| None = None` | `None` 시 Phase 1.5 메시지와 동일 (호환성 보장) |
| **FR-09** | 메시지 통합 — 단타 후보 줄 아래 들여쓰기로 헤드라인 추가 | `└ 📰 +0.74 "Title" (Source)` 형태 |
| **FR-10** | 인사이더 섹션 — 거시 섹션 다음, 단타 후보 섹션 이전 위치 | 메시지 흐름에 자연스럽게 |
| **FR-11** | feature flag `ENABLE_NEWS` (env var) | `ENABLE_NEWS=true` 시만 news_map fetch + 메시지 포함. default true. 비활성화 시 Phase 1.5 동작 |
| **FR-12** | 압축 정책 — 4000자 초과 시 뉴스 헤드라인부터 drop | 기존 `_compress_if_needed` 재사용 |
| **FR-13** | F1 헤드라인 영문 → 한글 번역 (메시지 표시) | `deep-translator>=1.11.4` (Google 무료 endpoint, API 키 0). VADER score는 영문 원문으로 계산 후 번역. 번역 실패 시 원문 fallback (fail-open). `ENABLE_NEWS_TRANSLATION` env flag (default true). 운영 후 추가됨 (2026-05-11) |

### 4.2 Non-Functional Requirements

| ID | 요구사항 | 측정 |
|---|---|---|
| NFR-01 | 메시지 길이 | ≤ 4,000 chars (Slack 한도) |
| NFR-02 | 단일 실행 시간 | ≤ 30초 (Phase 1.5의 9.3s + news ~7s = ~16s, 안전마진 2배) |
| NFR-03 | Secrets 노출 | 0건 (Webhook URL 외 추가 secret 없음) |
| NFR-04 | 의존성 추가 | **2개**: `vaderSentiment>=3.3.2`, `deep-translator>=1.11.4` (FR-13 후속 추가) |
| NFR-05 | Phase 1.5 회귀 | 0건 (71 테스트 그대로 통과) |
| NFR-06 | 신규 테스트 | ≥ 22 케이스 |
| NFR-07 | Phase 1.5 호환성 | `build_v15_message(quotes, signals)` 호출 시 `news_map=None` default → 동일 출력 |
| NFR-08 | 메시지 가독성 | 단타 후보 헤드라인 들여쓰기 + 인사이더 별도 섹션 + 어닝스 배지 inline |

## 5. User Stories & Acceptance Criteria

### US-1. 단타 후보의 "왜 떴는지" 즉시 파악
> *준으로서, 단타 후보 종목 옆에 그날 그 회사 뉴스 1개 + 좋은/나쁜 점수가 자동으로 박혀 있으면 진입 정당성을 5초 안에 판단하고 싶다.*

**AC:**
- ✅ 단타 후보 줄 아래 들여쓰기로 `└ 📰 +0.74 "Headline" (Source)` 형태 표시
- ✅ |compound| < 0.3 인 헤드라인은 "불확실"으로 surface 안 함 (혼란 방지)
- ✅ 헤드라인 데이터 없으면 후보 줄만 표시, 들여쓰기 줄 생략

### US-2. 어닝스 폭탄 사전 회피
> *오늘 사려는 종목이 모레 실적 발표면 알고 사고 싶다.*

**AC:**
- ✅ 종목 줄 끝에 `📅3d` (어닝스까지 일수) 배지 표시
- ✅ 7일 초과면 배지 미표시 (노이즈 방지)
- ✅ days_to_earnings 데이터 없으면 배지 미표시 (조용히 생략)

### US-3. 인사이더 매수 알림
> *임원이 자기 회사 주식 사면 강한 신호인데, 일일이 SEC Form 4 보지 않아도 자동 알림 받고 싶다.*

**AC:**
- ✅ 7일 누적 임원 순매수 ≥ $1M인 종목만 새 섹션에 표시
- ✅ 표시 형식: `• TSLA 테슬라: 임원 N명 +$X.XM 매수`
- ✅ 해당 종목 0이면 섹션 자체 생략

### US-4. 회귀 안전성 보장
> *Phase 1.5 메시지/테스트가 그대로 작동해야 한다. 새 기능 때문에 기존 흐름 깨지면 안 됨.*

**AC:**
- ✅ Phase 1.5의 71 테스트 모두 통과 (변경 없이)
- ✅ `ENABLE_NEWS=false` 시 메시지 출력 = Phase 1.5와 byte 단위 동일
- ✅ `build_v15_message(quotes, signals)` 호출 (news_map 생략) = `news_map=None` 명시 = 동일

## 6. Success Criteria (Measurable)

| ID | 지표 | 목표 | 측정 방식 |
|---|---|---|---|
| SC-2N-1 | 단타 후보 헤드라인 매칭률 | ≥ 80% (보통 운영 중 단타 후보 ≥1 헤드라인) | 7일 운영 후 슬랙 메시지 수기 검증 |
| SC-2N-2 | 어닝스 배지 정확도 | 100% (yfinance.earnings_dates와 일치) | 단위 테스트 + 7일 검증 |
| SC-2N-3 | 인사이더 섹션 발화 빈도 | 월 ≥ 2회 (의미 있는 수준) | 30일 운영 후 측정 |
| SC-2N-4 | 메시지 ≤ 4,000자 | 100% | 통합 테스트 + 운영 측정 |
| SC-2N-5 | Phase 1.5 회귀 0건 | 100% | `pytest tests/test_main.py tests/test_data.py tests/test_signals.py tests/test_v15_message.py` 71 통과 유지 |
| SC-2N-6 | 운영 실행 시간 ≤ 30초 | 100% | GitHub Actions log timestamp |
| SC-2N-7 | VADER \|compound\| ≥ 0.3 surface 정확도 | ≥ 70% (정확한 긍/부정 분류) | 30개 헤드라인 수기 검증 |
| SC-2N-8 | 신규 테스트 ≥ 22 | 100% | `pytest --collect-only \| wc -l` |

## 7. Constraints & Assumptions

### 7.1 Constraints
- **C-1.** AI/LLM API 사용 금지 (Phase 2-AI 분리)
- **C-2.** 의존성 추가 ≤ 1개 (`vaderSentiment`만)
- **C-3.** Secrets 추가 0
- **C-4.** Phase 1.5 코드 경로 변경 최소 (`build_v15_message` 시그니처만 확장)
- **C-5.** Slack 메시지 4,000자 한도
- **C-6.** 1일 1회 KST 06:00 발송 주기 그대로

### 7.2 Assumptions
- **A-1.** yfinance.Ticker.news가 14 종목 모두 ≥ 1 결과 반환 (실패 시 fail-open)
- **A-2.** `ThreadPoolExecutor(max_workers=8)`로 14 ticker × 3 종류 데이터 호출이 30초 내 완료
- **A-3.** VADER lexicon이 영문 금융 헤드라인에 대해 ~70% 정확도 유지 (조사 결과)
- **A-4.** SEC Form 4 데이터는 1–2일 지연 — KST 06:00 = 미장 마감 후라 허용
- **A-5.** ENABLE_NEWS feature flag는 기본 true (운영 즉시 활성화)

## 8. Risks & Mitigations

| ID | 위험 | 영향 | 확률 | 대응 |
|---|---|---|---|---|
| **R-1** | yfinance.Ticker.news 비공식 API 스키마 변경 | 헤드라인 누락 | 중 | defensive dict access, fail-open. 누락 시 후보 줄만 표시, 메시지 발송 정상 |
| **R-2** | VADER 30% 오답 (예: "dwindles" 사전 누락) | 잘못된 점수 표시 | 중 | `\|compound\| ≥ 0.3` threshold로 confidence 보강, 0.3 미만은 surface 안 함 |
| **R-3** | 4,000자 초과 (단타 후보 5+ + 어닝스 + 인사이더 동시) | 메시지 잘림 | 중 | `_compress_if_needed`가 뉴스 헤드라인부터 drop, 거시/시간외 순서로 |
| **R-4** | 인사이더 데이터 SEC 지연 1–2일 | 신호 늦음 | 저 | 허용 (KST 06:00 포스트마켓이라 영향 적음) |
| **R-5** | Phase 1.5 회귀 | 운영 메시지 깨짐 | 저 | `news_map=None` default + try/except fail-open. 71 테스트 회귀 검증 |
| **R-6** | ThreadPoolExecutor 동시 호출로 yfinance rate limit | 부분 실패 | 저 | max_workers=8 (보수적), 부분 실패 허용 |
| **R-7** | yfinance.Ticker.earnings_dates 일부 종목 NaT 반환 | 어닝스 배지 누락 | 저 | None 처리, 배지 표시 안 함 |
| **R-8** | 인사이더 데이터 비어있음 (일반적) | F3 섹션 표시 안 됨 | 저 | 정상 동작 (해당 종목 0이면 섹션 생략) |

## 9. Out of Scope (Phase 3+)

(상위 morning-us-index Plan §9 참조)
- **Phase 2-AI** — Gemini/Claude API + News API 활용한 자연어 종합 브리핑 (`/pdca pm morning-us-index-ai`)
- **Phase 3** — 한국 시장 통합 + KOSPI/KOSDAQ + 멀티 채널 + 차트 이미지
- **Phase 4** — Self-hosted runner / 실시간 5% 급등락 알림 / Healthchecks 모니터링

## 10. Roadmap & Milestones

| 마일스톤 | 산출물 | DoD |
|---|---|---|
| M1 — Plan ✅ | 본 문서 | 4 Checkpoint 통과, 사용자 승인 |
| M2 — Design | `docs/02-design/features/morning-us-index-noai-v2.design.md` | 3 옵션 비교 + 모듈 맵 + 메시지 mockup + 22 테스트 플랜 |
| M3 — Do | 코드 확장 + 22 테스트 | 로컬 `python main.py` 정상 메시지 (헤드라인+배지+인사이더 중 ≥1) 출력 |
| M4 — Check | analysis.md | Match Rate ≥ 90% |
| M5 — Iter (필요 시) | | 100% 도달 |
| M6 — Deploy | git push + workflow_dispatch | 슬랙 도착, 메시지 검증 |
| M7 — Report | report.md | Phase 2-NoAI 종료 + Phase 3 안내 |

## 11. Open Questions

| ID | 질문 | 결정 시점 |
|---|---|---|
| OQ-1 | yfinance.Ticker.news 응답 스키마 변경 시 fallback (현재 fail-open만) | Design |
| OQ-2 | `ENABLE_NEWS` feature flag default — true vs false | Design (현재 true 가정) |
| OQ-3 | 헤드라인 길이 truncate 정책 (예: 60자 초과면 ...) | Design |
| OQ-4 | 인사이더 섹션 정렬 — 매수 금액 큰 순 vs ticker 알파벳 순 | Design |
| OQ-5 | Phase 1.5 보험 cron `'30 21 * * *'` 제거 시점 — Phase 2-NoAI 운영 안정 후? | Do or Report |

## 12. References

- Phase 1 Plan: `docs/01-plan/features/morning-us-index.plan.md`
- Phase 1.5 Plan: `docs/01-plan/features/morning-us-index-v15.plan.md`
- Phase 1.5 Design: `docs/02-design/features/morning-us-index-v15.design.md`
- Phase 1.5 Analysis: `docs/03-analysis/morning-us-index-v15.analysis.md`
- **Proposal docs**: `docs/proposal/phase2-noai/{beginner,developer}.md`
- yfinance: https://github.com/ranaroussi/yfinance
- vaderSentiment: https://github.com/cjhutto/vaderSentiment
- VADER vs TextBlob 금융 정확도 연구: https://jds-online.org/journal/JDS/article/1441/info
- SEC EDGAR API: https://www.sec.gov/search-filings/edgar-application-programming-interfaces

---

**다음 단계**: `/pdca design morning-us-index-noai-v2`
