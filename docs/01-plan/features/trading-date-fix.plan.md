---
name: trading-date-fix
type: plan
version: 0.1.1
status: draft
phase: plan
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
builds_on: morning-us-index-noai-v2 (운영 중) + slack-mobile-preview (이 사이클로 발견)
prd: null
related_pain_point: "직전 거래일: 2026-05-11 (미 증시 휴장)" 모순 표시 — today가 직전 거래일?
discovered_by: slack-mobile-preview actions-log mode 시각 검증 (run-id 25649430993, 2026-05-11)
---

# Plan — trading-date-fix (헤더 직전 거래일 모순 표시 해소)

## Executive Summary

| 관점 | 한 줄 요약 |
|---|---|
| **Problem** | 슬랙 메시지 헤더 "직전 거래일: YYYY-MM-DD (미 증시 휴장)"의 날짜가 **today**를 가리켜 사용자 인지 부조화. 원인: `max(q.last_date for q in quotes)`가 24-7 자산(future/macro)의 today 날짜를 반환. |
| **Solution** | 본 시장 캘린더 기준 자산(`category ∈ {'index', 'stock'}`)만으로 `last_trading_date` 계산. helper 함수 `_resolve_last_trading_date(quotes)` 추출하여 main.py:149 + main.py:635 두 곳 일괄 적용. |
| **Function · UX · Effect** | 휴장일 메시지가 정확히 본 시장 마지막 거래일(예: 5/8 금) 표시 → "오늘이 직전 거래일이라니?" 인지 부조화 0. 정상 거래일은 그대로 today/yesterday 표시 유지. |
| **Core Value** | "**메시지 신뢰도 회복**" — 한 줄 모순으로 흔들렸던 헤더 신뢰성을 정확한 날짜 1개로 복원. slack-mobile-preview 도구의 첫 실증 산출물. |

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 2026-05-11 KST 06:00 발송 메시지에서 "직전 거래일: 2026-05-11 (미 증시 휴장)" 모순 표시 발견 (slack-mobile-preview 도구로). 사용자 인지 부조화: 오늘이 어떻게 직전 거래일? |
| **WHO** | 준 (메시지 수신자). 매 발송 헤더를 신뢰해야 의사결정 가능 |
| **RISK** | 매우 낮음 — helper 함수 1개 신규 + 2곳 1줄씩 교체. 회귀 영향 최소. main.py:149(Phase 1.5)/main.py:635(build_v15_message) 모두 단순 표현식 교체 |
| **SUCCESS** | 휴장일 헤더 "직전 거래일: {본 시장 마지막 거래일}" 정확 표시 / 정상 거래일 회귀 0 / 119+3 = 122 단위 통과 / 다음 휴장일 발송에서 모순 0건 |
| **SCOPE** | main.py 2곳 + config.py 상수 1개 + tests/test_main.py 3 케이스 추가. news.py / signals.py / data.py 변경 0 |

---

## 1. Overview

slack-mobile-preview 도구로 actions-log 모드 시각 검증 중 발견된 헤더 표시 버그 1건 해소. 도구의 첫 가치 실증 산출물 — v5~v10 시대에는 준에게 폰 스크린샷 요청해야만 발견 가능했을 모순을 Ally가 멀티모달로 직접 식별.

**핵심 차별점**: 작은 변경(1 helper + 2 호출처 + 1 상수 + 3 테스트). 회귀 위험 매우 낮음. SC-MP-7(사용자 스크린샷 요청 0회) 패턴 유지.

## 2. Background & Problem

### 2.1 발견 경위

| 시점 | 사건 |
|---|---|
| 2026-05-11 03:55 KST | `gh workflow run daily_report.yml` (run-id 25649430993) — 슬랙 발송 |
| 2026-05-11 03:55+α | `python scripts/preview_mobile.py --source actions-log --run-id 25649430993` — Ally가 PNG 시각 분석 |
| 같은 분 | 헤더 "직전 거래일: **2026-05-11** (미 증시 휴장)" 모순 발견 |
| 사용자 반응 | "오늘은 휴장이라니...먼말이야?" |

