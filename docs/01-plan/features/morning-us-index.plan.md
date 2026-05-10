---
name: morning-us-index
type: plan
version: 0.1.0
status: draft
phase: plan
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
prd: null
---

# Plan — morning-us-index (미국 증시 모닝 브리핑 자동화)

## Executive Summary

| 관점 | 한 줄 요약 |
|---|---|
| **Problem** | 매일 아침 미 증시 종가를 일일이 확인해야 하고, 노트북이 꺼진 새벽 시간대에는 자동화도 안 된다. |
| **Solution** | GitHub Actions cron으로 매일 KST 06:00 ^IXIC·^GSPC 종가/변동률을 yfinance로 가져와 Slack Webhook으로 발송. 컴퓨터 전원과 무관하게 항상 동작. |
| **Function · UX · Effect** | 슬랙 1개 채널에 지수명/종가/전일대비 변동률(%) + 상승🟢/하락🔴 이모지가 붙은 메시지가 매일 자동 도착. 사용자는 슬랙만 열면 어제 미 증시 결과를 즉시 파악. |
| **Core Value** | "장 마감을 잠자다 놓쳐도, 아침에 슬랙 알림 1개로 끝난다" — 시간 지연 없는 글로벌 시장 모니터링의 자동화된 1차 인덱스. |

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 컴퓨터를 꺼도 항상 동작하는 미 증시 일일 종가 알림이 필요. (Phase 1은 숫자만, AI/뉴스 분석은 Phase 2로 분리) |
| **WHO** | 단일 사용자(준). 본인 슬랙 워크스페이스 1개 채널 수신. |
| **RISK** | ① yfinance 데이터 지연/장애 ② GitHub Actions cron 5–15분 jitter ③ 미 증시 휴장일 처리 누락 ④ Webhook URL 노출 |
| **SUCCESS** | 평일 KST 06:00±30분 슬랙 도착률 ≥ 95%, 종가/변동률 정확도 100%, Secrets 노출 0건. |
| **SCOPE** | Phase 1: 지수 2종 → 슬랙. Phase 2(별도 PDCA): 뉴스 수집 + AI 브리핑. |

---

## 1. Overview

매일 한국 시간 오전 6시, 직전 미 증시 거래일의 **나스닥 종합지수(^IXIC)** 와 **S&P 500(^GSPC)** 종가/변동률을 슬랙 채널 1곳으로 자동 발송하는 서버리스 자동화 시스템.

핵심은 **사용자의 로컬 머신과 무관하게 동작**해야 한다는 점이며, 이를 위해 GitHub Actions의 schedule trigger를 사용한다. AI 분석·뉴스 수집은 본 Plan 범위에서 제외하고 Phase 2(별도 feature)로 분리한다.

## 2. Background & Problem

### 2.1 현재 상황
- 사용자는 매일 아침 미 증시 결과를 yfinance·Investing.com·블룸버그 등에서 수동으로 확인.
- 노트북을 끄고 자는 시간(KST 0–7시)에 미 증시 마감(NY 16:00 ET ≈ KST 05–06시)이 일어나, 로컬 cron으로는 자동화 불가.
- 기존 슬랙 봇 서비스는 유료이거나 표시 형식 커스터마이즈가 약함.

### 2.2 문제 정의
| Pain | 빈도 | 비용 |
|---|---|---|
| 마감 직후 종가 확인 누락 | 거의 매일 | 시장 흐름 파악 지연 |
| 로컬 cron이 컴퓨터 꺼지면 동작 안 함 | 주 3–4회 | 자동화 신뢰성 0 |
| 휴장일/공휴일 구분 없는 알림 | 주 2회 | 노이즈, 불신 |

## 3. Goals & Non-Goals

### 3.1 Goals (Phase 1)
- **G1.** 컴퓨터 전원 상태와 무관하게 매일 KST 06:00 자동 발송.
- **G2.** ^IXIC, ^GSPC의 직전 거래일 종가 + 전일대비 변동률(%) 정확 표기.
- **G3.** 휴장일/공휴일에는 "(휴장 / N일 기준 마지막 거래일)" 표기로 마지막 거래일 데이터 발송.
- **G4.** Webhook·API Key 등 비밀값은 GitHub Secrets로만 주입 (.env 또는 코드 하드코딩 금지).
- **G5.** 사용자가 README만 보고 30분 이내에 fork → repo 생성 → Secrets 등록 → 첫 메시지 수신까지 완료.

