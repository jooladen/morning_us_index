# 🔵 pytest — Developer Deep Dive

> Python 테스트 프레임워크의 사실상 표준. unittest의 보일러플레이트를 걷어내고 함수 + assert + fixture 패러다임을 정착시킴.

생성: 2026-05-11 · 출처: `/jooladen3-good-question pytest`

---

## 1. Origin of Pain

unittest(stdlib, JUnit clone)는 Python 1.5(1999) 시절에 들어왔다. Java/xUnit 패러다임을 거의 그대로 복사한 형태:

```python
import unittest
class TestList(unittest.TestCase):
    def setUp(self):
        self.lst = [1, 2, 3]
    def test_length(self):
        self.assertEqual(len(self.lst), 3)
    def test_contains(self):
        self.assertIn(2, self.lst)
    def tearDown(self):
        del self.lst
```

이게 Python스럽지 않다는 비판은 일찍부터 있었다. 구체적 불편:

1. **`AssertionError`만 던지고 끝** — `self.assertEqual([1,2,3], [1,2,4])` 실패 시 어느 인덱스가 다른지 안 보여줌. dict, set 비교도 동일.
2. **Parameterized testing 부재** — 같은 로직을 N개 입력으로 돌리려면:
   - 메서드 N개 복붙
   - 외부 라이브러리 (`parameterized`, `ddt`) 의존
   - for 루프 안에 우겨넣기 (1번 fail 시 나머지 미실행, 결과 보고도 1줄)
3. **Setup 공유의 어색함** — `setUpClass`, `setUpModule`, fixture가 메서드인지 클래스인지 모듈인지 매번 결정해야 함. 디렉토리 단위 공유는 더 어색.
4. **Boilerplate 누적** — `class Test...(unittest.TestCase)`, `self.assertEqual`, `self.assertTrue`, `self.assertRaises`, `self.assertIsNone`, ... 메서드 30+개 외워야 함. 결국 테스트 작성 진입 장벽이 됨.
5. **Plugin 생태계 부재** — DB·Mock·Coverage·HTTP·Async 등 도메인별 helper가 stdlib에 없음.

가장 심각한 결과: **테스트를 짜는 게 귀찮으면, 안 짜게 된다.** 그리고 안 짠 테스트는 production 사고로 돌아온다.

## 2. Identity & Analogy

**pytest = Python testing framework**. 핵심 철학을 한 문장으로: "**그냥 함수 + `assert` 키워드 + fixture 의존성 주입이면 충분하다.**"

비유: unittest가 **관공서 양식**이라면 pytest는 **포스트잇**. 같은 의미 전달, 다른 의식.

```python
# unittest
class TestSum(unittest.TestCase):
    def test_two_plus_two(self):
        self.assertEqual(sum([2, 2]), 4)

# pytest
def test_two_plus_two():
    assert sum([2, 2]) == 4
```

핵심 무기 4종:

### 2.1 Assert rewriting
pytest는 import 시점에 AST 레벨에서 `assert` 문을 분해·재작성한다. 그래서 단순 `assert a == b`도 실패 시 양쪽 값을 보여준다:

```
>       assert [1, 2, 3, 4, 5] == [1, 2, 3, 4, 6]
E       assert [1, 2, 3, 4, 5] == [1, 2, 3, 4, 6]
E         At index 4 diff: 5 != 6
```

dict, set, dataclass 비교 모두 자동 diff. 별도 메서드(`assertEqual`, `assertIn`, ...) 불필요.

### 2.2 Fixture (DI 패러다임)
함수 시그니처의 인자 이름이 곧 의존성:

```python
@pytest.fixture
def db_session():
    session = create_session()
    yield session            # teardown은 yield 뒤
    session.close()

def test_user_create(db_session):  # 자동 주입
    db_session.add(User(name="x"))
    assert db_session.query(User).count() == 1
```

`scope`로 라이프사이클 제어: `function`(기본) / `class` / `module` / `package` / `session`. 무거운 fixture(DB 컨테이너 기동 등)를 전 세션 공유 가능.

`conftest.py`에 fixture 정의 시 디렉토리 트리 전체에서 자동 공유 — import 불필요.

