---
name: morning-us-index-v15
type: plan
version: 0.1.0
status: draft
phase: plan
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
builds_on: morning-us-index (Phase 1, completed)
prd: null
---

# Plan — morning-us-index-v15 (Phase 1.5: yfinance 단독 풍부화 + 단타 신호)

## Executive Summary

| 관점 | 한 줄 요약 |
|---|---|
| **Problem** | Phase 1은 지수 2개(^IXIC, ^GSPC)만 알려줌. 단타 트레이더에게는 선물/시간외/거래량 이상/VIX/개별 종목 신호가 없어 "오늘 어디로 갈 시장인지" 결정 정보 부족. |
| **Solution** | yfinance 단독으로 5 지수 + 3 선물 + 14 종목 + 4 거시 데이터 = 26 데이터 포인트를 1통의 슬랙 메시지에 담고, 단타 진입 후보를 5종 신호(🔥거래량 / 🎯갭 / ⚡VIX / 🆙신고가 / 📊시간외)로 자동 마크. AI/뉴스/외부 API 0, 비용 0. |
| **Function · UX · Effect** | 섹터 그룹화된 마크다운 메시지 + 메시지 끝에 "🚨 오늘 단타 후보" 자동 요약. 모닝브리핑 1개 열면 30초 안에 어떤 종목이 단타 후보인지 식별 가능. |
| **Core Value** | "**아침 슬랙 1통으로 오늘의 단타 진입 후보 자동 스크리닝**" — 사람 눈으로 20개 종목 챠트 일일이 안 봐도 신호가 발생한 종목만 자동 추출. |

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 단타(상한가 눌림목) 진입 후보를 매일 아침 자동 스크리닝. 정보량 부족한 Phase 1을 풍부화. |
| **WHO** | 단일 사용자(준), 단타/스윙 트레이더. 한국 시간 새벽 = 미장 마감 직후 정보 가장 가치 높음. |
| **RISK** | ① yfinance Ticker.info N+1 호출 지연 ② 시간외 데이터 종목별 정확도 차이 ③ 메시지 길이 Slack 4000자 한도 ④ 일부 ticker 일시 미반환 |
| **SUCCESS** | 26 데이터 포인트 정상 수신 / 단타 신호 5종 정확도 ≥ 95% / 메시지 ≤ 4000자 / 실행 ≤ 60초 / Phase 1 회귀 0 |
| **SCOPE** | yfinance 단독. AI/뉴스 = Phase 2, 한국 시장 = Phase 3, 실시간 = Phase 4 |

---

## 1. Overview

Phase 1(^IXIC + ^GSPC 종가 발송) 위에 **데이터 폭 + 단타 신호 마크**를 더한다. 같은 GitHub repo, 같은 main.py를 확장 (`build_message()` 시그니처는 Phase 1에서 이미 `extra_blocks` ready). 외부 API 추가 0, Secrets 추가 0, 운영비 변동 0.

**핵심 차별점**: 단타에 **직접 도움되는 신호**를 자동 마크하여, 트레이더가 종목 리스트를 일일이 스캔하지 않아도 "오늘 볼 종목"이 메시지 끝에 요약됨.

## 2. Background & Problem

### 2.1 Phase 1의 한계

Phase 1 메시지 (현재):
```
[2026-05-11 KST 06:00 발송] 직전 거래일: 2026-05-08
• 나스닥 ^IXIC: 26,247.08  ▲ +440.88 (+1.71%) 🟢
• S&P 500 ^GSPC: 5,432.10  ▲ +12.45 (+0.23%) 🟢
```

부족한 것:
- **지수**: 다우 빠짐. VIX(공포지수) 빠짐. 러셀2000(중소형주) 빠짐.
- **선물**: ES=F/NQ=F/YM=F — **한국 새벽엔 선물이 다음장 전망 1순위**인데 빠짐.
- **개별 종목**: 0개. 어떤 종목이 어제 움직였는지 모름.
- **시간외 거래**: 마감 후 호재/악재 반영. 다음날 갭 예고. 빠짐.
- **거시**: 환율, 원자재 빠짐. 한국 시장 영향 추론 불가.
- **단타 신호**: 거래량 이상, 갭, 신고가 등 정량 신호 0개.

### 2.2 단타(상한가 눌림목) 트레이딩 패턴 요구사항

준의 사용 시나리오: 매일 새벽 6시 슬랙 메시지로 미국 시장의 흐름을 30초 안에 파악 → "오늘 어떤 섹터/종목을 볼지" 결정.

이 패턴에서 가치 있는 신호:
- 거래량 이상 = 뉴스/이벤트 발생, 단타 후보 1순위
- 갭상승/하락 = 갭 채우기 매수 진입점 발생
- VIX 급등 = 변동성 ↑ = 눌림 매수 타점 빈도 ↑
- 52주 신고가 = 강세 추세, 추격 vs 단타 양면
- 시간외 추가 변동 = 다음장 갭 예고