### 3.2 Non-Goals (Phase 1 제외)
- ❌ AI(Gemini/Claude) 기반 시장 해설 ← Phase 2
- ❌ 뉴스 헤드라인 수집(MCP/web search/News API) ← Phase 2
- ❌ 다우(^DJI), 러셀(^RUT), 섹터 ETF, VIX, 환율 등 추가 지표 ← Phase 2 후보
- ❌ 한국 증시(KOSPI/KOSDAQ) 통합 ← 별도 feature
- ❌ 사용자 멀티테넌트(여러 사용자/채널 라우팅) ← 단일 사용자 가정

## 4. Requirements

### 4.1 Functional Requirements

| ID | 요구사항 | 비고 |
|---|---|---|
| FR-01 | yfinance로 ^IXIC, ^GSPC의 최근 2거래일 일봉 데이터 조회 | `Ticker.history(period="5d")` 후 마지막 2행 사용(주말 안전 마진) |
| FR-02 | 직전 거래일 종가, 그 이전 거래일 종가로 변동률(%) 계산 | `(close_t - close_t-1) / close_t-1 * 100`, 소수점 2자리 반올림 |
| FR-03 | 변동률 양수면 🟢 + ▲, 음수면 🔴 + ▼, 0%면 ⚪ + ■ 이모지 부착 | 메시지 시각 구분 |
| FR-04 | 슬랙 메시지 형식 (Design §4.3 양식 준수): `[YYYY-MM-DD KST 06:00 발송] 직전 거래일: YYYY-MM-DD\n• 나스닥 ^IXIC: 17,234.50  ▲ +145.32 (+0.85%) 🟢\n• S&P 500 ^GSPC: 5,432.10  ▼ -12.45 (-0.23%) 🔴` | plain markdown text (Block Kit 미사용 — Design §3.1 결정) |
| FR-05 | Slack Incoming Webhook으로 POST 발송 | 환경변수 `SLACK_WEBHOOK_URL` |
| FR-06 | 직전 거래일이 발송 시점 기준 2일 이상 과거이면 헤더에 "(미 증시 휴장 / 마지막 거래일)" 부가 (마지막 거래일 자체는 헤더에 이미 표기됨, Design §4.3) | 토·일·미 공휴일 |
| FR-07 | yfinance 호출/슬랙 POST 실패 시 1차 재시도(지수 백오프 30s, 60s, 120s, 최대 3회) | 일시 장애 흡수 |
| FR-08 | 모든 재시도 실패 시 슬랙으로 에러 알림 발송(가능하면) + GitHub Actions 작업을 fail로 처리 | 무음 실패 방지 |
| FR-09 | GitHub Actions: cron `'0 21 * * *'` (UTC 21:00 = KST 06:00) | schedule + workflow_dispatch 둘 다 지원 |
| FR-10 | `workflow_dispatch`로 수동 실행 가능 | 디버깅·즉시 검증용 |

### 4.2 Non-Functional Requirements

| ID | 요구사항 | 측정 |
|---|---|---|
| NFR-01 | 슬랙 메시지 도착률 | 평일 30일 기준 ≥ 95% (Action delay 고려) |
| NFR-02 | 단일 실행 소요시간 | ≤ 60초 |
| NFR-03 | Secrets 노출 0건 | git log에 `SLACK_WEBHOOK_URL` 평문 0회 |
| NFR-04 | 의존성 최소화 | Phase 1 패키지 ≤ 5개 (yfinance, requests, pandas는 yfinance가 끌어옴) |
| NFR-05 | 메시지 가독성 | 이모지·숫자 정렬·천단위 콤마 표기 |
| NFR-06 | Phase 2 확장성 | `build_message(data)` 함수가 분리되어 있어 AI/뉴스 모듈을 끼워 넣기 가능 |

## 5. User Stories & Acceptance Criteria

### US-1. 슬리퍼 트레이더 모닝 알림
> *준으로서, 컴퓨터를 꺼두고 자도 매일 아침 슬랙으로 어제 미 증시 결과를 받고 싶다. 그래야 출근 전에 시장 톤을 파악할 수 있다.*