### 2.3 Parametrize
하나의 테스트 함수, N개 케이스:

```python
@pytest.mark.parametrize("amount,rate,expected", [
    (1000, 0.05, 1050),
    (0, 0.05, 0),
    (-100, 0.05, -95),
    (1_000_000, 0.0, 1_000_000),
])
def test_apply_interest(amount, rate, expected):
    assert apply_interest(amount, rate) == expected
```

각 케이스가 **독립적으로 실행/보고**된다. 1번 실패해도 2~4번은 끝까지 돈다.

### 2.4 Markers
`@pytest.mark.slow`, `@pytest.mark.integration` 등으로 분류 → CLI 필터:

```bash
pytest -m "not slow"                   # 빠른 것만
pytest -m "integration"                 # 외부 의존 검증
pytest -m "not slow and not integration"
```

우리 morning-us-index의 `pytest.ini`도 이 패턴을 사용한다:

```ini
[pytest]
markers =
    integration: requires network / external API
addopts = -m "not integration" -ra --strict-markers
```

## 3. Philosophy & DNA

**Holger Krekel** (독일). 2003–2004년 `pylib` 일부로 시작 → 2010년대 들어 독립 프로젝트로 분리. 현재 GitHub Org `pytest-dev`가 유지.

핵심 설계 결정:

1. **No Class, No Self** — `unittest.TestCase` 상속 강제 안 함. 함수만으로 충분.
2. **Plain `assert`** — Python 기본 키워드를 쓰되, AST 재작성으로 메시지 풍부화.
3. **DI by Convention** — fixture는 인자 이름으로 매칭. 명시적 데코레이터/주입 컨테이너 불필요.
4. **Plugin-First Architecture** — 코어는 작게, 확장은 플러그인으로. `pluggy` 라이브러리(역시 pytest-dev에서 분리)가 이 hook 시스템.

영향: Plugin 생태계가 1,500개+. `pytest-django`, `pytest-asyncio`, `pytest-mock`, `pytest-cov`, `pytest-xdist`(병렬), `pytest-bdd`(behavior-driven), `pytest-benchmark` 등.

unittest 호환성도 유지 — 기존 unittest TestCase 클래스를 pytest로 그대로 실행 가능. 마이그레이션 비용을 0으로 낮춰 채택을 가속.

## 4. Value & Utility

### 4.1 코드량 70% 감소

5줄 → 2줄, 100개 케이스 → 1 함수. 누적되면 큰 차이.

### 4.2 디버깅 시간 5분 → 5초

assert rewriting 덕분에 실패 메시지가 곧 진단. dict 비교 사례:

```
E       AssertionError: assert {'a': 1, 'b': 2} == {'a': 1, 'b': 3}
E         Differing items:
E         {'b': 2} != {'b': 3}
```

### 4.3 Mocking이 1급 시민

```python
@patch("main.time.sleep", return_value=None)
@patch("main.requests.post")
def test_post_slack_5xx_retries(mock_post, _mock_sleep):
    mock_post.return_value = MagicMock(status_code=503, text="...")
    with pytest.raises(RuntimeError, match="재시도 후"):
        post_slack("...", "msg")
    assert mock_post.call_count == 3
```

우리 morning-us-index의 `tests/test_main.py:test_l1_5_post_slack_5xx_retries_then_runtimeerror` 가 이 패턴. `time.sleep`까지 패치해서 30s+60s+120s 대기를 0.001초로 압축 → 테스트 0.88초 안에 끝남.

### 4.4 Fixture 캐싱으로 통합 테스트도 빠르게

`scope="session"` fixture로 Postgres 컨테이너 1번만 기동 → 200개 통합 테스트가 공유. unittest는 setUpClass/setUpModule로 가능하지만 코드가 더 복잡.

### 4.5 우리 프로젝트 실제 수치

| 항목 | 수치 |
|---|---|
| 테스트 파일 | 1개 (`tests/test_main.py`, 227줄) |
| 테스트 케이스 | 17개 (단위 16, 통합 1) |
| 단위 테스트 실행 시간 | 0.88초 |
| 통합 테스트 실행 시간 | 1.93초 (yfinance 실 호출 포함) |
| 같은 커버리지를 unittest로 짠다면 | ~400줄 추정, 메서드 시그니처 보일러플레이트 |

