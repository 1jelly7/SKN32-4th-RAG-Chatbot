# 사내 지식 RAG · Text2SQL MCP 챗봇 (Django + FastAPI)

> 사내 규정 문서와 구매·판매 데이터를 **하나의 채팅창**에서 검색하고, 검증된 근거와 함께 답변하는 업무용 AI 챗봇

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?logo=openai&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-0467DF)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-009639?logo=nginx&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-Tool%20Boundary-6E56CF)
![Tests](https://img.shields.io/badge/tests-402%20passed%20%C2%B7%2027%20skipped-success)

**SKN 32기 · 장꼬방(JangGGo) 팀** · 2026.08.24 ~ 2026.08.27

Django는 사용자 UI와 계정·세션·관리자 기능을 소유하고, FastAPI는 채팅 API·LangGraph·캐시·MCP
조율을 담당합니다. 두 애플리케이션은 독립 프로세스로 실행되며, Nginx가 하나의 공개 주소
(`127.0.0.1:8000`) 뒤에서 경로 기반으로 두 서비스를 라우팅합니다.

문서 근거가 필요한 질문에는 **FAISS 기반 RAG**를, 수치·현황 질문에는 **MySQL 기반 Text2SQL**을
사용합니다. 두 근거가 모두 필요하면 LangGraph가 문서 검색과 데이터 조회를 **병렬로 실행**하고,
Evidence Eval이 채택한 근거만 최종 답변에 사용합니다.

---

## 목차

- [시연 영상](#시연-영상)
- [팀 소개](#팀-소개)
- [프로젝트 개요](#프로젝트-개요)
- [이번 프로젝트에서 새로 추가된 기능](#이번-프로젝트에서-새로-추가된-기능)
- [데이터](#데이터)
- [사용 예시](#사용-예시)
- [시스템 아키텍처](#시스템-아키텍처)
- [핵심 구현](#핵심-구현)
- [품질 검증](#품질-검증)
- [기술적 도전과 해결](#기술적-도전과-해결)
- [기술 스택](#기술-스택)
- [빠른 시작](#빠른-시작)
- [AWS 배포](#aws-배포)
- [API](#api)
- [프로젝트 구조](#프로젝트-구조)
- [보안과 안전장치](#보안과-안전장치)
- [주요 제약](#주요-제약)
- [회고](#회고)
- [관련 문서](#관련-문서)

---

## 시연 영상

[![사내 지식 RAG·Text2SQL MCP 챗봇 시연 영상](https://img.youtube.com/vi/8LOiReSEG5Q/maxresdefault.jpg)](https://youtu.be/8LOiReSEG5Q)

**▶️ 이미지를 클릭하면 유튜브에서 시연 영상이 재생됩니다**

---

## 팀 소개

<table>
  <tr>
    <td align="center" width="220"><img src="docs/assets/team/문동원.png" width="100" height="100" style="object-fit: cover;" alt="문동원"/></td>
    <td align="center" width="220"><img src="docs/assets/team/박회종.png" width="100" height="100" style="object-fit: cover;" alt="박회종"/></td>
    <td align="center" width="220"><img src="docs/assets/team/이태혁.png" width="100" height="100" style="object-fit: cover;" alt="이태혁"/></td>
    <td align="center" width="220"><img src="docs/assets/team/이호원.png" width="100" height="100" style="object-fit: cover;" alt="이호원"/></td>
  </tr>
  <tr>
    <td align="center"><b>문동원</b></td>
    <td align="center"><b>박회종</b></td>
    <td align="center"><b>이태혁</b></td>
    <td align="center"><b>이호원</b></td>
  </tr>
  <tr>
    <td align="center"><b>Front-End</b></td>
    <td align="center"><b>PM · AWS · Django</b></td>
    <td align="center"><b>RAG-Test · WebSearching</b></td>
    <td align="center"><b>ERP-Chatbot</b></td>
  </tr>
  <tr>
    <td align="center"><b>https://github.com/greenmdw</b></td>
    <td align="center"><b>https://github.com/1jelly7</b></td>
    <td align="center"><b>https://github.com/kiri5358</b></td>
    <td align="center"><b>https://github.com/coreawon09</b></td>
  </tr>
</table>

---

## 프로젝트 개요

### 문제 정의

사내 정보는 두 곳에 나뉘어 있습니다.

- **규정·정책·매뉴얼** → 문서(PDF)
- **매출·구매액·미수금** → 데이터베이스

기존 방식에서는 사용자가 **문서의 위치를 알거나 SQL을 쓸 줄 알아야** 원하는 답을 찾을 수
있었습니다. "구매 규정과 올해 공급업체별 구매액을 비교해줘" 같은 복합 질문은 두 시스템을
오가며 사람이 직접 조합해야 했습니다.

### 해결 방식

1. 질문이 문서·데이터·복합 질문 중 무엇인지 판단합니다.
2. 필요한 정보원만 **MCP Tool 경계**로 조회합니다.
3. 수집된 근거의 관련성·충분성·충돌 여부를 검사합니다.
4. **검증된 근거만** LLM에 전달해 답변을 생성합니다.
5. 답변과 함께 문서 출처, 표, 차트, 캐시 여부를 반환합니다.

### 설계 원칙

| 원칙 | 구현 |
|---|---|
| **환각 방지가 최우선** | 근거 없는 사실은 답하지 않고, 부족하면 부족하다고 명시 |
| **직접 접근 금지** | FastAPI·LangGraph는 파일·FAISS·업무 MySQL에 직접 접근하지 않고 MCP Tool 경계만 사용 |
| **최소 권한** | 4개 DB(계정·문서·판매·구매)를 분리하고 도메인별 읽기/쓰기 계정을 나눔 |
| **부탁이 아닌 강제** | LLM에게 규칙을 "부탁"하지 않고 뷰·권한·코드로 어길 수 없게 만듦 |

### WBS (개발 Time Line)

**2026-08-24 (월) ~ 2026-08-027 (목) · 4일**

| 일자         | 요일 | 주요 작업                     | 산출물             |
|------------|----|---------------------------|-----------------|
| 2026-08-24 | 월  | 데이터량 증가, 기존프로젝트 결과물 버그 수정 | 증가 데이터, 프로젝트 토대 |
| 2026-08-25 | 화  | RAG 검색 평가 파이프라인 점검(Ground Truth 라벨링, LLM Judge 실패 복구), 테스트 계획 및 결과 보고서 작성 | qrels(라벨링 결과) CSV, RAG 검색평가 테스트계획 및 결과 보고서 |
| 2026-08-26 | 수  | 대시보드 백엔드 API 구현(월별 매출/구매 추이), Nginx 게이트웨이 라우팅 이슈 해결, 시스템 구성도·README 정리 | 월별 추이 API, 시스템 구성도, README 최종본 |
| 2026-08-27 | 목  | 발표 자료 제작                  | 발표 자료 · 문서 정리   |

---

## 이번 프로젝트에서 새로 추가된 기능

이전 이터레이션 대비 이번 프로젝트에서 새로 붙은 부분입니다.

| 기능                     | 내용                                                                             | 상태 |
|------------------------|--------------------------------------------------------------------------------|-|
| **이상탐지 대시보드**          | 매출·구매 데이터의 이상 거래(급증·연체·이상치)를 고정 SQL(LLM 미개입)로 탐지해 표시                           | GUI 리뉴얼 진행 완료 |
| **월별 매출/구매 추이 API**    | 대시보드 차트용 올해 월별 합계 + 평균±2표준편차 이상치 플래그                                           | `GET /api/dashboard/monthly-trends` 완료 |
| **RAG 검색 품질 평가 파이프라인** | 질문 100건 × 후보 30개 LLM 관련성 라벨링(qrels) → Recall@k·Precision@k·MRR·nDCG 측정         | 라벨링·1차 지표 측정 완료, golden set 사람 검토는 진행 예정 |
| **문서 이미지,표 캡셔닝**      | Docling 기술을 사용하여 pdf 안에 들어있는 이미지 캡셔닝 기능 추가 및 pdf 뿐만이 아닌 png, csv 등의 다른 데이터도 파싱 | PDF 이미지 캡셔닝은 구현 완료(`ingestion/loaders.py`의 `load_pdf_docling()`), 다만 `enable_docling_captioning` 기본값이 `False`라 평소엔 꺼져 있음. png/csv 등 비-PDF 파싱은 아직 미착수 |
---

## 데이터
회사의 ERP 시스템을 재현하기 위해 **공공기관 사내 규정 자료**와 **Kaggle의 가상 기업 ERP 데이터**를 활용했으며 기존 데이터에서 더 많은 데이터를 적용하기 위해 erp 데이터를 5년치 데이터로 데이터를 증가시켰다.

| 구분 | 출처                                                                                                                                               | 활용 내용 | 규모                            |
|---|----------------------------------------------------------------------------------------------------------------------------------------------------|---|-------------------------------|
| 사내 규정 문서 | [LH E&S 규정·지침 게시판](https://www.lhes.co.kr/bbs/board.php?bo_table=comm05)                                                                    | 사내 규정·업무 지침 PDF를 벡터화해 RAG 기반 지식 검색 | PDF 10건 → **381 청크**          |
| ERP (Sales DB) | [Kaggle · ERP System Modules & Tables Dependency](https://www.kaggle.com/datasets/moutasmtamimi/dataset-erp-system-modules-tables-dependency/data) | 고객·주문·송장·배송 데이터를 정제해 Text2SQL 질의응답 | 주문 **800건** / 5년치             |
| ERP (Purchase DB) | [Kaggle · ERP System Modules & Tables Dependency](https://www.kaggle.com/datasets/moutasmtamimi/dataset-erp-system-modules-tables-dependency/data)                                                                                                                                               | 구매요청·발주·공급업체·입고·송장 데이터를 정제해 Text2SQL 질의응답 | 발주 **250건** · 발주상세 **614건**(평균 2.46줄/발주) · 공급업체 **25곳** · 청구서 **141건** · 입고 **141건** / 5년치(2021-08~2026-08) |

---

## 사용 예시

기본 채팅(문서/데이터/복합 질문 분류와 역할별 접근 제어)은 [핵심 구현](#핵심-구현)에서 다룹니다.
여기서는 **이번 프로젝트에서 새로 추가된 기능**을 실제로 어떻게 켜보고 확인하는지 정리합니다.

### 1. 이상탐지 대시보드

1. `admin` 또는 `finance` 역할로 로그인합니다. 상단 "대시보드" 탭은 이 두 역할에게만
   보입니다(`DASHBOARD_ROLES = ['admin', 'finance']`, `hr`는 tab 자체가 숨겨짐).
2. 대시보드 진입 시 KPI 카드(이번 달 매출/구매, 연체 미수·미지급금, 이번 달 감지된 이상
   신호 건수), 월별 매출·구매 추이 차트, 이상거래 카드(발주번호/거래처/품목·근거·심각도)가
   표시됩니다.
3. 추이 차트에서 **빨간 점으로 표시된 달**이 이상치입니다 — 해당 연도 월별 합계의
   평균 대비 **±2표준편차를 벗어난 달**로 판정합니다.
4. 새로고침/재방문마다 즉시 다시 계산됩니다(별도 push 없이 페이지 로드마다 재조회).

### 2. 월별 매출/구매 추이 API (대시보드 차트가 사용하는 원본 데이터)

```
GET /api/dashboard/monthly-trends?year=2026
```

```json
{
  "sales_trend": [
    { "period": "1월", "value": 431000000.0, "is_anomaly": false },
    { "period": "2월", "value": 980000000.0, "is_anomaly": true }
  ],
  "purchase_trend": [ ... ]
}
```

`year`를 생략하면 올해 기준으로 조회합니다. LLM/Text2SQL을 거치지 않고 고정 SQL로만
동작해 응답이 빠르고, 매 호출마다 최신 값을 다시 계산합니다.

### 3. RAG 검색 품질 평가 파이프라인

```powershell
# 1) 질문셋 → 하이브리드 검색 후보 30개 → LLM Judge 0~3점 라벨링
python scripts/rag_ground_truth_label.py data/rag_eval/question.csv data/rag_eval/qrels_draft.csv

# 2) API 실패(RateLimitError 등)로 판정 못 한 건만 재판정 (검색은 다시 안 함)
python scripts/retry_failed_judgments.py data/rag_eval/qrels_draft.csv data/rag_eval/qrels_retried.csv

# 3) 확정된 qrels로 Recall@k · Precision@k · MRR · nDCG@k 산출
python scripts/rag_eval_metrics.py data/rag_eval/qrels_retried.csv --relevance-threshold 2
```

세 번째 명령의 콘솔 출력이 [품질 검증 → RAG 검색 평가](#rag-검색-평가-qrels-기반) 섹션 수치의
근거입니다. 전체 방법론·이슈 이력·한계점은
[RAG 검색평가 테스트계획 및 결과 보고서](docs/assets/RAG_검색평가_테스트계획및결과보고서.pdf)를
참고하세요.

### 4. 문서 이미지·표 캡셔닝 (Docling)

기본은 꺼져 있습니다(`ENABLE_DOCLING_CAPTIONING=false`). 켜서 확인하려면:

```env
ENABLE_DOCLING_CAPTIONING=true
OPENAI_API_KEY=<발급받은 키>
```

```powershell
python scripts/verify_docling.py <PDF 경로>
```

이 스크립트는 챗봇 질문이나 RAG 검색을 거치지 않고 "Docling+비전 캡셔닝이 이미지에서
캡션을 실제로 뽑아내는가"만 단독으로 확인합니다. 켠 뒤 문서를 다시 인덱싱하면, PDF 안
이미지에 달린 캡션도 검색 대상 텍스트에 포함됩니다. 변환 중 예외가 나도 재인덱싱 전체가
멈추지 않고 기존 pypdf 경로로 자동 폴백합니다.

---

## 시스템 아키텍처

<div align="center">
  <img src="docs/assets/system_architecture_diagram.png" alt="시스템 아키텍처" width="100%">
</div>

브라우저는 Nginx 게이트웨이(`:8000`) 하나만 바라봅니다. Nginx는 경로별로 Django(`:8001`)와
FastAPI(`:8002`)에 요청을 나눠 보냅니다.

- **Django**: 사용자 UI, 계정/세션/로그인, Django Admin
- **FastAPI**: 채팅 API, LangGraph 오케스트레이션, 답변 캐시(프로세스 내 메모리), MCP Client
- **MCP Tool 서비스**: 문서 검색(FAISS)과 구매·판매 Text2SQL을 같은 프로세스 안에서 호출

새 경로를 Nginx에 추가할 때는 반드시 `deploy/nginx/local.conf`의 catch-all
(`location ^~ /api/ { return 404; }`)보다 먼저 매치되는 구체적인 `location` 블록을 등록해야
합니다. 등록하지 않으면 FastAPI를 직접(`:8002`) 호출할 때는 정상 응답하지만, 게이트웨이
(`:8000`)를 거치면 404가 반환되는 문제가 생깁니다 — 이번 프로젝트에서 실제로 겪은 문제입니다
(아래 [기술적 도전과 해결](#기술적-도전과-해결) 참고).

### BOTH 경로는 병렬로 실행됩니다

문서 검색과 데이터 조회는 서로 다른 상태 키(`document_evidence`, `database_evidence`)에만
기록하므로 순차로 기다리지 않고 두 노드를 동시에 시작하며, Evidence Eval이 둘 다 끝난 뒤
한 번만 합류시킵니다.

```
[순차]  document ──▶ database ──▶ evidence      총 시간 = A + B
[병렬]  document ──┐
        database ──┴──▶ evidence                총 시간 = max(A, B)
```

---

## 핵심 구현

### 문서 RAG 흐름

```text
문서 DB의 활성 문서 경로 조회
  → 등록 경로의 PDF/TXT/Markdown 로드
  → 질문 임베딩 (sentence-transformers)
  → FAISS 벡터 검색 + 어휘 하이브리드 검색
  → 관련 문서 조각 병합
  → 내부 file_path를 제거한 출처 반환
```

### Text2SQL 흐름과 4겹 안전장치

```text
자연어 질문
  → 뷰·지표 정의를 스키마로 제공        [시맨틱 레이어]
  → LLM이 SQL 생성
  → ① 정적 검사 (SELECT · 허용 뷰 · LIMIT)
  → ② EXPLAIN 사전검증 → 실패 시 1회 재작성
  → ③ 조회 전용 계정으로 실행
  → ④ 뷰가 업무 규칙을 강제
  → 행 · SQL · metadata 반환
```

| # | 안전장치 | 막는 것 | 구현 |
|---|---|---|---|
| ① | 정적 SQL 가드 | 다중 문장 · 쓰기 명령 · 허용 밖 테이블 · 과대 LIMIT | `sql_guard.py` |
| ② | EXPLAIN 사전검증 | 문법 오류 · 존재하지 않는 컬럼 | `mysql.py` |
| ③ | 조회 전용 계정 | 코드 버그로도 원본 테이블 접근 불가 | reader 계정 |
| ④ | 시맨틱 뷰 | 취소 주문 포함 · fan-out 중복 합산 · PII 노출 | `views.sql` |

**핵심 아이디어**: LLM에게 "취소 주문은 빼주세요"라고 **부탁**하는 대신, 뷰에서 취소 주문을
**아예 안 보이게** 만들어 어길 방법 자체를 없앴습니다.

### 이상탐지 · 대시보드 API 설계

이상탐지와 월별 추이는 **LLM/Text2SQL을 거치지 않습니다.** 질문마다 SQL을 새로 생성하는 대신,
`sales_reader`/`purchase_reader` 계정으로 미리 검증한 고정 SQL만 실행합니다 — 대시보드처럼
매 페이지 로드마다 반복 조회되는 경로는 속도와 안전성이 더 중요하기 때문입니다. 한쪽 도메인
조회가 실패해도 다른 쪽은 정상 반환되도록 `asyncio.gather(..., return_exceptions=True)`로
격리합니다.

### RAG 검색 품질 평가 방법론

질문마다 하이브리드 검색으로 상위 30개 후보를 모으고, 각 (질문, chunk) 쌍을 LLM Judge가
0~3점으로 채점해 qrels(정답지)를 만듭니다. 이 정답지를 기준으로 Recall@k·Precision@k·MRR·
nDCG@k를 계산합니다.

| 점수 | 판정 기준 |
|---|---|
| 0 | 질문의 답이나 근거와 무관 |
| 1 | 같은 주제지만 답하기엔 부족 |
| 2 | 중요한 부분을 답하지만 조건·예외 부족 |
| 3 | 이 chunk만으로 신뢰할 수 있는 답변 근거 |

---

## 품질 검증

### 자동화 테스트

```powershell
.venv\Scripts\python.exe -m pytest
```

**결과: 402 passed · 27 skipped**

기본 unit/integration 테스트는 fake/mock 중심입니다. 실제 MySQL, 원격 MCP, 운영 FAISS까지
검증했다는 의미는 아니며, 외부 서비스 검증은 opt-in 테스트(`RUN_LOCAL_MYSQL_TESTS=1`)로 별도
수행합니다.

### 적대적 테스트

```powershell
python scripts/adversarial_eval.py --verbose
```

```text
(.venv) PS C:\project_file\project_test> python scripts/adversarial_eval.py --verbose
적대적 평가 — 케이스 28건

[1] 라우팅 계층
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Loading weights: 100%|███████████████████████████████████████████████████████████████████████████████████████| 199/199 [00:00<00:00, 3762.69it/s]
    27/28 통과 (96%)
    실패 유형: 거짓전제×1
      [거짓전제] 연차가 30일인 게 맞나요
        기대=DOCUMENT 실제=GENERAL

[2] 검색 계층 (chunk=560, top_k=10, 임계값=0.58, 벡터+어휘 하이브리드)
    19/28 통과 (68%)
    실패 유형: 거짓전제x2, 다중홉x1, 띄어쓰기x1, 어휘격차x3, 오타x1, 줄임말x1
    관련 질문 최저점: 0.449 / 무관 질문 최고점: 0.567
    → 관련/무관 점수대가 겹칩니다. 임계값만으로는 분리 불가.
      [띄어쓰기] 취업 규 칙 알려줘
        기대문서=취업규칙 / top_k 밖 / 1위='인사규정 시행세칙[2026.05.' 0.569[vector]
      [줄임말] 법카 한도 얼마야
        기대문서=법인카드 / top_k 밖 / 1위='계약업무처리 지침[2026.06.' 0.413[vector]
      [오타] 취업규책 알려줘
        기대문서=취업규칙 / 기대문서 2위 0.572[vector]
      [어휘격차] 징계 받으면 어떻게 되나요
        기대문서=취업규칙 / top_k 밖 / 1위='임직원 행동강령(2025.12.1' 0.659[vector]
      [어휘격차] 출장비 정산 방법
        기대문서=회계규정 / 기대문서 9위 0.533[vector]
      [어휘격차] 경조사비 얼마 나와?
        기대문서=복지후생 / 기대문서 1위 0.552[vector]
      [다중홉] 계약 담당자가 지켜야 할 회계 절차
        기대문서=계약업무 / top_k 밖 / 1위='회계규정[2025.12.16. 개' 0.656[vector]
      [거짓전제] 법인카드 한도가 500만원 맞지?
        기대문서=법인카드 / 기대문서 1위 0.449[vector]
      [거짓전제] 연차가 30일인 게 맞나요
        기대문서=취업규칙 / 기대문서 1위 0.497[vector]

[3] 방어 계층
    PASS  출처에 내부 경로 미노출
    PASS  LLM 컨텍스트에 내부 경로 미노출
    PASS  문서 본문 인젝션 무력화

총계: 49/59 (83%)
```

검색 계층 미통과 9건 중 상당수(어휘격차 3건, 거짓전제 2건)는 **관련 문서가 top_k 밖으로
완전히 밀려난 게 아니라 순위권 안에 있는데도 임계값(0.58)에 못 미친** 경우입니다. 관련
질문 최저점(0.449)이 무관 질문 최고점(0.567)보다 낮아 **점수대가 서로 겹치기 때문에,
임계값을 조정하는 것만으로는 두 그룹을 깔끔히 분리할 수 없습니다.** 특히 "취업 규 칙"처럼
단어 사이에 공백이 새로 끼는 케이스와 "법카"·"징계" 같은 줄임말/어휘격차 케이스가 반복적으로
실패하는 걸 보면, 임베딩 자체보다는 **청킹 단위와 어휘 정규화 전략**을 다음 개선 대상으로
보는 게 맞아 보입니다. 방어 계층은 3/3(100%) 전부 통과해, 내부 경로 노출과 프롬프트
인젝션은 안전하게 차단되고 있습니다.

### RAG 검색 평가 (qrels 기반)

질문 100건 × 하이브리드 검색 후보 30개를 LLM Judge가 0~3점으로 채점해 qrels(정답지)를
만들고, 이를 기준으로 Recall@k·Precision@k·MRR·nDCG@k를 측정했습니다. 자세한 절차·이슈
발생 이력·한계점은 [RAG 검색평가 테스트계획 및 결과 보고서](docs/assets/RAG_검색평가_테스트계획및결과보고서.pdf)에
정리되어 있고, 아래는 핵심 수치 요약입니다.

| 지표 | threshold=2 (rubric 기본값) | threshold=1 (완화 기준) |
|---|:---:|:---:|
| Recall@5 | 0.410 | 0.760 |
| Precision@5 | 0.138 | 0.450 |
| Recall@10 | 0.460 | 0.790 |
| nDCG@5 / @10 | 0.499 / 0.520 | 0.499 / 0.520 (threshold 무관) |
| MRR | 0.304 | 0.683 |
| 정답 후보 0개인 질문 | 50 / 100 | 19 / 100 |

검색기 자체는 "주제 관련성" 기준(threshold=1)으로는 Recall@5 0.76으로 양호하지만,
rubric 권장 기준(threshold=2, "이 chunk 하나만으로 완결된 답변 가능")으로는 절반 수준으로
떨어집니다 — 청킹 단위가 작아 하나의 답이 여러 chunk에 걸쳐 나뉘어 있을 가능성을 시사하며,
위 적대적 테스트의 청킹 전략 개선 필요성과도 같은 방향을 가리킵니다. 100건 중 19건은
threshold와 무관하게 정답 후보가 아예 없어, 검색 실패인지 문서 커버리지 부재인지 원문
확인이 다음 과제로 남아 있습니다. 라벨(2점·3점 및 애매 사례)에 대한 사람 검토·golden set
확정은 아직 진행 전입니다.
---

## 기술적 도전과 해결

### 1. pymysql의 `%` 이스케이프와 MySQL 계정 호스트 와일드카드 충돌

**상황** — `setup_all.py`로 MySQL 계정을 생성하는 중 `ValueError: unsupported format character`가
발생했습니다.

**원인** — pymysql은 매개변수(`%s`) 치환에 파이썬 구식 `%`-포매팅을 그대로 쓰는데, `CREATE
USER`/`ALTER USER`에 넘기는 호스트 값의 와일드카드 `%`가 이 포매팅 문법과 충돌했습니다.

**해결** — 매개변수가 있는 `CREATE USER`/`ALTER USER`에서만 `%`를 `%%`로 이스케이프하고,
매개변수가 없는 `GRANT`는 원래대로 단일 `%`를 쓰도록 분리했습니다. 실제 pymysql 이스케이프
함수로 따옴표 포함 비밀번호까지 재현·검증했습니다.

### 2. 재시도 후에도 실패한 LLM 판정이 "진짜 무관"과 구분되지 않던 문제

**상황** — RAG 평가용 qrels를 만들 때, 후보 30개를 세마포어 없이 동시 호출했더니
`RateLimitError`가 대량 발생했고, 실패한 판정이 전부 조용히 0점으로 기록돼 "진짜 무관"과
"그냥 호출 실패"가 구분되지 않았습니다.

**해결** — `asyncio.Semaphore` + 지수 백오프 재시도를 추가해 실패율을 크게 낮췄습니다. 그래도
재시도 5회를 소진하는 건이 일부(약 5%) 남아, 실패 사유를 reason 필드에 명시적으로 남기도록
했습니다. 검색 단계(임베딩+FAISS)를 다시 돌리지 않고, 이미 알고 있는 chunk_id로 원문만 조회해
실패 건만 재판정하는 별도 스크립트로 100% 회수했습니다.

### 3. Nginx catch-all에 새 API 경로가 걸리는 문제

**상황** — 새 대시보드 API를 FastAPI에 추가했는데, `:8002`(FastAPI 직접)로는 정상 응답하고
`:8000`(Nginx 게이트웨이)으로는 404가 났습니다.

**원인** — `deploy/nginx/local.conf`는 알려지지 않은 `/api/*` 요청이 Django page route로
새지 않도록 마지막에 `location ^~ /api/ { return 404; }`catch-all을 둡니다. 새 경로용
`location` 블록을 등록하지 않으면 이 catch-all에 걸립니다.

**해결** — 기존 `/api/reports`, `/api/anomalies` 블록과 동일한 패턴으로 `location = /api/dashboard`,
`location ^~ /api/dashboard/` 블록을 추가했습니다. `proxy_pass`에 후행 슬래시를 붙이면 nginx가
매치된 경로를 치환해버려 FastAPI가 다른 이유로 다시 404를 낸다는 점도 함께 확인했습니다
(경로는 슬래시 없이 그대로 전달해야 `main.py`의 `prefix="/api"` 라우터와 맞음).

### 4. 프론트가 먼저 스펙을 정하고 백엔드가 뒤따라가는 개발 순서

**상황** — GUI 담당 팀원이 대시보드 화면을 더미 데이터로 먼저 완성했고, 백엔드는 그 더미
데이터의 필드 모양(`sales_trend`/`purchase_trend`, `period`/`value`/`is_anomaly`)에 맞춰
API를 만들어야 했습니다.

**해결** — 정식 스펙 문서가 아직 없는 상태였지만, `dashboard.js`의 더미 데이터 구조 자체를
사실상의 계약(contract)으로 보고 필드명을 정확히 맞춰 구현했습니다. 이렇게 하면 프론트 쪽
수정 없이 `fetchDashboardData()` 내부의 더미 반환값만 실제 fetch 호출로 바꾸는 것으로 연결이
끝납니다.

---

## 기술 스택

| 영역 | 기술 | 역할 |
|---|---|---|
| Runtime | Python 3.11 | API · Agent · MCP · ETL 실행 |
| Backend (UI/Auth) | Django | 사용자 UI, 계정·세션, Admin |
| Backend (API/AI) | FastAPI, Pydantic | 채팅 API, 요청·응답 검증 |
| Gateway | Nginx | 단일 공개 주소 경로 라우팅 |
| LLM | OpenAI SDK | 의미 라우팅 · Text2SQL · 답변 생성 · RAG 관련성 판정 |
| Orchestration | LangGraph | 조건 분기 · 병렬 분기 · 상태 전달 |
| Tool boundary | MCP | 문서·구매·판매 기능 분리 |
| RAG | FAISS, sentence-transformers | 문서 검색 |
| Database | MySQL 8.0 | 계정 · 문서 경로 · 구매 · 판매 |
| Cache | In-memory (프로세스 내 TTL 캐시) | 검증된 답변 재사용. `RedisCache`는 인터페이스만 정의된 미구현 스텁 |
| Frontend | HTML, CSS, JavaScript, Chart.js | 채팅 · 대시보드 · 표 · 차트 UI |
| Test | pytest, pytest-asyncio, httpx | 단위·통합·Django 계약 검증 |

---

## 빠른 시작

### 사전 요구사항

- Python 3.11과 `venv`
- MySQL 8.0
- Nginx (Python 의존성이 아니므로 별도 설치, `PATH`에서 `nginx` 명령 실행 가능해야 함)
- 실제 LLM 사용 시 OpenAI API 키

### 1. 환경 준비

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`DJANGO_SECRET_KEY`와 `AUTH_INTROSPECTION_KEY`는 서로 다른 값으로, 충분히 긴 난수로
생성합니다.

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48)); print(secrets.token_urlsafe(48))"
```

### 2. 통합 초기화

```powershell
.venv\Scripts\python.exe setup_all.py --apply
```

문서 또는 특정 도메인을 아직 준비하지 않았다면 해당 단계를 생략합니다.

```powershell
.venv\Scripts\python.exe setup_all.py --apply --skip-documents --skip-purchase
```

### 3. 로컬 게이트웨이 실행

```powershell
.\scripts\local_gateway.ps1
```

Django 설정 검사 → `collectstatic` → Nginx 설정 검사 → Django(`:8001`) →
FastAPI(`:8002`) → Nginx(`:8000`) 순으로 기동합니다. 상태 확인·재시작·종료도 같은 스크립트를
씁니다.

```powershell
.\scripts\local_gateway.ps1 status
.\scripts\local_gateway.ps1 restart
.\scripts\local_gateway.ps1 stop
```

브라우저에서 `http://127.0.0.1:8000/`으로 접속합니다. `127.0.0.1:8001`/`:8002`는 장애 진단용
upstream 주소일 뿐, 정상 사용자 접속 경로가 아닙니다.

---

## AWS 배포

로컬 개발 구성([빠른 시작](#빠른-시작))은 3개 프로세스(Django·FastAPI·Nginx)를 개별 실행하는
방식이라, 그 구조를 그대로 단일 EC2 인스턴스의 **systemd 서비스**로 옮기는 배포 방식을
채택했습니다. 아래에서 이 선택의 근거, 서버 스펙, 네트워크 구성, 배포 절차 순으로 정리합니다.

### 배포 방식 선정

| 방식 | 장점 | 이 프로젝트에서의 문제 |
|---|---|---|
| Docker Compose | 환경 재현성, 배포 스크립트 표준화 | 2GiB RAM에서 Docker 데몬 + 컨테이너별 베이스 이미지 오버헤드가 부담. MySQL·임베딩 모델까지 올리면 여유가 크지 않음 |
| **네이티브(systemd) — 채택** | 오버헤드 없이 가용 메모리를 앱에 온전히 사용, 기존 `local_gateway.ps1` 구조를 그대로 이식 가능 | 서버 간 이식성은 Docker보다 낮음 — 지금은 단일 인스턴스라 문제 없음 |
| RDS(MySQL 분리) | 백업 자동화, 수평 확장 | 지금 데이터 규모(발주 250건 등)엔 과함 · 비용과 네트워크 왕복만 늘어남 |
| **로컬 MySQL(동일 인스턴스) — 채택** | 추가 비용·네트워크 지연 없음 | 인스턴스 장애 시 DB도 함께 영향받음 — 트래픽이 늘면 RDS 분리를 재검토 |

**메모리가 빠듯하다는 전제 하에 오버헤드를 최소화하는 쪽을 우선했습니다.** 트래픽이 늘거나
다중 인스턴스로 확장할 시점이 오면 Docker + RDS로 전환하는 걸 다음 단계로 남겨둡니다.

### 네트워크 접근 방식 선정

| 방식 | 장점 | 이 프로젝트에서의 문제 |
|---|---|---|
| 도메인 공개형(퍼블릭 도메인 + `0.0.0.0/0` 오픈) | 접근이 가장 간편, 어디서든 바로 접속 | 매출·구매·HR 데이터를 다루는 **사내용** 툴을 인터넷 전체에 노출 — 이 프로젝트가 강조해온 "최소 권한·직접 접근 금지" 철학과 상충 |
| Private IP 전용(회사 내부망 취급) | 인터넷 노출이 전혀 없어 가장 안전 | 실제 사내망이 VPN Gateway/Direct Connect로 이 VPC에 연결돼 있어야 성립. 학습 프로젝트라 그런 물리적 내부망 자체가 없어 접속 방법이 없음 |
| **퍼블릭 IP + SSL VPN(WireGuard) — 채택** | 앱(:443)은 인터넷에 직접 노출되지 않고 VPN 터널을 통과해야만 도달 가능. 실제 사내망 없이도 "가상의 내부망" 효과 | VPN 클라이언트 설정이 한 단계 더 필요(팀원·평가자가 WireGuard 설치 필요) |

애플리케이션 계층 RBAC(역할별 DB 접근 통제)에 **네트워크 계층 통제**를 한 겹 더 얹는
구조입니다. WireGuard는 OpenVPN보다 가볍고(커널 기반) AWS Client VPN처럼 연결
시간당 과금도 없어, 2GiB RAM 인스턴스에 부담 없이 앱과 같은 인스턴스에 올릴 수 있습니다.

### 서버 스펙

| 항목 | 값 |
|---|---|
| 인스턴스 유형 | `t3.small` |
| vCPU | 2개 |
| RAM | 2GiB |
| AMI | Ubuntu Server 24.04 LTS |
| 스토리지 볼륨 타입 | gp3 |
| 스토리지 용량 | 30GiB |

> **2GiB RAM 제약에 대한 대응**: MySQL(`innodb_buffer_pool_size`를 128MB로 명시 축소) +
> Django/FastAPI(각 프로세스 worker 1개) + 임베딩 모델을 함께 올리면 여유가 크지 않습니다.
> 스왑 2GB를 안전망으로 추가하고, `ENABLE_DOCLING_CAPTIONING`은 운영에서도 기본값(`false`)을
> 유지할 것을 권장합니다(레이아웃 모델 로딩이 메모리 부담을 더함). 실사용 중 메모리 압박이
> 관측되면 `t3.medium`으로 올리는 걸 우선 검토합니다.

### AWS 네트워크 구성도

<div align="center">
  <img src="docs/assets/aws 구성도.png" alt="AWS 네트워크 구성도" width="100%">
</div>

- **애플리케이션(Nginx `:443`)은 인터넷에 직접 노출되지 않습니다.** 인터넷에 공개된 건
  VPN 서버(WireGuard, UDP `51820`)뿐이고, `443`/`80`은 **VPN 터널 인터페이스(`wg0`)에만
  바인딩**해 VPN을 통과한 트래픽만 받습니다.
- **보안 그룹**은 `51820/udp`(WireGuard, `0.0.0.0/0`)만 공개로 열고, `22`(SSH)도
  공개 인바운드에서 제거해 **VPN 터널을 통해서만 접속**하도록 통일했습니다.
- Django(`:8001`)와 FastAPI(`:8002`)는 기존과 동일하게 `127.0.0.1`에만 바인딩해 Nginx를
  거치지 않은 직접 접근이 불가능합니다.
- **MySQL도 `127.0.0.1`에만 바인딩**해 인스턴스 외부에서는 접근할 수 없습니다.
- 아웃바운드는 OpenAI API 호출과 패키지 설치(`apt`/`pip`)를 위해 전체 허용합니다.
- TLS 인증서는 `443`이 공개로 열려 있지 않아 Let's Encrypt의 기본 HTTP-01 방식이 안 되므로,
  도메인이 있다면 **DNS-01 챌린지**로 발급하거나, 어차피 VPN으로 신뢰된 사용자만 접근하므로
  **자체 서명 인증서**로도 충분합니다.

### 배포 계획

아직 실제 배포는 진행하지 않은 단계이며, 아래는 위 결정들을 실행에 옮길 때 따르기로 한
방침입니다.

- **인스턴스·네트워크**: 위 스펙으로 EC2를 만들고 **Elastic IP**를 붙여 VPN 서버 주소가
  재시작 후에도 바뀌지 않게 합니다. 보안 그룹은 처음부터 `51820/udp`(WireGuard)만
  `0.0.0.0/0`으로 열고, `22`/`80`/`443`은 보안 그룹 단계에서부터 아예 공개 인바운드에
  포함하지 않습니다.
- **VPN 우선 구성**: 애플리케이션을 올리기 전에 WireGuard부터 구성합니다. 서버 키 쌍을
  만들고 `wg0` 인터페이스에 내부 대역(`10.8.0.0/24` 등)을 할당한 뒤, `iptables`로
  `wg0`에서 들어온 트래픽만 `443`/`80`/`22`에 도달하도록 제한합니다. 팀원·평가자 몫의
  클라이언트 키는 이 시점에 미리 발급해 배포합니다.
- **애플리케이션 배치**: 저장소를 clone하고 `venv` + `pip install -r requirements.txt`,
  `.env`에 운영 값(`DJANGO_SECRET_KEY`, `AUTH_INTROSPECTION_KEY`, `OPENAI_API_KEY` 등)을
  채운 뒤 `python setup_all.py --apply`로 DB·계정·문서 인덱스·ETL을 한 번에 준비합니다.
- **프로세스 관리**: Django(gunicorn)·FastAPI(uvicorn)를 systemd 서비스로 등록해 부팅 시
  자동 시작되게 하고, 메모리를 아끼기 위해 둘 다 worker 1개로 제한합니다.
- **Nginx/TLS**: `deploy/nginx/local.conf`를 기반으로 `listen`을 `wg0`의 내부 IP에만
  바인딩하도록 바꾸고, 도메인이 있으면 DNS-01로, 없으면 자체 서명 인증서로 TLS를
  적용합니다.
- **자원 안전망**: 2GB 스왑 파일을 추가해두고, 배포 직후 `systemctl status`로 4개
  서비스(Django·FastAPI·Nginx·WireGuard)가 모두 정상인지, VPN 없이는 `443`이 실제로
  열리지 않는지를 반드시 외부에서 재확인합니다.

---

## API


| Method | Endpoint | 설명 | 인증 |
|---|---|---|---|
| `POST` | `/api/auth/login` | 로그인과 세션 쿠키 발급 | 불필요 |
| `POST` | `/api/auth/logout` | 활성 세션 폐기 | 필요 |
| `GET` | `/api/auth/me` | 현재 사용자·역할 조회 | 필요 |
| `POST` | `/api/chat` | 질문 처리 | 필요 |
| `GET` | `/api/documents/download?doc_id=...` | 등록 문서 원문 다운로드 | 필요 |
| `GET` | `/api/reports/templates` | 리포트 템플릿 목록 | 필요 |
| `POST` | `/api/reports/generate` | 리포트(.docx) 생성 | 필요 |
| `GET` | `/api/anomalies` | 이상탐지 결과 (TEMP, 대시보드 리뉴얼 후 교체 예정) | 필요 |
| `GET` | `/api/dashboard/monthly-trends?year=` | 올해(또는 지정 연도) 월별 매출/구매 추이 | 필요 |
| `GET` | `/api/health` | 프로세스 생존 확인 | 불필요 |

```json
{ "question": "2026년 고객별 매출을 알려줘" }
```

주요 응답 필드는 `answer`, `sources`, `tables`, `cached`, `route`, `evidence_status`,
`request_id`입니다. **내부 evidence와 파일 경로는 공개 응답 모델에 포함하지 않습니다.**

---

## 프로젝트 구조

```text
django_app/           사용자 UI, 계정, 인증 API, Django Admin, DB migration
app/                  FastAPI 채팅·문서·리포트·대시보드 API, LangGraph, 캐시, MCP client
shared/               Django와 FastAPI가 공유하는 역할 정책
mcp_servers/
  document_tools/     문서 DB, 파일 로드, FAISS 검색, 다운로드 해석
  data_tools/         구매·판매 Text2SQL과 읽기 전용 조회
ingestion/            문서 로드, 청킹, 임베딩, FAISS 인덱싱
etl/
  purchase/           구매 ETL
  sales/              판매 ETL
database/             계정·문서·구매·판매 DDL과 조회 뷰
deploy/nginx/         로컬 게이트웨이 설정
scripts/              계정·문서·인덱스·데이터 배치 진입점, RAG 평가 도구
tests/                unit, integration, django 계약 테스트
docs/                 아키텍처, 인터페이스, 소유권, 테스트 문서
```

---

## 보안과 안전장치

- 세션은 Django HttpOnly 서버 세션 쿠키(`SameSite=Lax`)로 관리
- RBAC는 UI가 아니라 **API와 MCP/DB 경계에서 재검사**
- 문서 다운로드는 임의 경로 대신 **등록된 `document_id`만** 허용
- Data MCP는 **허용된 뷰와 단일 SELECT만** 실행
- SQL 주석 · 쓰기 명령 · 다중 문장 · 200건 초과 LIMIT 차단
- 챗봇 조회 계정과 ETL 쓰기 계정 **분리**
- 응답에서 `file_path` · API 키 · 비밀번호 · token 후보 **제거**
- `.env` · 원천 데이터 · FAISS 산출물 · 런타임 로그는 **Git 추적 제외**
- FastAPI는 Django `SECRET_KEY`, 세션 테이블, account DB에 접근하지 않음 — 내부 인증 확인은
  별도 `AUTH_INTROSPECTION_KEY`로만 검증

---

## 주요 제약

- FastAPI와 Agent는 account DB, 업무 MySQL, FAISS와 원문 파일에 직접 접근하지 않습니다.
- Django는 account DB만 소유하며 채팅, MCP, 업무 DB를 호출하지 않습니다.
- Data MCP 조회는 허용된 View에 대한 읽기 전용 쿼리만 수행합니다.
- ETL과 문서 인덱싱은 채팅 요청 경로에서 실행하지 않습니다.

---

## 회고

### 문동원

### 박회종

### 이태혁

### 이호원


---

## 관련 문서

| 문서 | 내용 |
|---|---|
| [docs/architecture.md](docs/architecture.md) | 시스템 흐름과 코드 경계 |
| [docs/interface.md](docs/interface.md) | MCP Tool과 HTTP 응답 계약 |
| [docs/ownership.md](docs/ownership.md) | 역할·디렉터리 소유권과 변경 규칙 |
| [docs/test-scenarios.md](docs/test-scenarios.md) | 테스트 시나리오와 완료 기준 |
| [docs/performance.md](docs/performance.md) | 성능 예산과 측정 방법 |
| [docs/django-fastapi-separation-plan.md](docs/django-fastapi-separation-plan.md) | Django/FastAPI 구조 분리 계획 |

---

<div align="center">

⏳ **SKN 32기 · 장꼬방(JangGGo) 팀** · 2026.08.26

</div>
