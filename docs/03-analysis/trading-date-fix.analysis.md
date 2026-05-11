---
name: trading-date-fix
type: analysis
version: 0.1.0
status: complete
phase: check
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
plan: docs/01-plan/features/trading-date-fix.plan.md
design: docs/02-design/features/trading-date-fix.design.md
match_rate: 100
match_rate_breakdown:
  structural: 100
  functional: 100
  contract: 100
gap_counts:
  critical: 0
  important: 0
  minor: 0
formula: "static-only: structural × 0.2 + functional × 0.4 + contract × 0.4"
analyst: Ally (direct 3-axis comparison, no agent)
---

# Analysis — trading-date-fix (Match Rate 100%)

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 2026-05-11 발송 헤더 "직전 거래일: today (미 증시 휴장)" 모순 (slack-mobile-preview 도구로 발견) |
| **WHO** | 준 — 헤더 신뢰성 필수 |
| **RISK** | 매우 낮음 (helper 1개 + 호출 1곳) |
| **SUCCESS** | 휴장일 정확 표시 / 회귀 0 / 122 통과 |
| **SCOPE** | main.py 1곳(build_v15_message) + config.py 상수 + tests 3 케이스 |

---

## 1. Overall Match Rate

```
Static-only = Structural × 0.2 + Functional × 0.4 + Contract × 0.4
            = 100 × 0.2     + 100 × 0.4     + 100 × 0.4
            = 100%
```

| Category | Score | Status |
|---|:-:|:-:|
| Structural Match | **100%** | ✅ |
| Functional Depth | **100%** | ✅ |
| Contract Compliance | **100%** | ✅ |
| **Overall Match Rate** | **100%** | ✅ |

---

## 2. Structural Match — 100% (8/8)

| 항목 | Plan/Design 명세 | 실제 | 결과 |
|---|---|---|---|
| `config.py` `TRADING_DAY_CATEGORIES` 상수 | tuple[str, ...] = ('index', 'stock') | config.py:30-34 정확 | ✅ |
| `main.py` `_resolve_last_trading_date` helper | 함수 시그니처 + fallback | main.py:608-628 | ✅ |
| `main.py` import 추가 | TRADING_DAY_CATEGORIES from config | main.py:35 | ✅ |
| `main.py:635` helper 호출 (Design v0.1.1) | `_resolve_last_trading_date(quotes)` | main.py:662 (helper 추가로 라인 shift) | ✅ |
| `main.py:149` (Phase 1, IndexQuote) | helper 미적용 (v0.1.1 정정) | main.py:151 max(전체) 유지 + 주석 | ✅ |
| `tests/test_main.py` 3 L1-td 케이스 | test_resolve_last_trading_date_* | 모두 존재 + passed | ✅ |
| Plan/Design 문서 | v0.1.1 / v0.1.1 | 존재, 동기화 완료 | ✅ |
| 영향 외 파일 변경 0 | data.py/news.py/signals.py/preview_mobile.py | 변경 0 | ✅ |

---

## 3. Functional Depth — 100%

### 3.1 Plan FR-01 ~ FR-05 (v0.1.1 정정 반영)

| FR | 요구 | 구현 위치 | 충족 |
|---|---|---|:-:|
| FR-01 | helper `_resolve_last_trading_date(quotes) -> date` | main.py:608-628 | ✅ |
| FR-02 | config.py 상수 `TRADING_DAY_CATEGORIES = ('index', 'stock')` | config.py:34 | ✅ |
| FR-03 (v0.1.1) | main.py:149 helper **미적용** + IndexQuote/Quote 차이 주석 | main.py:151-155 | ✅ |
| FR-04 | main.py:635 helper 호출 | main.py:662 | ✅ |
| FR-05 | fallback `max(q.last_date for q in quotes)` | helper line 626-628 | ✅ |

### 3.2 Design §4 함수 동작 깊이

| 함수 | Design 단계 | 구현 | 깊이 |
|---|---|---|:-:|
| `_resolve_last_trading_date` | 1. filter trading_assets / 2. if 비어있지 않으면 max / 3. fallback max | 동일 3단계 (line 625-628) | 100 |

### 3.3 Placeholder / 미완성 검사