## 5. Risk & Cost

unittest 고집 시 누적 비용:

### 5.1 채용·온보딩 비용
2026년 현재 Python 면접에서 "테스트 어떻게 짜세요?" 질문에 90%가 pytest로 답한다. 사내가 unittest only면 신규 입사자가 사내 컨벤션을 새로 외워야 함.

### 5.2 회귀 테스트 누락
parametrize 부재로 경계 케이스 N개 테스트가 메서드 N개 복붙으로 이어지고, 결국 일부만 작성된 채로 배포. 환율·통화·날짜 boundary 같은 도메인에서 production 사고 빈도 ↑.

### 5.3 Mock 패턴 표준화 부재
unittest의 `mock.patch`는 사용 가능하지만 fixture와 통합되지 않음. 5개 테스트가 같은 mock을 공유하려면 setUp에서 매번 시작/종료. pytest-mock의 `mocker` fixture는 자동 cleanup.

### 5.4 Plugin 생태계 단절
pytest-django의 `db` fixture, pytest-asyncio의 `event_loop`, pytest-trio, pytest-postgresql, ... 도메인별 보일러플레이트 제거기를 못 씀.

### 5.5 실제 사고 시나리오

환율 계산 함수에 작은 변경. unittest 5개 통과 → 배포. 그러나 **TWD(대만 달러)** 케이스가 5개 안에 없었음. 한 달 뒤 대만 사용자 결제 망가진 것 발견. 회사 손실 + 신뢰도 하락.

`@pytest.mark.parametrize`로 통화 30종을 한 줄에 넣어 테스트했다면 PR 단계에서 잡혔을 사고. **테스트 진입 장벽이 곧 사고 확률.**

> 결론: pytest를 안 쓰는 비용 = 매일의 보일러플레이트 + 가끔의 production 사고 + 새 동료의 학습 세금 + 채용 풀 축소.

## 6. Next Steps

| # | 도구/개념 | 역할 | 왜 자연스러운 다음? |
|---|---|---|---|
| 1 | **pytest-mock** | `mocker` fixture로 `unittest.mock.patch` 래핑 | `mocker.patch(...)` 사용. fixture scope에 자동 cleanup. 우리도 이미 `@patch` 데코레이터로 사용 중인데, fixture 형태로 쓰면 더 깔끔 |
| 2 | **pytest-cov** | 코드 커버리지 측정 (`coverage.py` 래퍼) | `pytest --cov=main --cov-report=term-missing`. CI 80% 게이트 가능 |
| 3 | **hypothesis** | Property-based testing | `@given(st.floats(min_value=0))` 로 입력값 자동 생성. 사람이 못 떠올리는 경계 케이스 발견 |
| 4 | **pytest-xdist** | 병렬 실행 | `pytest -n 4` 로 4 코어 활용. 통합 테스트 많은 프로젝트에서 필수 |
| 5 | **tox / nox** | 환경 매트릭스 | Python 3.10/3.11/3.12 × OS 조합으로 자동 실행. 라이브러리 만들 때 필수 |
| 6 | **GitHub Actions ci.yml** | PR 자동 검증 | 우리 `daily_report.yml`은 production 워크플로. 별도 `ci.yml` 추가하면 매 PR마다 pytest 자동 실행 |
| 7 | **mutmut / cosmic-ray** | Mutation testing | "테스트가 실제로 코드의 의미를 검증하는가?" 코드 한 글자씩 변형해도 테스트가 통과하면 의미 없는 테스트 |
| 8 | **pytest fixture 마스터링** | scope, parametrize, indirect fixtures | 고급 패턴: factory fixture, autouse, indirect parametrize |

### 추천 학습 순서

```
pytest 기본
    ↓
pytest-mock (외부 의존성 격리)
    ↓
pytest-cov (커버리지 측정 → 80% 게이트)
    ↓
GitHub Actions에 pytest 통합 (PR 자동 검증)
    ↓
parametrize + hypothesis (경계 케이스 자동화)
    ↓
mutation testing (테스트 자체의 품질 검증)
```

