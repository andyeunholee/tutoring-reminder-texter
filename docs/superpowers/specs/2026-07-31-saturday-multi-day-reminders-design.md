# 토요일 실행 시 여러 날짜 알림 준비 — 설계

작성일: 2026-07-31

## 배경

`Tutoring Reminder Texter - Daily` 작업이 매일 오후 2시에 앱을 띄우고, 앱은
`?auto=1` 로 **내일** 하루치 `[TUT]` 세션을 검색해 보여준다. 문자는 자동으로
나가지 않고 사용자가 검토 후 직접 보낸다.

주말에는 이 하루짜리 창이 부족하다. 토요일 오후에 앉았을 때 일·월·화 세션까지
한 번에 준비할 수 있어야 한다.

## 목표

토요일에 실행된 회차는 **일요일·월요일·화요일** 3일치 세션을 가져와서, 각 날짜별로
따로 문자를 만들어 검토·전송할 수 있게 한다. 토요일 이외의 요일은 지금과 동일하게
내일 하루만 다룬다.

## 비목표

- 템플릿 문안 변경. 한 통에 여러 날짜를 합치지 않으므로 `src/templates.py` 는 건드리지 않는다.
- `src/calendar_service.py` 의 조회 API 변경. 날짜별 반복 호출로 충분하다.
- 스케줄러 작업(`.bat`, 등록된 Windows 작업) 변경. 토요일 판정은 앱이 실행 시점에 한다.
- 날짜 간 중복 제거. 일요일 문자와 월요일 문자는 같은 사람에게 각각 나간다 (의도된 동작).

## 받아들인 트레이드오프

이 문자는 원래 "내일 수업" 알림이다. 토요일 회차에서 화요일 세션 알림을 보내면
수신자는 3일 전에 받는다. 사용자가 이 점을 인지하고 승인했다.

## 선결 과제: message key 충돌

`src/message_builder.py:39-41`

```python
def message_key(kind, identity, phones):
    basis = f"{kind}|{identity.casefold()}|{','.join(sorted(phones))}"
    return hashlib.md5(basis.encode("utf-8")).hexdigest()[:10]
```

키에 날짜가 없다. 같은 교사가 일요일과 화요일에 모두 수업이 있으면 **두 메시지의
키가 동일**해진다. `app.py` 는 이 키로 위젯과 결과를 색인한다:

- `app.py:217-218` — `ss[f"draft_{key}"]`, `ss[f"send_{key}"]`
- `app.py:398` — `ss.results[key]`
- `app.py:215-221` — `valid_keys` 기반 stale key 정리

따라서 충돌 시 문자 두 통이 편집창 하나를 공유하고, 결과 행도 하나만 남는다.
날짜별 분리 발송의 전제 조건이므로 가장 먼저 고친다.

### 해결

`message_key` 에 선택적 `day_tag` 를 추가한다. **비어 있으면 기존 해시를 그대로
유지**해서 기존 동작·테스트와 호환된다.

```python
def message_key(kind: str, identity: str, phones: list[str], day_tag: str = "") -> str:
    basis = f"{kind}|{identity.casefold()}|{','.join(sorted(phones))}"
    if day_tag:
        basis = f"{day_tag}|{basis}"
    return hashlib.md5(basis.encode("utf-8")).hexdigest()[:10]
```

`build_messages(..., day_tag: str = "")` 로 받아 `_build_teacher_messages` 와
`_build_student_messages` 에 전달한다. 호출 측은 `day.isoformat()` 을 넘긴다.

## 구성 요소

### 1. `src/coverage_window.py` (신규)

날짜 선택 규칙만 담는 순수 모듈. I/O 없음, 단위 테스트 대상.

```python
SATURDAY = 5   # date.weekday(): Mon=0 … Sat=5, Sun=6

def default_span(today: date) -> int:
    """`today` 에 시작한 회차가 며칠치를 다룰지."""
    return 3 if today.weekday() == SATURDAY else 1

def coverage_days(first_day: date, span: int) -> list[date]:
    """`first_day` 부터 연속 `span` 일. span 은 최소 1."""
    return [first_day + timedelta(days=i) for i in range(max(1, span))]
```