### 2.2 원인 분석

`main.py:149`, `main.py:635`:
```python
last_trading_date = max(q.last_date for q in quotes)
any_stale         = any(q.is_stale for q in quotes)
```

| 자산 카테고리 | last_date (2026-05-11 KST 06:00 시점) | is_stale |
|---|---|---|
| **index** (나스닥/S&P/다우/VIX) | 2026-05-08 (금, 마지막 거래일) | True ⚠️ |
| **stock** (NVDA/MU/AMD 등) | 2026-05-08 (금) | True ⚠️ |
| **future** (야간 선물 — 24-5 거래) | 2026-05-11 (today) | False |
| **macro** (forex — 24-5 거래) | 2026-05-11 (today) | False |

→ `max(...)` 가 future/macro의 today 반환
→ `any(...)` 가 True (index/stock stale)
→ 헤더에 동시에 "직전 거래일: 2026-05-11" + "(미 증시 휴장)" — 모순

### 2.3 슬랙 모바일에서 본 모습

```
📅 2026-05-11 KST 06:00
직전 거래일: 2026-05-11 (미 증시 휴장)   ← today와 같음
📊 상승 11 / 하락 3 / VIX 17.19 (안정)
```

## 3. Goals & Non-Goals

### 3.1 Goals

- **G1.** 휴장일 헤더에 본 시장 마지막 거래일(예: 5/8) 정확히 표시
- **G2.** 정상 거래일 헤더 회귀 0 (기존 표시 유지)
- **G3.** main.py 동일 로직 2곳을 helper 함수 1개로 통합 (DRY)
- **G4.** `category ∈ {'index', 'stock'}` 기준을 config.py 상수로 추출
- **G5.** L1 테스트 3 케이스 추가 (정상거래일/주말혼합/모두stale)

### 3.2 Non-Goals (이번 사이클에서 안 함)

- ❌ 헤더 텍스트 포맷 자체 변경 (사용자가 거절: "직전 거래일: 5/8 (미 증시 휴장)" 그대로 유지)
- ❌ 24-7 자산 last_date를 별도 헤더 라인으로 분리 표시 (Non-Goal)
- ❌ STALE_THRESHOLD_DAYS 값 변경 (현재 2일 유지)
- ❌ data.py / news.py / signals.py 변경 (이번 사이클 범위 외)
- ❌ slack 채널 데이터 마이그레이션 / 과거 메시지 retroactive 수정

## 4. Requirements

### 4.1 Functional Requirements

| ID | 요구사항 | 비고 |
|---|---|---|
| **FR-01** | helper 함수 `_resolve_last_trading_date(quotes) -> date` | main.py 안 신규. `category in TRADING_DAY_CATEGORIES`만으로 max(last_date). 비어 있으면 fallback. |
| **FR-02** | `TRADING_DAY_CATEGORIES = ('index', 'stock')` config.py 신규 상수 | 의미 명확화 + 향후 확장 시 한 곳에서 수정 |
| **FR-03** (v0.1.1 정정) | main.py:149 (Phase 1 build_message) — **helper 미적용** | IndexQuote(category 필드 없음) 받음 → AttributeError. 본 시장 자산만 받아 모순 발생 불가. 기존 `max(...)` 유지 + IndexQuote/Quote 차이 주석 추가 |
| **FR-04** | main.py:635 (build_v15_message) — `max(...)` → `_resolve_last_trading_date(quotes)` | Quote 받는 유일한 위치. helper 호출처 = **1곳** (v0.1.0 명시 2곳에서 정정) |
| **FR-05** | fallback: `category in TRADING_DAY_CATEGORIES` 자산이 0개일 때 기존 `max(q.last_date for q in quotes)` 동작 보존 | edge case (e.g. 테스트 fixture에 future만) |

### 4.2 Non-Functional Requirements