| 검사 | 결과 |
|---|---|
| `# TODO` / `# FIXME` | 0건 |
| 빈 함수 본문 | 0건 |
| `print()` 디버그 잔존 | 0건 |
| 하드코딩 mock 데이터 (실제 코드에서) | 0건 (테스트는 의도된 fixture) |

### 3.4 Design v0.1.0 → v0.1.1 정정 사유 — 코드 진실 우선

| 정정 | 사유 |
|---|---|
| 호출처 2곳 → **1곳** | Phase 1 build_message는 IndexQuote 받음 (category 필드 없음). Plan/Design v0.1.0의 grep만 본 추론 미스 발견 후 정정 |
| Phase 1 main.py:149는 `max(전체)` 유지 | 5개 지수(모두 index)만 받아 모순 표시 발생 불가. helper 통합 가치 없음 |

→ **Design v0.1.1 + Plan v0.1.1 후행 동기화 완료** (정직 보고 원칙 준수).

---

## 4. Contract Compliance — 100%

### 4.1 Plan Success Criteria

| ID | 지표 | 목표 | 결과 |
|---|---|---|:-:|
| SC-TD-1 | 휴장일 헤더 모순 0건 | 0건 (다음 휴장일 발송) | ✅ 정적: L1-td-2 invariant 잠금 |
| SC-TD-2 | 정상 거래일 회귀 0 | 0건 | ✅ 119/119 기존 통과 |
| SC-TD-3 | 신규 L1 테스트 통과 | 3/3 | ✅ 3 passed |
| SC-TD-4 | 전체 단위 통과 수 | 119 → **122** | ✅ 122 passed in 1.11s |
| SC-TD-5 | 변경 핵심 라인 (docstring 제외) | ≤30 | ✅ ~25 (helper 본문 ~5 + import 1 + 호출 1 + 상수 1 + 주석 ~17) |
| SC-TD-6 | main.py 외 파일 변경 0 (config + tests + docs 제외) | 0 | ✅ data.py/news.py/signals.py 변경 0 |

### 4.2 Plan NFR-01 ~ NFR-06

| ID | 목표 | 결과 |
|---|---|:-:|
| NFR-01 메시지 빌드 시간 영향 0 | helper O(n) — 변화 없음 | ✅ |
| NFR-02 변경 라인 수 ≤ 30 (핵심) | ~25 | ✅ |
| NFR-03 기존 119 테스트 회귀 0 | 119/119 통과 | ✅ |
| NFR-04 신규 L1 ≥ 3 | 3 | ✅ |
| NFR-05 slack-mobile-preview 영향 0 | preview_mobile.py 변경 0 | ✅ |
| NFR-06 운영 영향 (.github/workflows) | 0 | ✅ |

### 4.3 Design §6 Error Handling

| 시나리오 | helper 동작 | 결과 |
|---|---|:-:|
| trading_assets 비어 있음 (운영 미발생, 안전망) | fallback `max(q.last_date for q in quotes)` | ✅ |
| Quote.category Literal 외 값 | mypy strict 차단 | ✅ |
| quotes 빈 리스트 | main.py:627 (build_v15_message)가 RuntimeError 사전 차단 | ✅ |

### 4.4 Design §8 Test Plan ↔ 실제 매핑

| Design # | 실제 함수 | 결과 |
|---|---|:-:|
| L1-td-1 (모두 fresh) | `test_resolve_last_trading_date_all_fresh` | ✅ |
| L1-td-2 (주말 혼합) | `test_resolve_last_trading_date_weekend_mixed` | ✅ + 추가 검증 `assert max(전체)==date(2026,5,11)` |
| L1-td-3 (모두 stale) | `test_resolve_last_trading_date_all_stale` | ✅ |

---

## 5. Gap Classification

### 5.1 Critical Gaps — **0건**

### 5.2 Important Gaps — **0건**

### 5.3 Minor Gaps — **0건**

본 Check 단계 진입 직전 발견된 Plan v0.1.0 → v0.1.1 후행 동기화 3건은 모두 본 Check 단계 중 즉시 처리됨 (FR-03 정정 / FR-04 1곳 명시 / SC-TD-5 핵심 라인 정의 명확화).

---

## 6. Decision Record Verification