→ Phase 1.5의 단타 신호 5종 = 위 5개 패턴을 자동 마크.

## 3. Goals & Non-Goals

### 3.1 Goals
- **G1.** 5 지수 + 3 선물 + 14 종목 + 4 거시 데이터 = **26 데이터 포인트**를 1개 슬랙 메시지에 담음
- **G2.** 단타 신호 **5종** 자동 마크 (🔥 / 🎯 / ⚡ / 🆙 / 📊)
- **G3.** 섹터 그룹화 (반도체 / 빅테크 / 자동차+암호 / 거시) + "🚨 오늘 단타 후보" 자동 요약
- **G4.** 메시지 길이 ≤ Slack 4,000자 한도
- **G5.** Phase 1 회귀 **0건** (기존 17 테스트 통과 유지)
- **G6.** 신규 단위/통합 테스트 **30+ 케이스** 추가

### 3.2 Non-Goals (이번 사이클에서 안 함)
- ❌ AI/뉴스 분석 (Phase 2)
- ❌ 한국 시장 통합 — KOSPI/KOSDAQ/원화 ETF (Phase 3)
- ❌ 차트 이미지 첨부 (Phase 3)
- ❌ 실시간 알림 — 5% 급등락 즉시 통지 (Phase 4)
- ❌ 멀티 채널 라우팅 (Phase 3)
- ❌ 자동 섹터 추론 — `Ticker.info['sector']` 사용 (사용자 결정: 수동 매핑만)

## 4. Requirements

### 4.1 Functional Requirements

| ID | 요구사항 | 비고 |
|---|---|---|
| FR-01 | INDICES 확장: ^IXIC, ^GSPC, **^DJI(다우), ^RUT(러셀2000), ^VIX(공포지수)** | 5개 |
| FR-02 | FUTURES 추가: **ES=F(S&P 미니), NQ=F(나스닥 미니), YM=F(다우 미니)** | 한국 새벽 다음장 전망 1순위 |
| FR-03 | STOCKS 추가: **NVDA, TSLA, MSFT, AAPL, AMZN, AVGO, INTC, MU, AMD, GOOGL, META, TSMC, ASML, COIN** | 11(빅테크/반도체) + 3(한국 ADR/암호) = 14 |
| FR-04 | MACRO 추가: **USDKRW=X(원/달러), CL=F(WTI), GC=F(금), BTC-USD(비트코인)** | 4개, 거시 흐름 |
| FR-05 | SECTOR_MAP 수동 매핑: 반도체 / 빅테크 / EV·자동차 / 암호화폐 / 지수 / 거시 | hard-coded dict |
| FR-06 | 단타 신호 자동 마크 — 5종 임계값 ||
| | 🔥 거래량 이상 | volume / vol_avg_20d ≥ **2.0** |
| | 🎯 갭 | (open - prev_close) / prev_close 절대값 ≥ **1.5%** |
| | ⚡ VIX 급등 | VIX 일중 변동 절대값 ≥ **5%** |
| | 🆙 52주 신고가 | last_close ≥ fiftyTwoWeekHigh × **0.99** |
| | 📊 시간외 변동 | after-hours pct 절대값 ≥ **1.0%** (데이터 있을 때만) |
| FR-07 | 사상최고 ★ 표시 | 종가 ≥ 52주 최고가 × 0.999 |
| FR-08 | 메시지 섹션 구조 (마크다운) ||
| | 헤더 | `[YYYY-MM-DD KST 06:00 발송] 직전 거래일: YYYY-MM-DD` |
| | 📈 [지수] | INDICES 5개 + ★ + ⚡ |
| | 🎯 [단타 핵심: 선물 + 시간외] | FUTURES 3개 + AHRS(시간외 변동 있는 종목만) |
| | 🏭 [반도체] | NVDA AVGO INTC MU AMD TSMC ASML 등 + 신호 마크 |
| | 📱 [빅테크] | AAPL MSFT GOOGL META AMZN |
| | 🚗 [EV / 암호] | TSLA COIN |
| | 💰 [거시] | USDKRW=X CL=F GC=F BTC-USD |
| | 🚨 [오늘 단타 후보] | 신호 2개 이상 발생한 종목 자동 요약 |
| FR-09 | "단타 후보" 자동 요약 — 신호 2개+ 발생 종목을 별도 섹션에 한 줄 요약 | 예: `INTC — 🎯+🔥 (갭+거래량)` |
| FR-10 | 휴장일 처리 — Phase 1과 동일, 모든 종목/거시에 일관 적용 | `is_stale` 그대로 |
| FR-11 | 일부 ticker 데이터 미반환 시 부분 실패 허용 — 다른 종목은 정상 발송, 누락은 ❓ 또는 skip | 운영 안정성 |