| ID | 요구사항 | 측정 |
|---|---|---|
| NFR-01 | 메시지 빌드 시간 영향 0 | helper 함수가 단순 리스트 컴프리헨션, O(n) 그대로 |
| NFR-02 | 변경 라인 수 | ≤ 30 (helper 신규 5 + 상수 1 + 호출처 2 + 테스트 3) |
| NFR-03 | 기존 119 테스트 회귀 0 | pytest |
| NFR-04 | 신규 L1 테스트 ≥ 3 | (a) 정상거래일 / (b) 주말혼합 / (c) 모두stale |
| NFR-05 | 도구 사이클(slack-mobile-preview) 영향 0 | preview_mobile.py 변경 0 |
| NFR-06 | 운영 영향 (.github/workflows/) | 0 — 코드 변경만 |

## 5. User Stories & Acceptance Criteria

### US-1. 휴장일에도 헤더가 모순 없이 보임

> *준으로서, 주말이나 미국 휴일 다음 발송 메시지를 받았을 때 "직전 거래일"이 명확한 과거 날짜(예: 5/8 금)로 표시되어 정보가 깨지지 않게 보고 싶다.*

**AC:**
- ✅ KST 06:00 발송 시 모든 본 시장 자산(index+stock)이 stale → "직전 거래일: {본 시장 자산 last_date의 max} (미 증시 휴장)"
- ✅ 표시된 날짜는 항상 today보다 과거
- ✅ slack-mobile-preview 도구로 본 시점에 모순 자국 0

### US-2. 정상 거래일에 회귀 없음

> *평일에는 기존과 동일하게 today/yesterday 표시 그대로.*

**AC:**
- ✅ 모든 자산 fresh → `any_stale=False` → 기존 그대로 "직전 거래일: {today or 1day ago}" 표시
- ✅ 기존 110 + 119 단위 테스트 회귀 0

### US-3. 향후 카테고리 확장 시 한 곳 수정

> *나중에 ETF 같은 본 시장 시간대 자산 카테고리 추가될 때 `TRADING_DAY_CATEGORIES`만 갱신하면 즉시 반영.*

**AC:**
- ✅ config.py에 명시 상수 존재
- ✅ helper 함수가 이 상수만 참조

## 6. Success Criteria (Measurable)

| ID | 지표 | 목표 | 측정 방식 |
|---|---|---|---|
| SC-TD-1 | 휴장일 헤더 모순 표시 0건 | 0건 (다음 휴장일 발송) | actions-log mode PNG 시각 검증 |
| SC-TD-2 | 정상 거래일 회귀 0 | 0건 | pytest tests/test_main.py |
| SC-TD-3 | 신규 L1 테스트 통과 | 3/3 | pytest |
| SC-TD-4 | 전체 단위 통과 수 | 119 → **122** | pytest -m "not integration" |
| SC-TD-5 | 변경 라인 수 (핵심 코드만, docstring/주석/테스트 별도) | ≤ 30 | git diff --stat 분석 시 helper 본문 + 호출 교체 + import + 상수 합산 |
| SC-TD-6 | main.py 외 파일 변경 0 (config.py + tests/ 제외) | 0 | git diff --name-only |

## 7. Constraints & Assumptions

### 7.1 Constraints

- **C-1.** Quote dataclass의 category 타입은 `Literal["index", "future", "stock", "macro"]` 고정 — 이 4종 외 추가 시 본 Plan 무효
- **C-2.** main.py 외 last_trading_date 계산 위치 영향도 전수 검색 결과 0건 (Plan 작성 시 grep 확인됨)
- **C-3.** helper 함수는 main.py 안에 두기 (별도 모듈 분리 X — over-engineering 회피)

### 7.2 Assumptions

- **A-1.** future/macro 자산이 항상 본 시장보다 fresh — 검증됨 (2026-05-11 사례)
- **A-2.** 모든 본 시장 자산은 동일 거래일을 가짐 (예: NVDA 5/8 = S&P 500 5/8) — yfinance 동작 보장
- **A-3.** `category in ('index', 'stock')` 자산이 비어 있는 fixture는 운영에 없음 (fallback은 안전망 용도)

## 8. Risks & Mitigations