**AC:**
- ✅ 평일 KST 06:00 ± 30분에 슬랙 메시지가 도착한다.
- ✅ 메시지에 ^IXIC, ^GSPC 종가와 전일대비 변동률(%)이 포함된다.
- ✅ 상승은 🟢, 하락은 🔴로 한 눈에 구분된다.

### US-2. 휴장일 노이즈 제거
> *주말이나 미 공휴일에도 알림이 와도 좋지만, 그게 어제 데이터인지 헷갈리지 않게 분명히 표시되길 원한다.*

**AC:**
- ✅ 토·일 또는 미 공휴일 다음 날에는 메시지에 `(미 증시 휴장 / 마지막 거래일: YYYY-MM-DD)` 텍스트가 부가된다.
- ✅ 마지막 거래일의 종가/변동률을 그대로 표시한다(중복 발송 안내는 메시지로만).

### US-3. 비용/관리 부담 0
> *서비스 가입·결제·서버 관리 없이 무료로 1년 이상 운영하고 싶다.*

**AC:**
- ✅ GitHub 무료 플랜 + Slack 무료 플랜으로 1회 발송당 비용 0.
- ✅ 한 달 GitHub Actions 사용량이 무료 한도(public 무제한 / private 2,000분) 1% 미만.

## 6. Success Criteria (Measurable)

| ID | 지표 | 목표 | 측정 방식 |
|---|---|---|---|
| SC-1 | 평일 30일 슬랙 도착률 | ≥ 95% (28/30일 이상) | 슬랙 채널 메시지 카운트 |
| SC-2 | 종가/변동률 정확도 | 3일치 수기 검증 100% 일치 | Yahoo Finance 웹과 대조 |
| SC-3 | 휴장일 표기 정확도 | 휴장 다음 날 100% 표시 | 토/일/공휴일 후 메시지 확인 |
| SC-4 | Secrets 노출 | git log에 0건 | `git log -p \| grep -i webhook` |
| SC-5 | 신규 사용자 셋업 시간 | README 따라 ≤ 30분 | 스톱워치 측정 |
| SC-6 | 실패 알림 동작 | 의도적 실패 1회 시 슬랙 에러 메시지 도착 | 잘못된 ticker로 1회 테스트 |

## 7. Constraints & Assumptions

### 7.1 제약
- **C-1.** GitHub Actions schedule cron은 5–15분 정도 지연될 수 있음(특히 정시·매시간대). KST 06:00 정각 보장 ✗ → 06:30 이내면 OK.
- **C-2.** yfinance는 Yahoo Finance 비공식 스크래핑 기반이라 서비스 측 변경 시 장애 발생 가능. 대체 라이브러리: `yahoo-finance2`(Node), `pandas-datareader`, 유료 API.
- **C-3.** Slack Incoming Webhook은 채널 1개에 고정. 다채널 라우팅은 Phase 3+.
- **C-4.** 미 동부시간: EDT(서머타임 3월–11월) UTC-4 / EST(표준시 11월–3월) UTC-5. KST 06:00 = UTC 21:00 = NY 17:00(EDT) / NY 16:00(EST). 마감 직후라 일부 데이터 지연 가능 → `period="5d"` 사용해 확정된 직전 거래일 데이터를 안정적으로 확보.

### 7.2 가정
- **A-1.** 사용자는 GitHub 계정과 Slack 워크스페이스를 이미 보유.
- **A-2.** Slack 워크스페이스에 Incoming Webhook 앱 생성 권한이 있다.
- **A-3.** 인터넷 연결과 Yahoo Finance 접근이 가능한 GitHub Actions runner 환경.

## 8. Risks & Mitigations