**4단계 성숙도 모델**:
1. 테스트를 **짠다**
2. 테스트를 **잘 짠다** (mocking, fixture, parametrize)
3. 테스트가 **자동으로 돌게 한다** (CI/CD)
4. 테스트 **자체를 의심하고 강화한다** (coverage, mutation)

pytest는 1단계 출발점이자 4단계 모든 곳에서 중심에 남는다.

---

## 📊 다른 언어/생태계 매핑

| 언어 | 도구 | pytest 대비 |
|---|---|---|
| Java | **JUnit 5 (Jupiter)** | 원조. `@Test`, `@ParameterizedTest`. pytest가 이걸 보고 "Python답지 않다" 생각하며 만든 것 |
| JavaScript | **Jest** (Meta) | Snapshot, mock 빌트인. pytest와 가장 가까운 ergonomics |
| JavaScript | **Vitest** | Vite 생태계, Jest 호환. 빠른 HMR |
| JavaScript | **Mocha + Chai** | Mocha=실행기, Chai=assertion. 분리형 |
| Ruby | **RSpec** | `describe/it/expect` 자연어 BDD 스타일. pytest의 함수 스타일과 다른 길 |
| Ruby | **Minitest** | Ruby의 unittest. 표준 라이브러리 포함 |
| Go | **testing (stdlib)** | 단순함의 끝판왕. `testify`로 assertion 보강 가능. 함수 시그니처 `func TestX(t *testing.T)` 강제 |
| Rust | **cargo test** | 빌드 도구에 내장. `#[test]` 매크로. property testing은 `proptest` 또는 `quickcheck` |
| C# | **xUnit / NUnit** | xUnit이 JUnit의 후예. 닷넷 진영 표준 |
| Kotlin | **Kotest** | DSL 풍부, BDD 스타일 가능 |
| PHP | **PHPUnit** | xUnit 패밀리 표준 |
| Swift | **XCTest** | Apple 공식, Xcode 통합 |

**관찰**: pytest의 "함수 + assert + fixture DI" 패턴은 동적 언어에서 자연스러우나 정적 언어(Java, Go, Rust)는 데코레이터/매크로로 비슷한 ergonomics를 추구하면서도 클래스/구조체 기반을 유지하는 경향.

---

## 🎯 우리 프로젝트 적용 사례

`tests/test_main.py` 17 케이스 분석:

| 분류 | 테스트 | 사용 기능 |
|---|---|---|
| Pure function (build_message) | L1-1, L1-2, L1-3a/b/c/d, extra_blocks 2건, empty | plain assert |
| External API mocking (Slack) | L1-5, L1-5b, L1-5c, success | `@patch("main.requests.post")`, `@patch("main.time.sleep")` |
| Env var (config) | missing/set/blank | `monkeypatch` fixture (pytest 빌트인) |
| Real network (yfinance) | L1-4 | `@pytest.mark.integration` |
| Boundary defense | prev=0 div-by-zero | plain assert + 코드 가드 검증 |

**활용 포인트**:
- `monkeypatch` fixture로 환경변수 임시 변경 (test 후 자동 복원)
- `MagicMock` + `@patch` 데코레이터 스택으로 외부 호출 격리
- `pytest.raises(RuntimeError, match="재시도 후")` 로 예외 메시지까지 검증
- `pytest.mark.integration` 로 CI에서 외부 의존 테스트 분리 (`addopts = -m "not integration"`)

---

## 📚 References

- 공식 문서: https://docs.pytest.org/
- pytest GitHub: https://github.com/pytest-dev/pytest
- Plugin 카탈로그: https://docs.pytest.org/en/stable/reference/plugin_list.html
- Holger Krekel 인터뷰/블로그: https://holgerkrekel.net/
- 우리 프로젝트 `pytest.ini`: 마커 정의, addopts 설정
- 우리 프로젝트 `tests/test_main.py`: 17 케이스 실 사례

---

> 다음 호기심: `/jooladen3-good-question fixture` `/jooladen3-good-question hypothesis` `/jooladen3-good-question coverage`