### 4.2 Non-Functional Requirements

| ID | 요구사항 | 측정 |
|---|---|---|
| NFR-01 | 메시지 길이 | ≤ 4,000 chars (Slack hard limit) |
| NFR-02 | 단일 실행 시간 | ≤ 60초 (26 ticker 호출 고려, Phase 1의 30초에서 완화) |
| NFR-03 | Secrets 노출 | 0건 (Phase 1 동일) |
| NFR-04 | 의존성 추가 | 0개 (yfinance, requests 그대로) |
| NFR-05 | Phase 1 회귀 | 0건 (기존 17 테스트 통과 유지) |
| NFR-06 | 신규 테스트 | 30+ 케이스 (단위 + 통합) |
| NFR-07 | Phase 2 확장성 유지 | `build_message(quotes, extra_blocks=...)` 시그니처 보존 |
| NFR-08 | 메시지 가독성 | 섹터 그룹화 + 신호 시각 마크 + 한국어 라벨 |

## 5. User Stories & Acceptance Criteria

### US-1. 30초 모닝브리핑
> *준으로서, 매일 아침 슬랙 메시지 1통을 30초 안에 훑어보고 "오늘 어떤 종목/섹터를 볼지" 결정하고 싶다.*

**AC:**
- ✅ 메시지에 26 데이터 포인트가 섹터별로 그룹화돼 있다
- ✅ 단타 후보가 메시지 끝 별도 섹션에 자동 요약된다
- ✅ 신호 발생 종목은 시각 마크로 즉시 식별 가능하다

### US-2. 다음장 갭 사전 인지
> *한국 새벽 시점에 미국 선물 + 시간외 흐름으로 다음 장 갭을 사전에 예측하고 싶다.*

**AC:**
- ✅ ES=F / NQ=F / YM=F 선물 변동률이 메시지에 포함된다
- ✅ 시간외 1% 이상 변동 종목은 📊 마크로 표시된다

### US-3. 거래량 이상 종목 자동 발견
> *수십 종목 차트를 일일이 안 봐도 거래량 급증 종목이 자동으로 알림 오기를 원한다.*

**AC:**
- ✅ 거래량이 20일 평균의 2배 이상인 종목은 🔥 마크
- ✅ 단타 후보 섹션에 자동 포함

### US-4. 회귀 안전성
> *Phase 1 기능은 그대로 동작해야 한다. 새 기능 때문에 기존 메시지가 망가지면 안 된다.*

**AC:**
- ✅ 기존 17 테스트 모두 통과
- ✅ Phase 1 메시지(^IXIC + ^GSPC) 정확도 100% 유지
- ✅ `build_message(quotes)` (extra_blocks=None) 호출 시 Phase 1 동작과 동일

## 6. Success Criteria (Measurable)

| ID | 지표 | 목표 | 측정 방식 |
|---|---|---|---|
| SC-1.5-1 | 26 데이터 포인트 수신 | 100% (5+3+14+4) | 통합 테스트로 yfinance 호출 결과 검증 |
| SC-1.5-2 | 단타 신호 5종 정확도 | ≥ 95% (단위 테스트) | 알려진 입력 → 예상 마크 출력 일치 |
| SC-1.5-3 | 사상최고 ★ 정확도 | 100% (boundary 포함) | 52주 최고가 ±0.5% 케이스 단위 테스트 |
| SC-1.5-4 | "단타 후보" 자동 요약 동작 | 100% | 신호 ≥2개 종목이 요약 섹션에 포함되는지 |
| SC-1.5-5 | 메시지 길이 ≤ 4,000자 | 100% | 통합 테스트로 실측 |
| SC-1.5-6 | Phase 1 회귀 | 0건 | 기존 17 테스트 통과 |
| SC-1.5-7 | 단일 실행 시간 | ≤ 60초 | GitHub Actions log timestamp 분석 |
| SC-1.5-8 | 신규 테스트 | ≥ 30 케이스 | `pytest --collect-only \| wc -l` |

## 7. Constraints & Assumptions

### 7.1 Constraints
- **C-1.** yfinance만 사용 (외부 API/Secret 추가 X)
- **C-2.** 1일 1회 KST 06:00 발송 (Phase 1과 동일)
- **C-3.** 같은 GitHub repo, 같은 main.py 확장 (별도 repo X)
- **C-4.** Slack 단일 메시지 4,000자 한도
- **C-5.** 의존성 추가 없음 (yfinance, requests만)