| ID | 위험 | 영향 | 확률 | 대응 |
|---|---|---|---|---|
| R-1 | yfinance 일시 장애(Yahoo 측 변경) | 메시지 누락 | 중 | 3회 지수 백오프 재시도 → 실패 시 슬랙 에러 알림 + Action fail (이메일 자동 통지) |
| R-2 | GitHub Actions cron 지연(>30분) | NFR-01 미달 | 중 | README에 한도 명시. KST 06:00 ± 30분 윈도우를 SLA로 합의. 심각하면 self-hosted runner 검토(Phase 3) |
| R-3 | Webhook URL 유출 | 외부 메시지 스팸 | 저 | Secrets만 사용, .gitignore 강화, 유출 시 Slack에서 webhook regenerate |
| R-4 | 환율·서머타임 전환일 미 증시 마감 시점 변동 | KST 06:00 시점에 직전 거래일 데이터가 아직 없음 | 중 | `period="5d"` 사용 → 항상 *확정된* 직전 거래일을 인덱싱. 마감 직후 데이터 누락 영향 차단 |
| R-5 | 사용자가 Phase 2 확장 시 main.py 구조 모호 | 리팩터링 비용 | 중 | NFR-06: `fetch_indices()`, `build_message()`, `post_slack()` 3개 함수로 명확 분리 |
| R-6 | 무료 GitHub Actions 한도 초과(repo가 private + 다른 워크플로우 추가) | 결제 발생 | 저 | README에 "월 ~30분 사용" 명시. private 2,000분 한도의 ~1.5% |

## 9. Out of Scope (Phase 2+)

> Phase 2부터는 별도 feature로 PDCA를 다시 돌린다(`/pdca pm morning-us-index-ai`, `/pdca plan ...`).

- **Phase 2 (AI 분석)**: 뉴스 헤드라인 수집(NewsAPI / RSS / Gemini Grounding / Claude web_search) + Gemini API 또는 Claude API로 "왜 시장이 이렇게 움직였는지" 한국어 브리핑 생성. Secrets 추가: `GEMINI_API_KEY` 또는 `ANTHROPIC_API_KEY`.
- **Phase 3 (확장)**: Dow/Russell/VIX/주요 ETF/환율, 한국 증시 통합, 멀티 채널, 차트 이미지 첨부.
- **Phase 4 (운영)**: Self-hosted runner로 cron 정확도 향상, 실패 알림 PagerDuty/Discord 라우팅.

## 10. Roadmap & Milestones

| 마일스톤 | 산출물 | 완료 정의 |
|---|---|---|
| M1 — Design | `docs/02-design/features/morning-us-index.design.md` | 모듈 구조, 데이터 흐름, 메시지 포맷 샘플, 세션 가이드 확정 |
| M2 — Local Do | `main.py`, `requirements.txt` | 로컬에서 `python main.py` 실행 시 슬랙으로 메시지 1개 도착 |
| M3 — GitHub Actions Do | `.github/workflows/daily_report.yml`, README 1차 | `workflow_dispatch` 수동 실행 시 슬랙 도착 |
| M4 — Cron 안정화 | 평일 7일 연속 자동 실행 로그 | 도착률 ≥ 95% 확인 |
| M5 — Check & Report | analysis + report | Match Rate ≥ 90%, SC-1~SC-6 평가 |
| M6 (Optional) — Phase 2 분리 | 새 feature 시작 | `/pdca pm morning-us-index-ai` 호출 |

## 11. Open Questions

| ID | 질문 | 결정 필요 시점 |
|---|---|---|
| OQ-1 | 슬랙 채널명/멘션(@here, @channel 등) 사용? | Design 단계 |
| OQ-2 | 메시지 언어: 100% 한국어 vs 지수명 영문 유지? (현재 가정: 영문 ticker + 한글 라벨 혼용) | Design 단계 |
| OQ-3 | 한국 공휴일에도 발송할지(KST 06:00 한국 공휴일이라도 미 증시 데이터는 의미 있음 — **현재 안: 그대로 발송**) | Design 단계 |
| OQ-4 | 시간을 KST 06:00 vs 07:00로 할지(EST 시즌 데이터 안정성 위해 07:00이 더 안전) | Design 단계 |
| OQ-5 | Repo 이름/visibility(public 권장 — Actions 무제한) | Design 단계 |

## 12. References

- yfinance: https://github.com/ranaroussi/yfinance
- Slack Incoming Webhooks: https://api.slack.com/messaging/webhooks
- GitHub Actions schedule events: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- NYSE/NASDAQ market hours & holidays: https://www.nyse.com/markets/hours-calendars

---

**다음 단계**: `/pdca design morning-us-index`
