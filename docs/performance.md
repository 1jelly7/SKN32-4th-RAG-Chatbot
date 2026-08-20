# 채팅 성능 측정 및 운영 관측

## 목표와 측정 경계

목표는 일반 질문과 유효한 RAG/MCP 질문의 브라우저 입력부터 최종 DOM 렌더까지 5초
이하다. 서버 시간은 HTTP 요청 수신부터 응답 반환까지이며, E2E 시간은 클라이언트 요청
준비·네트워크·JSON 처리·DOM 렌더를 포함한다. 오류나 `INSUFFICIENT` 응답은 5초 안에
끝나더라도 목표 달성으로 세지 않는다.

권장 예산은 다음과 같다.

| 구간 | 예산 |
|---|---:|
| 브라우저 요청 준비·JSON·DOM 렌더 | 150ms |
| 인증·middleware | 50ms |
| cache | 20ms |
| agent routing·evidence·직렬화 | 100ms |
| RAG/MCP/DB | 1,500ms |
| 최종 LLM | 2,800ms |
| 네트워크 여유 | 380ms |
| 합계 | 5,000ms |

## 재현 명령

현재 프로젝트 표준인 `.venv` 환경에서 실행한다.

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pytest --version
.venv\Scripts\python.exe -m scripts.benchmark_chat_performance --scenario all --iterations 5
.venv\Scripts\python.exe -m pytest --durations=0 -vv
.venv\Scripts\python.exe -m pytest -vv -ra
```

벤치마크는 인증만 비식별 `BenchmarkAuthenticationGateway`로 대체하고, 설정된
OpenAI·Document MCP·Data MCP·FAISS·MySQL 경계는 실제로 호출한다. 따라서 실제
FastAPI→Django introspection 네트워크 지연은 이 수치에 포함되지 않는다. 질문·응답·세션
토큰·접속정보는 결과에 출력하지 않는다. 현재 브라우저 인증 E2E는 benchmark app이 아니라
Django와 FastAPI를 함께 실행하고 동일 origin 경로 라우팅을 적용한 환경에서 측정한다.

## 2026-08-03 측정 결과

> 이 절의 수치는 Django 분리 전 측정 이력이다. 현재 구조의 성능 기준선으로 재사용하려면
> 실제 Django introspection과 경로 라우팅을 포함해 다시 측정해야 한다.

환경은 Python 3.11.9, pytest 9.1.1이다. 각 API 시나리오는 miss 5회와 동일 사용자·질문·
conversation의 hit 5회로 측정했다. `provider_warmup_ms=11,731.699`는 요청 전 PDF/FAISS
예열 비용이며 요청 통계와 분리했다.

| 시나리오 | 역할 | 상태 | cache | min | avg | median | p95 | max | 유효 5초 이내 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 일반 | admin | HTTP 200 | miss | 758.920 | 1,641.877 | 1,637.679 | 3,083.385 | 3,083.385 | 5/5 |
| 일반 | admin | HTTP 200 | hit | 1.364 | 1.588 | 1.464 | 1.881 | 1.881 | 5/5 |
| 문서 RAG | hr | HTTP 200, SUPPORTED | miss | 1,487.977 | 1,665.089 | 1,685.178 | 1,836.200 | 1,836.200 | 5/5 |
| 문서 RAG | hr | HTTP 200, SUPPORTED | hit | 1.397 | 1.573 | 1.498 | 2.005 | 2.005 | 5/5 |
| 구매 DB | finance | HTTP 502 | miss | 1,069.907 | 1,441.899 | 1,192.306 | 2,308.857 | 2,308.857 | 0/5 |
| 복합 | finance | HTTP 200, INSUFFICIENT | miss | 2,488.140 | 2,626.190 | 2,627.819 | 2,757.800 | 2,757.800 | 0/5 |

구매 DB는 읽기 계정 인증 거부로 `QUERY_ERROR`이며, `.env` 금지 규칙에 따라 이 작업에서
자격증명을 수정하지 않았다. 복합 질문도 구매 근거가 없어 유효 성공이 아니다. 따라서
전체 상태는 `NOT_READY`다.

실제 브라우저 UI에서는 일반 질문 첫 miss 3,862ms, 이후 5회 hit 67~95ms였고, 문서
질문 첫 miss 2,906ms, 이후 5회 hit 68~97ms였다. API cache hit가 약 1~2ms이므로 JSON
처리와 DOM 렌더를 포함한 브라우저 오버헤드는 약 60~95ms다. DB UI 5회는 모두 오류였고
p95 2,251ms, 복합 UI 5회는 모두 `INSUFFICIENT`였고 p95 3,957ms였다.

## 병목과 개선

변경 전 문서 miss p95는 10,401.425ms였고 `document_mcp` 평균은 9,788.603ms였다.
`cProfile` 단일 실행 15,838ms 중 15,764ms가 6개 PDF·150페이지 재파싱이었다. 문서 DB가
허용한 `file_path + updated_at`을 키로 최대 64개 LRU 파싱 캐시를 두고, 로딩을 thread로
오프로딩했으며 startup에서 PDF와 FAISS를 예열했다. 변경 후 `document_mcp` 평균은
36.671ms, 문서 miss p95는 1,836.200ms다.

OpenAI `AsyncOpenAI`도 요청마다 만들지 않고 앱 수명주기 동안 공유해 HTTP keep-alive
연결 풀을 재사용한다. 구매·판매의 동기 PyMySQL/EXPLAIN은 `asyncio.to_thread`로 옮겨
event loop 차단을 막았다. 현재 `BOTH`는 Document와 Database 분기를 병렬 실행해
evidence에서 합류하고, 구매·판매 두 Tool은 Database 분기 안에서 순차 실행한다. 최종
답변은 최대 600 completion token, Text2SQL은 400 token과 10초 timeout으로 제한한다.

문서 검색이 반환한 실제 `index_version`은 다음 lookup 컨텍스트와 write key에 동시에
반영한다. 사용자 ID·서버 세션 ID·역할·허용 DB·conversation hash는 기존처럼 cache key에
포함되므로 다른 사용자나 역할이 답변 cache를 공유하지 않는다.

## 관측 필드와 운영 권고

각 응답은 `X-Request-ID`와 `Server-Timing`을 반환한다. 로그에는 request ID, HTTP method와
path, status, total elapsed, cache hit/miss, role, route, agent/cache/document/data/evidence/
LLM 단계 시간, LLM call 유형·모델·시도 수·가능한 input/output token 수가 기록된다.
질문 원문, 전체 근거, API key, 세션 토큰, 비밀번호, 내부 `file_path`는 기록하지 않는다.

운영에서는 다음을 권장한다.

- 유효 응답 p95가 4,500ms를 넘거나 LLM p95가 3,500ms를 넘으면 경고한다.
- cache hit 비율 급락, provider warmup 실패, HTTP 5xx, MCP timeout을 별도 알림으로 둔다.
- 구매 읽기 계정 인증을 복구한 뒤 DB와 복합 시나리오를 각각 5회 이상 재측정한다.
- 문서 변경 시 DB `updated_at`과 인덱스 버전을 함께 갱신하고 프로세스를 재예열한다.
- 다중 worker 배포 전 FastAPI의 `MemoryCache`를 공유 Redis 구현으로 교체한다. 인증
  세션은 이미 Django DB session이 소유하므로 FastAPI `SessionStore` 교체 대상이 아니다.
- 실제 배포 경로에서 Django introspection p95와 `503` 비율을 별도 관측한다.