| Layer | 결정 | 구현 반영 | 결과 |
|---|---|---|:-:|
| [Plan v0.1.1] | helper 추출 + config 상수 | main.py:608 + config.py:34 | ✅ |
| [Plan v0.1.1] | 호출처 1곳 (main.py:635만) | main.py:662 helper, main.py:151 max 유지 | ✅ |
| [Plan v0.1.1] | L1 테스트 3 케이스 | 3 passed | ✅ |
| [Design v0.1.1] | Option C (Pragmatic Balance) | helper in main.py + config 상수 | ✅ |
| [Design v0.1.1] | fallback robust | max(전체) fallback line 628 | ✅ |
| [Design v0.1.1] | helper 위치 main.py 안 | main.py:608 | ✅ |

→ Decision Record Chain **100% 일치** (v0.1.1 정정 반영).

---

## 7. Strategic Alignment

| 질문 | 답 |
|---|---|
| 구현이 Plan WHY를 다루나? | ✅ 2026-05-11 발송 헤더 모순 문제 해소 |
| Plan SC 모두 달성? | 정적 6/6 ✅ (운영 SC-TD-1 검증은 다음 휴장일 발송으로) |
| Design 핵심 결정 따랐나? | 6/6 ✅ (v0.1.1 정정 후) |
| 전략적 misalignment? | 없음 |

---

## 8. Runtime Verification

도구 사이클(CLI Python, 웹 API/UI 없음) → L1 API / L2 Playwright / L3 E2E는 N/A. 대신:

| Layer | 항목 | 결과 |
|---|---|:-:|
| L1 단위 (신규) | pytest 3 cases | ✅ 3 passed in 0.89s |
| L1 전체 회귀 | pytest -m "not integration" | ✅ 122 passed in 1.11s |
| 운영 검증 (다음 단계) | 다음 휴장일 actions-log mode 시뮬 | ⏳ 운영 후 |

---

## 9. Do 단계 정직 보고 추적

| 사건 | 시점 | 대응 |
|---|---|---|
| Plan/Design v0.1.0에 main.py:149 + 635 두 곳 helper 통합 명시 | Plan/Design 작성 시 | grep만 본 추론 미스 |
| Do 도중 회귀 4건 발견 (`IndexQuote` AttributeError) | module-3 후 회귀 검증 | 즉시 정정 |
| main.py:151 helper 호출 철회 → max(전체) 복원 + 주석 | 정정 직후 | 회귀 0 확인 |
| Design v0.1.1로 후행 동기화 | 정정 완료 후 | §4.2.2 + Version History 갱신 |
| Plan v0.1.1로 후행 동기화 | Check 단계 진입 시 (본 분석) | FR-03/FR-04/SC-TD-5 정정 |

→ "정직한 보고" 원칙 준수 — 추측/얼버무림 없이 코드 진실에 맞춰 문서 동기화.

---

## 10. 100% 도달 평가 — 솔직 진단

| 질문 | 답 |
|---|---|
| 현재 Match Rate가 정확히 100%인가? | **그렇다.** Structural / Functional / Contract 모두 100%. |
| 본질적으로 100%를 막는 갭이 있나? | **없다.** Plan/Design v0.1.0 추론 미스는 v0.1.1로 정정 완료. |
| 운영 시 100% 유지 가능한가? | SC-TD-1(휴장일 모순 0건)은 다음 휴장일 발송에서 actions-log 시뮬 검증 필요. 정적 가드(L1-td-2)는 invariant 잠금. |
| 이번 사이클을 100%로 닫을 자격이 있나? | **있다.** 정적 갭 0 + 122 passed + Plan/Design v0.1.1 동기화 완료. |

---

## 11. Next Steps

1. **Report 단계 진입**: `/pdca report trading-date-fix`
2. **다음 휴장일 발송 시 actions-log 시뮬 재검증** (SC-TD-1 운영 정량 측정)
3. **commit + push + Actions 트리거** (코드 운영 반영)

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 0.1.0 | 2026-05-11 | Initial. 직접 3축 정밀 비교 + Plan/Design v0.1.1 후행 동기화 완료. Match Rate 100%. Do 단계 정직 보고 추적 포함. | jooladen (with Ally — 직접 분석) |