### 7.2 Assumptions
- **A-1.** 14 개별 종목 + 11 지수/선물/거시 = 25 ticker 호출이 60초 내 가능
- **A-2.** yfinance `Ticker.history(period="1mo")` 한 번 호출이면 거래량 평균 계산 가능
- **A-3.** `Ticker.info['fiftyTwoWeekHigh']` 호출 비용 감수 (대안: history에서 max 계산)
- **A-4.** 시간외(`prepost=True`) 데이터는 종목별로 누락 가능 — fault-tolerant
- **A-5.** 섹터 매핑은 hard-coded — 신규 종목 추가 시 dict 업데이트 필요

## 8. Risks & Mitigations

| ID | 위험 | 영향 | 확률 | 대응 |
|---|---|---|---|---|
| R-1 | yfinance N+1 호출 지연 (25 ticker × 1초+) | NFR-02 미달 | 중 | `yf.Tickers([...])` 일괄 호출 또는 `concurrent.futures.ThreadPoolExecutor`로 병렬화 (Design 단계 결정) |
| R-2 | 시간외 데이터 종목별 정확도 | 📊 마크 부정확 | 중 | 데이터 없으면 mark 생략, "AHRS 데이터 없음" 별도 처리 |
| R-3 | 메시지 길이 4,000 초과 | NFR-01 미달 | 중 | 종목 수 제한 또는 신호 없는 종목은 압축 1줄 |
| R-4 | 일부 ticker 일시 미반환 (Yahoo glitch) | 부분 데이터 누락 | 중 | 부분 실패 허용. 누락 종목은 `❓` 표시, 다른 종목 정상 발송 |
| R-5 | 사상최고 boundary (last_close = 52w high × 0.999) | ★ 표시 부정확 | 저 | 명확한 임계값 + 단위 테스트로 boundary 검증 |
| R-6 | 기존 Phase 1 메시지 깨짐 (회귀) | NFR-05 미달 | 저 | `build_message(quotes)` (extra_blocks=None) 동일성 단위 테스트 추가 |
| R-7 | 한국 ADR 종목 데이터 부정확 (TSMC/ASML/COIN) | 일부 종목 누락 | 저 | 통합 테스트 시 검증, 문제 시 STOCKS에서 제외 |

## 9. Out of Scope (Phase 2+)

(상위 morning-us-index Plan §9 참조)
- **Phase 2** — AI 분석 + 뉴스 헤드라인 (`/pdca pm morning-us-index-ai`)
- **Phase 3** — 한국 시장 통합 + 멀티 채널 + 차트 이미지
- **Phase 4** — Self-hosted runner, 실시간 알림, 도착률 자동 측정

## 10. Roadmap & Milestones

| 마일스톤 | 산출물 | DoD |
|---|---|---|
| M1 — Plan ✅ | 본 문서 | 4 Checkpoint 통과, 사용자 승인 |
| M2 — Design | `docs/02-design/features/morning-us-index-v15.design.md` | 3 옵션 비교 + 모듈 맵 + 메시지 mockup + 테스트 플랜 |
| M3 — Do | 코드 확장 + 30+ 테스트 | 로컬 `python main.py` 정상 메시지 출력 |
| M4 — Check | analysis.md | Match Rate ≥ 90% |
| M5 — Iter | (필요 시) | 100% 도달 |
| M6 — Deploy | git push + workflow_dispatch | 슬랙 도착, 메시지 검증 |
| M7 — Report | report.md | Phase 1.5 종료 + Phase 2 안내 |

## 11. Open Questions

| ID | 질문 | 결정 시점 |
|---|---|---|
| OQ-1 | 메시지 4,000자 초과 시 정책 (신호 없는 종목 압축 vs 다중 메시지) | Design |
| OQ-2 | yfinance 호출 전략 (`yf.Tickers` 일괄 vs ThreadPoolExecutor 병렬) | Design |
| OQ-3 | `Ticker.info` 사용 여부 (느림) vs `history`에서 자체 계산 | Design |
| OQ-4 | "단타 후보" 요약에 포함될 최소 신호 수 (1 vs 2) | Design |
| OQ-5 | 시간외 데이터 정확도 — 검증 후 종목별 신뢰도 다르면 일부만 사용 | Do |

## 12. References

- Phase 1 Plan: `docs/01-plan/features/morning-us-index.plan.md`
- Phase 1 Design: `docs/02-design/features/morning-us-index.design.md`
- Phase 1 Analysis: `docs/03-analysis/morning-us-index.analysis.md`
- 사용자 요구 형태: `prompt/slack_output.md`
- yfinance Tickers: https://github.com/ranaroussi/yfinance
- yfinance Ticker.info / history(prepost=True): https://ranaroussi.github.io/yfinance/

---

**다음 단계**: `/pdca design morning-us-index-v15`
