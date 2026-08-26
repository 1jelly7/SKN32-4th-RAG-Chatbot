# [팀 공유 자료 9] 이상탐지(anomaly) 임시 대시보드 — 삭제 체크리스트

- **목적**: 채팅 화면 오른쪽에 임시로 붙여둔 이상탐지 위젯을, 다른 팀원이 실제
  이상탐지 대시보드를 완성한 뒤 깨끗하게 걷어낼 수 있도록 건드린 파일과 되돌리는
  방법을 한 곳에 정리한다.
- **왜 임시인가**: 정식 대시보드 전에 데이터가 실제로 이상한지부터 눈으로 보려고
  만든 것이라, sales_reader/purchase_reader에 고정 SQL 3종(금액 이상치·연체
  과다·거래처 급증거래) × 2도메인만 돌린다. LLM/Text2SQL 경로를 안 타고, 화면도
  채팅 페이지에 얹은 표 하나뿐이다.
- 코드 곳곳에 `TEMP` 주석을 남겨뒀다 — 이 문서는 그 주석들을 한 번에 모아둔 것이다.

---

## 1. 통째로 지우는 파일 (4개)

| 파일 | 비고 |
|---|---|
| `app/services/anomaly_service.py` | `AnomalyRow`, 고정 SQL 6개, `get_anomalies()` |
| `app/api/anomalies.py` | `GET /api/anomalies` |
| `app/tests/test_anomaly_service.py` | 3단계 단위 테스트 |
| `app/tests/test_anomalies_api.py` | 4단계 API 계약 테스트 |

## 2. 등록/배선 코드에서 몇 줄만 지우는 파일

### `app/main.py`
- import줄: `from app.api.anomalies import router as anomalies_router  # TEMP: ...`
- 등록줄: `application.include_router(anomalies_router, prefix="/api")  # TEMP`

두 줄 다 `# TEMP` 표시가 붙어 있어서 검색으로 바로 찾힌다.

### `deploy/nginx/local.conf`
`# TEMP: 이상탐지 임시 대시보드 API...` 주석부터 그 아래
```nginx
location = /api/anomalies {
    proxy_pass http://fastapi_local;
}
```
블록까지 삭제. **로컬 게이트웨이를 쓰는 사람은 nginx도 재시작(reload)해야
반영된다** — FastAPI 쪽만 지우고 nginx 설정을 안 지우면 `/api/anomalies`가
사라진 코드로 프록시되다가 502가 나는 정도라 위험하진 않지만, 정리하는 김에
같이 지우는 게 깔끔하다.

## 3. 프론트엔드 3개 파일 (여기가 제일 놓치기 쉽다)

### `django_app/web/templates/web/index.html`
`<!-- TEMP: 이상탐지 임시 대시보드 -->`부터 `<!-- // TEMP: 이상탐지 끝 -->`까지
(`#anomaly-panel` 블록 전체, `#sources-list` 바로 아래) 삭제.

### `django_app/web/static/web/style.css`
1. `/* TEMP: 이상탐지 임시 대시보드... */`부터 `/* // TEMP: 이상탐지 끝 */`까지
   (`.anomaly-*` 규칙 전부) 삭제.
2. **여기는 단순 삭제로 안 끝난다.** `.sources-panel`/`.sources-list`를
   `.anomaly-panel`과 세로로 나눠 쓰려고 flex 구조로 바꿔뒀다. 그 규칙 바로 위
   주석에 `old:`로 원래 값을 남겨뒀으니, 그 값으로 되돌려야 한다:
   ```css
   /* 되돌릴 값 */
   .sources-panel { min-height: 100dvh; overflow: hidden; border-left: 1px solid var(--line); background: #f9fafb; box-shadow: -5px 0 15px -10px rgba(0, 0, 0, .2); }
   .sources-list { height: calc(100dvh - 75px); overflow-y: auto; padding: 15px; }
   ```
   (`min-height`가 아니라 `height: 100dvh`로 되어 있는 게 지금 상태다 — 이상탐지
   패널과 flex로 공간을 나눠 쓰려고 min-height를 height로 바꾼 것까지 포함해서
   되돌려야 한다. 1단계 커밋 당시엔 이 차이를 놓쳐서 소스 카드가 많을 때 패널이
   뷰포트 밖으로 밀리는 버그가 났었다 — 되돌릴 때도 유의.)

### `django_app/web/static/web/chat.js`
1. 파일 맨 아래 `// --- TEMP: 이상탐지 임시 대시보드 ---`부터
   `// --- // TEMP: 이상탐지 끝 ---`까지 삭제 (`anomalyBody`, `renderAnomalies()`,
   `loadAnomalies()`).
2. **블록 밖에 참조가 2곳 더 있다** — 안 지우면 `loadAnomalies is not defined`
   런타임 에러가 난다:
   - `clearApplicationState()` 안: `if (typeof anomalyBody !== 'undefined') anomalyBody.innerHTML = ...` 줄
   - `showApplication()` 끝: `loadAnomalies();` 호출
   둘 다 바로 옆에 `// TEMP` 주석이 붙어 있다.

## 4. 선택 정리

- `app/requirements.txt`, `app/pyproject.toml`의 `typing-extensions` 줄:
  `AnomalyRow`를 FastAPI `response_model`로 쓰려고 추가한 의존성이다(Python 3.11 +
  pydantic v2에서는 `typing.TypedDict`가 아니라 `typing_extensions.TypedDict`가
  필요했다). 다른 곳에서 `typing_extensions`를 직접 import하는 데가 없으면
  지워도 되지만, 어차피 fastapi/pydantic의 전이 의존성이라 안 지워도 무해하다.

## 5. 지우고 나서 확인할 것

- `app/tests/` 전체 pytest 통과 (삭제한 테스트 파일이 안 남아 있는지도 함께 확인)
- 로컬 게이트웨이 실행 중이면 재시작(`scripts/local_gateway.ps1 restart`)해서
  브라우저 콘솔에 `loadAnomalies`/`anomalyBody` 관련 에러가 없는지 확인
- 채팅 페이지 오른쪽 패널이 "출처" 영역만으로 원래 높이대로 잘 나오는지 확인
  (2절의 `.sources-panel`/`.sources-list` 복원이 제대로 됐는지의 실질적 확인)