토요일 실행 → `first_day` = 일요일, `span` = 3 → 일·월·화.

### 2. `app.py` — 날짜 선택

`requested_day()` (`app.py:133-141`) 를 다음으로 대체한다.

- `first_day`: `?date=YYYY-MM-DD` 가 있으면 그 날, 없으면 `date.today() + 1일`
- `span` 은 다음 순서로 먼저 맞는 규칙을 쓴다:
  1. `?days=N` 이 있으면 N (`?date=` 와 함께 와도 `?days=` 가 이긴다)
  2. `?date=` 만 있으면 1 — 날짜를 명시한 조회는 그 하루만
  3. 둘 다 없으면 `default_span(date.today())`

파싱 실패한 `?date=` / `?days=` 값은 지금처럼 조용히 무시하고, 해당 항목이 없는 것으로
취급해 위 규칙을 다시 적용한다.

### 3. `app.py` — 입력 위젯

기존 `st.date_input("Session date")` 는 그대로 두고 옆에 추가한다:

```python
st.number_input("Days to cover", min_value=1, max_value=7, value=span, step=1)
```

`st.date_input` 을 범위 모드로 바꾸는 대안은 채택하지 않는다 — 범위 선택 도중
원소 1개짜리 튜플이 반환되는 상태를 매번 방어해야 해서 더 부서지기 쉽다.

Streamlit 위젯 특성상 `value=` 는 첫 렌더에만 적용되고 이후에는 세션 상태가
이긴다. 기존 `date_input` 과 동일한 동작이며 의도한 바다.

### 4. `app.py` — 조회

`src/calendar_service.py` 는 수정하지 않는다. 날짜마다 기존 메서드를 반복 호출한다.

```python
for d in coverage_days(first_day, span):
    events, total = svc.list_tut_events_on(d)
```

API 호출이 1회에서 최대 3회로 늘지만 주 1회 3회는 무시할 수준이고, 날짜별 구조가
자연스럽게 유지된다.

세션 상태를 평면 `ss.events` / `ss.searched_day` 에서 날짜별 목록으로 바꾼다:

```python
ss.day_results = [{"day": d, "events": [...], "total_scanned": n}, ...]
```

기존 `ss.events`, `ss.total_scanned`, `ss.searched_day` 는 제거한다. 이에 따라
`app.py:71-77` 의 `setdefault` 블록은 `ss.setdefault("day_results", None)` 로 바꾸고,
"아직 검색 안 함" 판정(`app.py:178`)도 `ss.day_results is None` 기준으로 바꾼다.
`ss.autosearch_done`, `ss.results`, `ss.run_log` 는 그대로 둔다.

### 5. `app.py` — 메시지 생성

`build_messages` 를 **날짜마다 한 번씩** 호출하고 이어붙인다.

```python
for r in ss.day_results:
    day_msgs = build_messages(r["events"], roster, ..., day_tag=r["day"].isoformat())
```

이렇게 하면 `merge_sessions_per_recipient` 병합이 하루 안에서만 일어나 현재 동작과
동일하고, `TEACHER_MULTI` / `STUDENT_GROUP_MULTI` 의 `date_long` (첫 이벤트 날짜에서
가져옴, `src/message_builder.py:115`, `:137`) 도 항상 올바르다.

사이드바 토글 필터(`send_teachers` / `send_students`)는 날짜별 결과를 합친 뒤 적용한다.

- `ss.messages`: 전 날짜 평면 리스트 (전송 로직이 그대로 쓴다)
- 렌더링용으로 날짜 → 메시지 목록 매핑을 함께 유지한다

`valid_keys` 기반 stale key 정리(`app.py:215-221`)는 평면 리스트 기준 그대로 동작한다.

### 6. `app.py` — 화면 2 (요약)

날짜별로 소제목 + 세션 표를 반복한다. 세션이 없는 날짜는 안내만 띄우고 **건너뛴다**.