| ID | 위험 | 영향 | 확률 | 대응 |
|---|---|---|---|---|
| **R-1** | future/macro 카테고리 자산만 있는 fixture → helper에서 빈 리스트 | helper crash | 저 | fallback: `max(q.last_date for q in quotes)` 사용 |
| **R-2** | 향후 새 카테고리(예: 'crypto') 추가 시 누락 | 모순 재발 | 중 | `TRADING_DAY_CATEGORIES` 상수 + 주석으로 추가 시 본 Plan 참조 |
| **R-3** | yfinance가 stock의 last_date를 시간외(after-hours)로 today 마킹 | 모순 재발 | 저 | yfinance 1d daily 기준이라 발생 가능성 낮음. 발견 시 R-2와 동일 처리 |
| **R-4** | 시뮬 PNG와 실 슬랙 모바일이 미세 다름 | 사용자 인지 부조화 잔존 | 저 | slack-mobile-preview v0.1.3 캘리브레이션으로 헤더 영역 1:1 확인됨 |

## 9. Out of Scope (Phase 2+)

- **Phase 2** — 헤더 표시 분리 ("본시장: 5/8 / 시간외: 5/11" 2줄) — 사용자가 거절
- **Phase 2** — 미국 휴일 캘린더 (NYSE calendar API) 연동
- **Phase 2** — 발송 시점이 마켓 오픈/클로즈 직전·후일 때의 fresh/stale 경계 처리
- **Phase 3** — STALE_THRESHOLD_DAYS 동적 계산 (요일·휴일 기반)

## 10. Roadmap & Milestones

| 마일스톤 | 산출물 | DoD |
|---|---|---|
| M1 — Plan ✅ | 본 문서 | 2 Checkpoint 통과, 사용자 승인 |
| M2 — Design | `docs/02-design/features/trading-date-fix.design.md` | 3 옵션 비교 + helper 시그니처 + 테스트 매핑 |
| M3 — Do | main.py + config.py + tests/test_main.py | helper 함수 + 상수 + 2 호출처 교체 + 3 테스트, 122 passed |
| M4 — Check | analysis.md | Match Rate ≥ 90%, helper 호출처 2곳 모두 적용 확인 |
| M5 — Report | report.md | 사이클 종료. 다음 휴장일 발송 시 시각 재검증 권장 |

## 11. Open Questions

| ID | 질문 | 결정 시점 |
|---|---|---|
| OQ-1 | helper 함수 이름 — `_resolve_last_trading_date` vs `_compute_index_stock_last_date` 등 | Design (`_resolve_last_trading_date` 권장 — 의도 명확) |
| OQ-2 | TRADING_DAY_CATEGORIES 상수 위치 — config.py vs main.py 모듈 상단 | Design (config.py 권장 — 사용자 결정 시 채택) |
| OQ-3 | helper의 fallback 동작 — 빈 리스트일 때 모든 quotes max vs `RuntimeError` | Design (max fallback 권장 — robust, 실제 운영엔 미발생 가정) |
| OQ-4 | 신규 L1 테스트 위치 — tests/test_main.py 추가 vs 새 파일 | Design (test_main.py 추가 권장 — 기존 헤더 테스트와 같은 파일) |
| OQ-5 | 다음 휴장일 시뮬 시각 재검증을 PDCA에 강제? | Report (운영 후 사이클로 검증 권장 — 자동화는 Phase 2) |

## 12. References

- 발견 메시지: GitHub Actions run-id 25649430993 (2026-05-11 03:55 UTC)
- 슬랙 발송: 채널 # 미증시지수
- 시뮬 PNG: scripts/output/preview-actions-25649430993-*.png
- 메모리 컨텍스트: `~/.claude/projects/.../memory/project_trading_date_display_bug.md`
- main.py:149 (Phase 1.5 빌드 함수) / main.py:635 (build_v15_message)
- 도구: scripts/preview_mobile.py (slack-mobile-preview, Match Rate 100%, v0.1.3)

---

**다음 단계**: `/pdca design trading-date-fix`
