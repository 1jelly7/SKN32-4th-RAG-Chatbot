# FastAPI + OpenAI + MCP 기반 RAG Assistant

이 프로젝트는 다음 기능을 하나의 PyCharm 프로젝트에서 단계적으로 확인하기 위한 교육용 예제입니다.

- OpenAI GPT 질의응답
- MCP Tool 호출
- MCP Resource 제공
- MCP Prompt 제공
- 안전한 파일 시스템 접근
- MySQL 데이터 저장 및 조회
- FAISS 또는 Qdrant Vector Search
- RAG 문서 검색과 근거 기반 답변
- FastAPI REST API

## 1. 프로젝트 구조

```text
mcp_rag_project/
├── app/
│   ├── main.py
│   ├── routers/
│   ├── services/
│   ├── tools/
│   ├── vectordb/
│   ├── llm/
│   └── config/
├── mcp_server/
│   ├── server.py
│   ├── tools.py
│   └── resources.py
├── docs/
├── data/
├── requirements.txt
├── .env.example
└── README.md
```

## 2. 권장 실행 환경

- Windows 11
- Python 3.11
- PyCharm
- 선택 사항: MySQL 8.x
- 선택 사항: Qdrant Docker 서버
- 선택 사항: Node.js(MCP Inspector 실행 시)

## 3. 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
Copy-Item .env.example .env
```

기본 설정은 다음과 같으므로 API 키나 외부 DB 없이도 인덱싱과 검색 구조를 확인할 수 있습니다.

```env
EMBEDDING_BACKEND=local
VECTOR_BACKEND=faiss
MYSQL_ENABLED=false
```

실제 OpenAI GPT와 임베딩을 사용하려면 `.env`를 수정합니다.

```env
OPENAI_API_KEY=발급받은_API_KEY
EMBEDDING_BACKEND=openai
```

## 4. FastAPI 실행

```powershell
python -m app.main
```

또는 다음과 같이 실행합니다.

```powershell
uvicorn app.main:app --reload
```

접속 주소:

- 안내 화면: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- 상태 확인: `http://127.0.0.1:8000/api/health`

## 5. RAG 실행 순서

Swagger에서 다음 순서로 실행합니다.

1. `POST /api/rag/rebuild`
2. `POST /api/rag/search`
3. `POST /api/rag/ask`

검색 예:

```json
{
  "query": "MCP의 Tool과 Resource 차이는?",
  "top_k": 4
}
```

RAG 질문 예:

```json
{
  "question": "MCP의 주요 구성 요소를 설명해줘.",
  "top_k": 4
}
```

## 6. MCP 서버 실행

FastAPI와 MCP 서버는 역할이 다르므로 별도 터미널에서 실행합니다.

```powershell
python -m mcp_server.server
```

stdio 서버는 일반 웹 화면을 열지 않고 MCP Client의 연결을 기다립니다.

## 7. MCP Inspector 테스트

Node.js가 설치되어 있다면 다음 명령으로 MCP Tool, Resource, Prompt를 테스트합니다.

```powershell
npx -y @modelcontextprotocol/inspector python -m mcp_server.server
```

Inspector에서 확인할 기능:

- Tools
  - `add`
  - `list_document_files`
  - `read_document_file`
  - `vector_search`
  - `rebuild_rag_index`
  - `rag_question_answer`
  - `mysql_knowledge_list`
- Resources
  - `config://runtime`
  - `docs://catalog`
- Prompts
  - `grounded_rag_prompt`

## 8. Qdrant local 모드

별도 Qdrant 서버 없이 프로젝트 폴더에 데이터를 저장합니다.

```env
VECTOR_BACKEND=qdrant
QDRANT_MODE=local
```

설정 변경 후 FastAPI를 재시작하고 인덱스를 다시 구축합니다.

## 9. Qdrant server 모드

Docker에서 Qdrant를 실행합니다.

```powershell
docker run -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

`.env` 설정:

```env
VECTOR_BACKEND=qdrant
QDRANT_MODE=server
QDRANT_URL=http://127.0.0.1:6333
```

## 10. MySQL 설정

root 계정으로 다음 SQL을 실행합니다.

```sql
CREATE DATABASE IF NOT EXISTS mcp_rag_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'mcp_user'@'localhost'
IDENTIFIED BY '1234';

GRANT ALL PRIVILEGES ON mcp_rag_db.* TO 'mcp_user'@'localhost';

FLUSH PRIVILEGES;
```

`.env`를 수정합니다.

```env
MYSQL_ENABLED=true
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=mcp_rag_db
MYSQL_USER=mcp_user
MYSQL_PASSWORD=1234
```

Swagger 실행 순서:

1. `POST /api/mysql/init`
2. `POST /api/mysql/items`
3. `GET /api/mysql/items`

## 11. 주의 사항

- `local` 임베딩은 API 키 없이 구조를 실습하기 위한 해시 기반 임베딩입니다.
- 의미 기반 검색 품질을 높이려면 OpenAI 임베딩을 사용합니다.
- stdio MCP 서버에서는 일반 `print()`를 stdout에 출력하지 않는 것이 안전합니다.
- 파일 Tool은 보안을 위해 `docs` 폴더 밖의 경로 접근을 차단합니다.
- MySQL API는 학습용 테이블만 사용하며 임의 SQL 실행 기능을 제공하지 않습니다.