현재 `app.py:232-234` 의 `st.stop()` 을 반드시 제거해야 한다. 그대로 두면 일요일이
비었을 때 월·화까지 통째로 보이지 않는다. 전체 중단은 **모든 날짜가 비었을 때만**.

취소 이벤트 expander와 파서 감사(raw titles) expander도 날짜별로 나눈다.

### 7. `app.py` — 화면 3 (검토 목록)

검토 폼은 **전 날짜를 감싸는 하나의 `st.form("review")`** 를 유지하고 제출 버튼도
하나로 둔다. 폼 안에서는 날짜별 소제목 아래에 해당 날짜의 메시지 컨테이너를 렌더한다.

날짜별 "Select all / Deselect all" 버튼은 **폼 바깥, 폼 위쪽**에 날짜당 한 줄로
배치한다. Streamlit 폼 안에서는 `st.form_submit_button` 외의 버튼을 쓸 수 없기
때문이다. 기존 전역 3버튼(`app.py:283-293`)도 그 위에 그대로 둔다.

`app.py:277-279` 의 "보낼 것 없음" `st.stop()` 은 **모든 날짜를 통틀어** 메시지가
없을 때만 발동하도록 바꾼다.

제출 버튼의 선택 개수 집계는 평면 리스트 기준이라 수정 없이 동작한다.

### 8. 전송 — 변경 없음

`build_jobs` (`app.py:332-347`), `run_send` (`app.py:350-422`), 결과·재시도 영역
(`app.py:448-468`) 모두 그대로 둔다. 키가 날짜별로 유일해지면 기존 로직이 정상
동작한다. 결과 표에는 날짜 열을 추가하면 좋지만 필수는 아니다.

### 9. 스케줄러 — 변경 없음

`daily_reminder.bat`, `run_app.bat`, `setup_daily_task.bat`, 등록된 Windows 작업
모두 수정하지 않는다. `?auto=1` 은 여전히 "즉시 검색"만 의미하고, 며칠치를 볼지는
앱이 `default_span(date.today())` 로 스스로 정한다.

## 오류 처리

- 캘린더 조회가 어느 하루에서 실패하면 지금처럼 `st.error` 후 중단한다. 부분 성공을
  섞으면 사용자가 "일요일 세션이 없는 것"과 "일요일 조회가 실패한 것"을 구분할 수 없다.
- 로스터 로드 실패 처리는 변경 없음 (`app.py:186-196`).
- `?days=` 는 1~7로 클램프한다.

## 테스트

`tests/test_coverage_window.py` (신규)

- 토요일 → `default_span` 이 3
- 월~금, 일요일 → `default_span` 이 1
- `coverage_days` 가 `first_day` 부터 연속된 날짜를 span 개 반환
- `span` 이 0 이나 음수여도 최소 1일

`tests/test_message_builder.py` (추가)

- 같은 kind·identity·phones 라도 `day_tag` 가 다르면 키가 다르다
- `day_tag` 가 비면 키가 기존과 동일하다 (하위 호환)
- `build_messages` 를 날짜별로 호출했을 때 각 메시지 본문의 `date_long` 이 해당
  날짜와 일치하고, 병합이 날짜를 넘지 않는다

기존 4개 테스트 파일은 모두 통과해야 한다.

## 수동 검증

`http://localhost:8501/?date=2026-08-02&days=3&auto=1` 로 열어 일·월·화 3일치가
날짜별 구획으로 나오는지, 같은 교사가 두 날짜에 있을 때 편집창이 서로 독립인지
확인한다. 토요일 자동 동작은 `?days=` 없이 토요일에 열어 확인한다.

## 성공 기준

1. 토요일 오후 2시 자동 실행 시 일·월·화 세션이 날짜별로 구분되어 나온다.
2. 토요일 외의 요일은 기존과 동일하게 내일 하루만 나온다.
3. 한 사람이 여러 날짜에 등장해도 문자·편집창·전송 결과가 각각 독립이다.
4. 각 문자의 날짜 줄이 그 문자가 다루는 날짜와 일치한다.
5. 중간에 비어 있는 날짜가 있어도 나머지 날짜가 정상적으로 보인다.
6. 문자는 여전히 자동 발송되지 않는다.
