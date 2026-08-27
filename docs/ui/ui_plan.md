# UI 작업 로그 (ui_plan)

이 파일은 UI/UX 작업의 계획과 완료 점검 기록이다. 규칙은 `CLAUDE.md`의 "ui_plan" 절을 따른다.

- 새 작업은 이 파일 **아래에 append** 한다. 과거 항목은 지우거나 고쳐 쓰지 않는다.
- 착수 전에 항목을 만들고, 작업이 끝나면 같은 항목으로 돌아와 체크박스와 상태를 갱신한다.
- 계획에 있었지만 안 한 것은 `미완:`, 계획에 없던 추가 작업은 `추가:`로 남긴다.

## 기록 형식

```
## [YYYY-MM-DD HH:MM] <작업 제목>
- 지시: <사용자가 요청한 내용 요약>
- 목표: <이 작업이 끝나면 사용자가 무엇을 할 수 있게 되는가>
- 범위: <건드릴 파일 목록>
- 시안: <ui_preview/... 경로, 없으면 "없음(사유)">
- 계획:
  - [ ] 1. ...
  - [ ] 2. ...
- 결정: <선택한 방향과 그 이유>
- 상태: 진행중 | 완료 | 부분완료
```

---

## 현재 UI 기준선 (2026-08-25)

작업 시작 시점의 상태. 비교 기준으로만 쓰고 수정하지 않는다.

| 항목 | 현황 |
|---|---|
| 템플릿 | `django_app/web/templates/web/index.html` 1개 (75줄). 로그인 화면이 같은 파일 안 `#login-screen`에 포함된 SPA 구조 |
| 스타일 | `django_app/web/static/web/style.css` (140줄). `:root`에 ink/muted/line/canvas/surface/soft/blue 계열 토큰 |
| 스크립트 | `django_app/web/static/web/chat.js` (376줄) |
| 차트 | `static/web/vendor/chart.umd.min.js` (Chart.js UMD 로컬 번들) |
| 화면 | 로그인, 채팅, 출처 패널(데스크톱 2단 / 모바일 오버레이) |
| 서버 | `web/views.py`의 `index` view가 shell만 렌더. 데이터는 클라이언트가 API 호출 |

---

## 작업 기록

<!-- 아래에 새 항목을 추가한다 -->

## [2026-08-25 11:59] 로그인 화면 배경/카드 리디자인
- 지시: 로그인 화면에 도시 야경 배경 이미지 적용, 중앙에 blur 처리된 유리(glassmorphism)
  카드로 로그인 폼 표시, 폰트를 Noto Sans(한글은 Noto Sans KR)로 변경. 계정 추가(회원가입)
  기능 필요 여부 검토 요청.
- 목표: 로그인 화면이 배경 사진 + 중앙 frosted-glass 카드 스타일로 바뀌고, 실제 코드
  반영 전 시안으로 먼저 확인 가능한 상태.
- 범위:
  - 시안: ui_preview/20260825-login-redesign.html (신규)
  - 실 코드는 승인 전까지 변경하지 않음 (index.html #login-screen, style.css .login-*)
- 시안: ui_preview/20260825-login-redesign.html
- 계획:
  - [ ] 1. Noto Sans / Noto Sans KR 라이선스 검토 (SIL OFL 여부, 상업/교육 사용 가능 여부)
  - [ ] 2. 프로젝트의 "외부 CDN 금지" 제약과 폰트 적용 방식 조율 (시안은 CDN 허용,
        실제 이식 시 self-host 필요 여부 결정)
  - [ ] 3. 배경 이미지 확보 방법 확인 (사용자가 첨부한 두 이미지는 대화창 첨부라 파일로
        접근 불가 — 실제 파일 전달 필요, 우선 placeholder 그라디언트로 시안 제작)
  - [ ] 4. 중앙 정렬 blur 카드(glassmorphism) 레이아웃 구현, 기존 login-card 구조 참고
  - [ ] 5. 계정 추가(회원가입) 기능의 범위 여부 확인 — accounts 앱은 CLAUDE.md 편집
        범위 밖. 확장 여부는 사용자 결정 필요
  - [ ] 6. 데스크톱/375px 두 뷰포트 확인
- 결정: (진행 중 기록)
- 상태: 진행중

## [2026-08-25 12:11] 로그인 시안 1차 수정 반영
- 지시: Noto Sans KR로 확정, 계정 추가 기능 제외, 배경은 사용자가 제공한 실제 도시 사진
  사용, "로그인 상태 유지"/"비밀번호를 잊으셨나요?" 제거(미구현 기능이므로).
- 범위: ui_preview/20260825-login-redesign.html (수정), ui_preview/assets/city-bg-2400.jpg (신규)
- 계획:
  - [x] 1. CSS placeholder 스카이라인 제거, 실제 배경 사진(city-bg-2400.jpg) 적용
  - [x] 2. row-between(로그인 상태 유지·비밀번호 찾기) 블록 및 관련 CSS 제거
  - [x] 3. register-line(계정 신청) 블록, JS 핸들러, 관련 CSS 제거
  - [x] 4. 모바일 375px에서 demo-bar 줄바꿈 문제 발견 후 수정 (flex-wrap, overflow-x hidden)
  - [x] 5. 데스크톱 1280px / 모바일 375px 브라우저로 재확인
- 결정:
  - 원본 사진(23.8MB, 6000x3937)은 리사이즈 없이 쓰기엔 너무 무거워 2400px/JPEG 78%로
    압축한 사본(city-bg-2400.jpg, 915KB)을 시안에 사용. 실제 이식 시 반응형 srcset이나
    추가 압축 필요 여부를 다시 검토한다.
  - Noto Sans / Noto Sans KR = SIL OFL 1.1, 상업·교육 목적 무관하게 무료 사용·재배포
    가능. 시안은 Google Fonts CDN으로 로드하되, 실제 코드 이식 시에는 CLAUDE.md의
    "외부 CDN 금지" 규칙에 따라 self-host로 전환하기로 함(별도 계획 필요, 미착수).
  - "로그인 상태 유지", "비밀번호를 잊으셨나요?"는 사용자 확인 결과 미구현 기능이라
    이번 리디자인 범위에서 제외. 백엔드 기능이 생기면 그때 다시 추가.
  - 계정 추가(회원가입) 기능은 하지 않기로 확정. 관련 UI 요소 전체 제거.
- 상태: 완료 (승인 대기 — 아직 django_app/web/ 실 코드에는 이식 안 함)

## [2026-08-25 12:14] 로그인 시안 승인 및 실 코드 이식 + 정책 변경
- 지시:
  1. 이 프로젝트는 데스크톱 웹 전용이다. 모바일 대응을 하지 않는다. CLAUDE.md도 수정.
  2. app/static/index.html(죽은 파일) 삭제.
  3. 로그인 카드 blur 강도가 너무 강함 — 낮출 것.
  4. 나머지는 승인 — 실제 django_app/web/ 코드에 이식 진행.
- 목표: 로그인 화면이 실제로 도시 배경 + blur 카드로 바뀌고, 프로젝트가 데스크톱 전용임이
  CLAUDE.md에 명시되어 이후 작업에서 모바일 확인 절차를 반복하지 않는다.
- 범위:
  - CLAUDE.md (반응형/모바일 관련 절 수정)
  - app/static/index.html (삭제)
  - ui_preview/20260825-login-redesign.html (blur 강도 조정)
  - django_app/web/templates/web/index.html (로그인 영역 마크업 교체)
  - django_app/web/static/web/style.css (로그인 스타일 교체, 폰트 적용)
  - django_app/web/static/web/img/city-bg.jpg (신규, 배경 이미지)
  - django_app/web/static/web/fonts/** (신규, Noto Sans KR self-host)
- 시안: ui_preview/20260825-login-redesign.html (blur 조정 후 최종본)
- 계획:
  - [x] 1. CLAUDE.md에서 "반응형 375px~1440px", "모바일 오버레이 유지" 등 모바일 전제
        문구를 데스크톱 전용으로 수정 (새 "데스크톱 전용" 절 추가)
  - [x] 2. app/static/index.html 삭제 (git rm, 빈 app/static/ 디렉터리도 함께 제거됨)
  - [x] 3. 시안의 backdrop-filter blur 값을 낮춰 재확인 (18px → 9px)
  - [x] 4. Noto Sans KR self-host: weight 400/700, 248개 unicode-range woff2(4.2MB)를
        static/web/fonts/noto-sans-kr/에 저장, fonts/noto-sans-kr.css로 @font-face 생성
  - [x] 5. 배경 이미지를 django_app/web/static/web/img/login-bg.jpg로 이동, style.css에서
        상대경로 url()로 참조
  - [x] 6. index.html의 #login-screen/.login-card 마크업에 placeholder만 보강
        (구조 자체가 이미 시안과 동일해 대규모 교체 불필요, 회원가입 UI는 원래도 없었음)
  - [x] 7. style.css 최상단에 폰트 @import 추가, :root font-family를 Noto Sans KR로 변경,
        .login-screen/.login-card 관련 규칙을 시안 스타일로 교체
  - [x] 8. Django 서버 대신(.env 비밀값 없어 기동 불가 — AGENTS.md상 .env는 직접 만들지
        않음) 실제 static 파일을 그대로 쓰는 QA용 정적 사본으로 렌더 확인. 데스크톱
        1280px에서 network 요청 전수 200 OK 확인, 폰트가 unicode-range 매칭분만
        지연 로드되는 것도 확인. 브라우저 패널이 이번 턴에 닫혀 있어 스크린샷은
        생략, DOM/네트워크 로그로 대체 확인
- 결정:
  - .env가 없어 실제 Django 서버 기동 검증은 못 함. 비밀값 파일이라 임의로 만들지
    않았음(AGENTS.md 금지 구역). 사용자가 로컬에서 `python manage.py runserver`로
    최종 육안 확인을 한 번 해주는 게 안전함.
  - 원본 배경 사진(StockSnap_QQXLXMX04M.jpg, 23.8MB)이 ui_preview/assets/에 git 스테이징
    되어 있음(내가 add하지 않았는데 스테이징된 상태로 발견). 저장소에 23MB 원본을
    커밋하는 건 과함 — 커밋 전에 제외하거나 gitignore 처리를 권장.
- 상태: 완료

## [2026-08-25 12:44] 답변별 출처 연결
- 지시: 출처 패널이 "마지막 질문"의 문서만 보여줘서 이전 답변의 근거를 확인할 수 없다.
  각 답변 카드에 "출처 n건 보기"를 붙이거나, 출처 패널에서 해당 답변을 선택하는 구조로
  개선한다. 먼저 작업 방식을 제안할 것.
- 목표: 대화가 길어진 뒤에도 임의의 과거 답변을 골라 그 답변이 실제로 사용한 근거
  문서를 즉시 확인할 수 있다.
- 사전 조사 결과 (코드 확인):
  - app/schemas/chat.py의 ChatResponse는 이미 sources[](각 Source에 id 보유)와
    request_id를 반환한다. 서버 변경 불필요 — 순수 프론트엔드 상태 문제다.
  - chat.js의 renderSources(data.sources, data.route)가 전역 패널을 매번 덮어쓴다.
    답변별 sources를 어디에도 보관하지 않아 이전 근거가 소실된다.
  - 출처는 source_type이 'document' / 'web' 두 갈래이고 렌더 분기가 다르다.
  - 답변 카드는 문자열 HTML로 insertAdjacentHTML/outerHTML 교체 방식으로 그려진다.
    답변마다 안정적인 id가 없어 새로 부여해야 한다.
- 범위 (예정):
  - django_app/web/static/web/chat.js  (답변별 sources 보관, 선택 상태, 칩 버튼)
  - django_app/web/static/web/style.css (칩, 선택된 답변 강조, 패널 헤더 컨텍스트)
  - django_app/web/templates/web/index.html (패널 헤더에 컨텍스트 영역 필요 시)
  - ui_preview/2026MMDD-answer-sources.html (시안)
- 계획:
  - [ ] 1. 구조 설계안(화면/플로우/예외 상태)을 사용자에게 제시하고 승인받기  ← 현재 단계
  - [ ] 2. 시안 제작 후 승인
  - [ ] 3. chat.js: 답변별 sources 보관 + 선택 상태 구현
  - [ ] 4. style.css: 칩/선택 강조/패널 컨텍스트 스타일
  - [ ] 5. 데스크톱 뷰포트 검증, collectstatic 후 실서버 확인
- 결정: (진행 중 기록)
- 상태: 진행중 (구조 승인 대기)

## [2026-08-25 12:48] 답변별 출처 연결 — 구조 승인
- 지시: 구조 승인. "새 답변 도착 시 보던 근거 유지 + 패널 헤더에 새 답변 근거 보기
  버튼" 방식 확정. CLAUDE.md의 "chat.js 400줄 초과 시 분리" 규칙은 근거가 약해
  삭제(빌드 스텝 없어 모듈 분리가 불가능하므로 줄 수 기준이 무의미).
- 결정:
  - CLAUDE.md 121~122행의 400줄 트리거를 제거하고, "문제가 실제로 체감될 때 판단"으로
    대체.
  - 답변 카드에 출처 칩(문서 n건/웹 n건/근거 0건), 패널 헤더에 "N번째 답변 · 근거"
    컨텍스트 표시. 과거 답변 보는 중 새 답변 도착 시 자동 전환하지 않고 유지 +
    "새 답변의 근거 보기" 버튼 노출.
- 다음: ui_preview에 시안 작성 후 승인받고 chat.js/style.css에 이식.
- 상태: 진행중 (시안 작성 단계)

## [2026-08-25 12:50] 답변별 출처 연결 — 시안 완료
- 시안: ui_preview/20260826-answer-sources.html
- 확인한 상태: 문서 근거 칩(선택 시 카드 목록), 웹 출처 칩, 근거 0건 칩(사유 텍스트
  표시), 선택된 답변 카드 강조(파란 테두리+그림자), 패널 헤더 컨텍스트("N번째 답변 ·
  질문"), 과거 답변 보는 중 새 답변 도착 → "새 답변의 근거 보기" 배너 → 클릭 시 전환.
  전부 브라우저로 클릭 검증 완료.
- 상태: 진행중 (사용자 승인 대기)

## [2026-08-25 14:49] 챗봇 아이콘 교체
- 지시: 사용자가 디자인한 로봇 아이콘(파란 글리프, 투명 배경)으로 답변 아바타(.avatar)와
  헤더 브랜드 마크(.brand-mark) 두 곳의 기존 인라인 로봇 SVG를 교체.
- 목표: 두 자리 모두 커스텀 브랜드 아이콘이 보이고, 기존 원형 배경(.avatar)·둥근사각형
  배경(.brand-mark)은 CSS가 계속 그려준다.
- 범위:
  - django_app/web/static/web/img/chatbot-icon.png (신규)
  - django_app/web/static/web/chat.js (robotIcon 상수 → img 태그)
  - django_app/web/templates/web/index.html (brand-mark 인라인 SVG → img 태그)
  - django_app/web/static/web/style.css (.avatar img, .brand-mark img 크기 규칙)
- 계획:
  - [x] 1. ui_preview/assets/chatbot_icon_square.png(1565x1565, 투명)를 256x256으로
        리사이즈해 static/web/img/chatbot-icon.png로 저장 (20KB)
  - [x] 2. chat.js의 robotIcon SVG 문자열을 img 태그로 교체(사용처 2군데: 로딩중
        assistant row, 최종 assistant row)
  - [x] 3. index.html 헤더 brand-mark 안 인라인 SVG를 img로 교체
  - [x] 4. style.css에 .avatar-icon / .brand-mark-icon 크기(62%)·object-fit 규칙 추가
  - [x] 5. collectstatic --clear + local_gateway.ps1 restart 후 데스크톱에서 실제
        렌더 확인 (JS로 로그인 화면을 일시적으로 우회해 헤더·답변 아바타 둘 다 새
        아이콘으로 나오는 것을 스크린샷으로 확인)
- 결정:
  - 시안이 무의미한 저위험 아이콘 교체(오타 수정급)로 판단해 별도 ui_preview HTML
    없이 바로 실 코드에 적용. 대신 앞서 대화에서 avatar 배경색 위 합성 이미지로 사전
    확인을 마쳤음.
  - JS 파일은 {% static %} 태그를 못 써서 아이콘 URL을 하드코딩하면 nginx의
    django-static 1년 immutable 캐시 때문에 재배포 시 갱신이 안 되는 문제가 있음.
    대신 index.html의 <body data-chatbot-icon="{% static ... %}">로 해시 붙은 URL을
    내려주고 chat.js가 그 값을 읽어 쓰도록 함 — 이 패턴은 앞으로 JS에서 static 자산을
    참조할 때 재사용한다.
- 상태: 완료

## [2026-08-25 15:21] 답변별 출처 연결 — 실 코드 이식 (누락 발견)
- 지시: 8000포트에서 확인했는데 답변별 출처 연결 기능이 반영 안 됐다는 사용자 지적.
- 원인: 시안 승인([2026-08-25 12:48] 항목)까지만 하고 아이콘 교체 작업으로 넘어가며
  chat.js/style.css 실 이식을 누락함. 자기 점검(ui_plan 재확인)을 그 시점에 안 해서
  놓침.
- 범위: django_app/web/static/web/chat.js, style.css
- 계획:
  - [x] 1. chat.js: 답변 카드에 안정적 id(ans-N) 부여, answerSources Map에 답변별
        {sources, route, index, question} 저장
  - [x] 2. chat.js: 답변 카드에 출처 칩 렌더 (문서 n건/웹 n건/근거 0건), 클릭 시 해당
        답변 선택 + 패널 오픈
  - [x] 3. chat.js: 선택된 답변 강조(is-selected), 패널 헤더(#sources-summary)를
        컨텍스트 텍스트("N번째 답변 · 질문의 근거")로 재사용
  - [x] 4. chat.js: 과거 답변 보는 중 새 답변 도착 시 자동전환 없이 "새 답변의 근거
        보기" 배너 노출, 클릭 시 최신으로 전환. GENERAL/DATABASE 라우트처럼 칩이 없는
        답변은 패널 상태에 영향을 주지 않도록 처리(계획에 없던 추가 판단)
  - [x] 5. style.css: .source-chip, .is-selected, .jump-banner 스타일 이식, 배너가
        레이아웃을 밀지 않도록 .sources-panel을 flex column으로 변경(계획에 없던 추가
        수정 — 시안엔 없던 실제 레이아웃 이슈)
  - [x] 6. collectstatic + local_gateway restart 완료. 로그인 세션이 없어 실제 /api/chat
        호출은 못 걸었지만, chat.js의 동일 로직 경로(answerSources·selectAnswer·
        sourceChipHtml)를 브라우저 콘솔에서 그대로 호출해 문서 3건/웹 1건/근거 0건
        답변과 "과거 답변 보는 중 새 답변 도착" 시나리오를 스크린샷으로 확인
- 결정: index.html의 #sources-summary를 그대로 재사용해 새 DOM을 늘리지 않음. 대신
  renderSources()에서 요약 텍스트를 세팅하던 책임을 selectAnswer()로 옮김.
- 상태: 완료

## [2026-08-25 15:41] 출처 패널 스크롤 분리, 웹 출처 클릭, DB 근거 표시 버그 수정
- 지시:
  1. 채팅 영역과 참고 문서 패널이 같이 스크롤됨 — 독립 스크롤로 분리
  2. 웹 문서 출처는 카드 클릭 시 새 창으로 바로 열리게
  3. 업무 데이터(DATABASE) 답변의 근거가 출처 패널에 전혀 안 뜸
- 원인 분석:
  1. .chat-panel/.sources-panel이 min-height:100dvh라 내용이 넘치면 패널 자체가
     늘어나 body가 스크롤됨. .messages/.sources-list의 overflow-y:auto가 무의미해짐.
  2. renderSources() 웹 분기에서 카드 안 작은 URL 텍스트만 <a>였음.
  3. app/agent/nodes.py의 _build_sources()가 source_type:"database"를 실제로 내려주는데
     chat.js의 renderSources()/sourceChipHtml()이 'document'/'web'만 필터링해서 DB
     소스를 조용히 버리고 있었음 — 실사용 버그, 시안에서도 놓쳤던 부분.
- 범위: django_app/web/static/web/chat.js, style.css
- 계획:
  - [x] 1. .app-shell/.chat-panel/.sources-panel을 min-height→height로 변경. 추가로
        발견: CSS grid/flex 아이템의 기본 min-height:auto 때문에 height를 줘도 내용
        만큼 커지는 문제가 있어 .chat-panel/.sources-panel/.messages에 min-height:0을
        명시해야 했음(계획에 없던 추가 원인 규명)
  - [x] 2. 웹 출처 카드를 <article>에서 <a target="_blank" rel="noopener noreferrer">로
        변경, 카드 전체 클릭 가능하게. 카드 안 중첩 <a>를 없애 유효하지 않은 HTML이
        되지 않게 함
  - [x] 3. renderSources()/sourceChipHtml()에 source_type "database" 처리 추가.
        databaseCardHtml()(테이블명·freshness·버전) 신설, 문서+DB 동시 노출(BOTH
        라우트) 지원, 칩 라벨을 "문서 N건 · 데이터 N건" 형태로 결합
  - [x] 4. 데스크톱에서 브라우저 콘솔로 문서+DB 혼합, 웹 출처, 스크롤 오버플로우
        시나리오를 실제 chat.js 함수로 재현해 확인 (로그인 세션 없어 스크린샷 대신
        DOM/스크롤 속성 비교로 검증)
- 결정: body 전체 스크롤을 완전히 막기 위해 html/body에 height:100%, body에
  overflow:hidden을 추가함 — 로그인 화면(position:fixed)에는 영향 없음.
- 상태: 완료


## [2026-08-25 15:55] 표·차트 조작 기능 (CSV 다운로드, 차트 이미지 저장, 정렬/상위N, 기간 대비 요약)
- 지시: 답변에 포함되는 표/차트에 CSV 다운로드, 차트 이미지 저장, 정렬 및 상위 N개
  보기, 기간형 데이터의 전월·전년 대비 및 최고/최저값 요약 기능을 추가. 먼저 계획을
  세워달라는 요청.
- 사전 조사 결과 (코드 확인):
  - app/schemas/chat.py의 TableData는 domain/sql/columns/rows/chartable/chart_type/
    label_column/value_column만 제공. 기간·날짜 컬럼을 명시하는 필드는 없음 —
    "전월·전년 대비"는 컬럼명 패턴(월/년/date/month/year 등)으로 클라이언트가
    추정해야 하는 휴리스틱임. 서버 스키마 변경 없이 프론트에서 최대한 처리하되,
    한계가 있으면 사용자에게 먼저 알린다.
  - 현재 renderTable()/drawChart()는 매 답변마다 정적 HTML을 한 번 그리고 끝 —
    정렬·Top N처럼 답변을 받은 뒤 사용자가 상호작용하며 다시 그리는 기능은 처음
    추가하는 유형. chartCounter로 canvas id만 관리하던 구조에 테이블별 상태
    (원본 rows, 현재 정렬/N 상태)를 별도로 들고 있어야 함.
  - Chart.js(vendor/chart.umd.min.js)는 이미 로컬 번들이라 이미지 저장(canvas.toBlob
    또는 chart.toBase64Image())에 추가 의존성 없이 가능.
- 범위 (예정): chat.js, style.css. 서버(app/) 변경은 원칙적으로 없음(단, 기간 추정
  휴리스틱이 신뢰도가 낮다고 판단되면 서버에 period_column 필드 추가를 제안할 수 있음
  — 그 경우 별도 승인 필요).
- 계획:
  - [ ] 1. 구조 설계안을 사용자에게 제시하고 승인받기 ← 현재 단계
  - [ ] 2. 시안 제작 후 승인
  - [ ] 3. 구현
  - [ ] 4. 검증
- 결정: (진행 중 기록)
- 상태: 진행중 (구조 승인 대기)

## [2026-08-25 15:57] 표·차트 조작 기능 — 구조 승인
- 지시: 구조 승인. CSV는 화면에 보이는 상태(정렬·상위N 반영) 그대로 다운로드. 전월·전년
  대비는 컬럼명/값 패턴 추측 방식으로 우선 진행하고, 인식 실패 시 그 부분만 숨기고
  최고/최저 요약은 항상 표시.
- 결정:
  - CSV export는 현재 렌더링된 rows(정렬·Top N 반영) 기준. 숫자는 화면 표시용 포맷(콤마·
    통화기호) 대신 원본 숫자 그대로 내보내 재계산 가능하게 함.
  - 기간 인식: columns 이름 패턴(월/년/date/month/year/기간/period)과 값 형식
    (YYYY-MM, YYYY-MM-DD, YYYY년 MM월, YYYY년, YYYY/MM 등)을 프론트에서 추측. 인식
    실패 시 전월/전년 대비 텍스트만 숨기고 최고/최저 요약은 항상 노출(value_column만
    있으면 계산 가능해 안정적).
  - server(app/schemas/chat.py)의 period_column 필드 추가는 이번 스코프에서 보류.
- 다음: ui_preview에 시안 작성 (표 정렬/Top N/CSV/차트 저장/기간요약 상태 포함) 후 승인.
- 상태: 진행중 (시안 작성 단계)

## [2026-08-25 16:01] 표·차트 조작 기능 — 시안 승인, 실 코드 이식 시작
- 지시: 시안 그대로 승인. 실 코드 이식 진행.
- 범위: django_app/web/static/web/chat.js, style.css
- 계획:
  - [x] 1. renderTable/renderChartPlaceholder/drawChart를 mountTableBlock 방식으로 교체
        (테이블별 정렬·상위N 상태, Chart 인스턴스 보관 및 destroy 후 재생성)
  - [x] 2. CSV 다운로드, 차트 이미지 저장, 기간 요약(computeSummary/parsePeriod) 이식.
        최고/최저 표시는 formatCell로 통화 포맷(JOD 등) 유지, CSV는 원본 숫자 그대로
  - [x] 3. style.css에 table-controls/csv-button/chart-save-button/sortable/
        period-summary 스타일 이식, chart-wrap을 header+canvas-box 2단 구조로 변경
  - [x] 4. collectstatic + local_gateway restart, 실서버(8000)에 로그인 화면을 JS로
        우회하고 chat.js의 실제 함수(mountTableBlock 등)를 더미 TableData로 호출해
        검증: 정렬 내림차순, 상위 5개 슬라이스, CSV/이미지 저장 버튼 무오류, 기간
        요약(최고/최저 + 전월 -5.5% + 전년 동월 +13.4%) 전부 시안과 동일하게 동작
- 상태: 완료


## [2026-08-25 16:13] 기간 요약 수정: 전월 대비 제거, 평균값 추가, 중복 기간 안전장치
- 지시: 전월 대비 값이 잘못 표시됨. 전월 대비 대신 평균값을 표시할 것.
- 원인 분석: 표가 "월 하나당 행 하나"가 아니라 월×다른 차원(제품 등)으로 여러 행이
  같은 월에 존재하는 경우, computeSummary()가 "최근 월"/"그 전월"에 해당하는 행을
  아무거나 하나씩 골라 비교해서 서로 다른 그룹 값이 비교되는 문제가 있었음. 전년
  대비도 동일 구조라 같은 위험을 가짐.
- 범위: django_app/web/static/web/chat.js
- 계획:
  - [x] 1. 전월 대비(mom) 계산·표시 제거
  - [x] 2. 평균값(avg) 계산·표시 추가 (value_column 평균, formatCell로 통화 포맷 유지)
  - [x] 3. 기간 컬럼 값에 중복이 있으면(같은 월이 여러 행) 전년 대비도 계산하지 않고
        숨김 — 중복 없는 깨끗한 단일 시계열일 때만 전년 대비 표시
  - [x] 4. collectstatic + 재배포, 실서버(8000)에서 두 케이스로 검증: (a) 월 1개=행
        1개인 깨끗한 시계열 → 최고/최저/평균/전년대비 전부 표시, (b) 월×제품 중복
        다차원 표 → 최고/최저/평균만 표시되고 전년대비는 자동으로 숨겨짐
- 상태: 완료


## [2026-08-25 16:17] 빠른 질문(예시 질문) 지원
- 지시: 첫 화면(빈 대화 상태)에 역할별 예시 질문 4~6개를 보여주고, 클릭하면 바로
  질문이 전송되게 한다.
- 사전 조사 결과 (코드 확인):
  - shared/auth_policy.py의 Role = "admin" | "hr" | "finance". hr은 document_db만,
    finance는 document_db+sales_db+purchase_db, admin은 전체 접근 가능 — 예시 질문을
    역할별로 다르게 구성할 근거가 이미 서버 정책에 있음.
  - chat.js의 showApplication(user)에서 user.role을 이미 받고 있음(현재는 표시만
    하고 저장은 안 함) — 여기서 역할을 저장하고 예시 질문 세트를 고르면 됨.
  - #messages는 현재 완전히 빈 <section>. 웰컴/빈 상태 마크업이 전혀 없어 신규 구현.
  - style.css에 .welcome-icon 선택자가 이미 있지만(사용되는 곳 없음) 실제 마크업은
    없음 — 재사용 가능.
- 범위 (예정): chat.js, style.css, index.html(placeholder 필요 시)
- 계획:
  - [ ] 1. 구조 설계안 제시 및 승인 ← 현재 단계
  - [ ] 2. 시안 제작 후 승인
  - [ ] 3. 구현
  - [ ] 4. 검증
- 결정: (진행 중 기록)
- 상태: 진행중 (구조 승인 대기)

## [2026-08-25 16:29] 빠른 질문 — 문구 확정, 시안 작성
- 지시: 질문 문구 확정.
  - hr: "법인카드 발급 방법 알려줘"
  - finance: "2026년 1분기 매출을 2025년 1분기와 비교해줘"
  - admin: 위 두 질문을 합친 것 (2개)
- 결정: 이전에 초안으로 제시한 4~6개 세트는 폐기하고 사용자가 확정한 문구만 사용.
  hr/finance는 칩 1개, admin은 2개로 개수가 역할마다 다름 — 의도된 결과.
- 다음: ui_preview에 시안 작성(역할별 전환 데모 포함) 후 승인받고 chat.js/style.css에
  이식.
- 상태: 진행중 (시안 작성 단계)

## [2026-08-25 16:33] 빠른 질문 — 시안 승인, 실 코드 이식
- 지시: 시안 승인, 실 코드 이식 진행. 동시에 "웹 출처 새 창 안 열림" 재발 제보.
- 웹 출처 재확인 결과: 배포된 chat.js(hash a42e1ad06e85)에 source_type:"web"을 실제
  주입해 재현한 결과 <a href target=_blank>로 정상 렌더됨 — 프론트 코드는 문제없음.
  사용자가 클릭한 카드가 📄 문서 카드(source_type:"document")였을 가능성이 높음 —
  문서 카드는 원래 클릭 불가(다운로드 버튼만 동작) 설계라 구분이 필요. 사용자에게
  아이콘 확인 요청, 답변 대기.
- 범위: django_app/web/static/web/chat.js, style.css
- 계획:
  - [x] 1. index.html의 #messages는 그대로 빈 섹션 유지 — showApplication()이 로그인
        성공 시 renderWelcomeIfEmpty()로 채우는 방식으로 확정, 템플릿 수정 불필요
  - [x] 2. chat.js: EXAMPLE_QUESTIONS 맵(hr/finance/admin), renderWelcomeIfEmpty() 구현
  - [x] 3. showApplication(user)에서 currentUserRole 저장 + renderWelcomeIfEmpty 호출.
        clearApplicationState()가 messages를 비운 뒤 showApplication이 실행되는 기존
        순서 그대로라 재로그인 시에도 자동으로 웰컴 재표시됨
  - [x] 4. 폼 submit 핸들러 맨 앞에서 .welcome-screen 제거 — 칩 클릭이든 직접 입력
        후 전송이든 동일 경로(input.value 설정 후 form.requestSubmit())라 한 곳만
        처리하면 됨
  - [x] 5. style.css에 welcome-screen/welcome-icon/welcome-title/welcome-sub/
        example-questions/example-chip 스타일 이식
  - [x] 6. collectstatic + local_gateway restart, 실서버(8000)에서 role별 3케이스
        (hr 1개/finance 1개/admin 2개) 문구·개수 확인, 칩 클릭 시 웰컴 제거 및 사용자
        말풍선 추가까지 확인
- 상태: 완료 (동시 진행: "웹 출처 새 창 안 열림" 재제보 — 배포된 코드에서 재현 시도
  결과 source_type:"web"인 카드는 정상 동작 확인. 문서(document) 카드와 혼동했을
  가능성 제기, 사용자 확인 대기 중이라 이 항목은 별도 완료 처리 보류)


## [2026-08-25 16:57] 웹 출처 클릭 안 됨 — 근본 원인 확정 및 UI단 임시 조치
- 지시: 지구본 카드 클릭해도 새 창이 안 열림. 원인 진단 요청.
- 원인 (사용자가 준 실제 /api/chat 응답 JSON으로 확정):
  - app/agent/nodes.py의 _build_sources()는 웹 출처에 "url" 키를 정상적으로 채워
    넣지만, app/schemas/chat.py의 Source Pydantic 모델에 url 필드가 선언돼 있지
    않아 응답 직렬화 시 조용히 사라짐 (Pydantic 기본 extra='ignore').
  - 대신 "id" 필드에는 우연히 동일한 URL 값이 들어있음(nodes.py에서
    "id": item.get("url", "")로 설정) — 프론트는 source.url만 봐서 undefined를
    받고 safeWebUrl()이 null 반환 → <a> 대신 <div>로 폴백.
  - 순수 프론트 버그가 아니라 서버 스키마 누락이 근본 원인. 서버 파일
    (app/schemas/chat.py)은 CLAUDE.md 편집 범위 밖이라 직접 고치지 않음.
- 범위: django_app/web/static/web/chat.js (임시 조치만)
- 계획:
  - [x] 1. webCardHtml()에서 safeWebUrl(source.url) || safeWebUrl(source.id)로 fallback
  - [x] 2. collectstatic + 재배포, 실서버(8000)에서 사용자가 제공한 실제 응답과 동일한
        형태(url 없이 id만 존재)로 재현 → <a href target=_blank>로 정상 렌더 확인
  - [x] 3. 사용자에게 근본 수정 위치 전달 완료: app/schemas/chat.py의 Source 모델에
        url: str | None = None 필드 추가 필요 (백엔드 담당자 조치 필요, UI 밖 범위)
- 결정: 서버 스키마를 직접 고치지 않고 프론트에서 id를 fallback으로 쓰는 이유 —
  CLAUDE.md 편집 범위(app/**)를 벗어나고, id가 우연히 url과 같다는 데 의존하는 임시
  방편이라 서버가 url 필드를 정식으로 채워 보내면 이 fallback은 자연히 안 쓰이게 됨
  (제거할 필요도 없음, safeWebUrl(source.url)이 먼저 성공하므로).
- 상태: 완료


## [2026-08-25 17:08] 이상탐지 대시보드 페이지 — 구조 설계
- 지시: 채팅/대시보드 탭 전환 헤더 추가(우측에 사용자명+로그아웃). 대시보드 화면에
  들어갈 데이터는 sales/purchase 데이터를 보고 직접 제안할 것.
- 사전 조사 (코드 확인):
  - database/sales/views.sql, database/purchase/views.sql 확인. v_sales_order/
    v_purchase_order가 "매출/구매액의 유일한 정의"로 취소·초안을 이미 제외한 뷰라
    이상탐지 기준 데이터로 적합. v_invoice/v_vendor_invoice로 연체 추적 가능,
    v_sales_order_status/v_purchase_order_status로 취소율 추적 가능.
  - shared/auth_policy.py 기준 hr은 document_db만 접근 가능 — 대시보드가 매출/구매
    데이터를 다루므로 접근 제어가 필요한 정책 문제라 사용자에게 확인.
  - 앱 코드 전체에 anomaly/이상탐지 관련 기존 구현 없음 — 전부 신규.
  - 현재 라우트는 "/" 하나뿐, 뷰는 shell만 렌더하는 MPA + client-JS 패턴. 새 페이지
    추가는 CLAUDE.md 작업범위에 이미 허용돼 있음(views.py/urls.py 최소 수정).
- 결정:
  - 대시보드는 새 라우트 /dashboard/ + 별도 템플릿으로 구현(같은 페이지 내 JS 탭
    전환 대신). 기존 MPA 패턴과 일치, 새로고침/북마크/뒤로가기 자연 동작.
  - 헤더를 {% include 'web/_header.html' %}로 공유. 로그인/세션 로직(현재 chat.js에
    뒤섞여 있음)을 auth.js로 분리해 index/dashboard 두 페이지가 공유 —
    "실제로 두 번째 소비자가 생기는 시점에 분리"라는 CLAUDE.md 원칙에 부합.
  - 대시보드 탭은 finance/admin 역할에게만 노출(사용자 확정) — hr은 sales_db/
    purchase_db 접근 권한이 없으므로 탭 자체를 안 보이게 함.
  - 이상탐지 계산(이동평균/표준편차 등)은 신규 백엔드 API(예: GET
    /api/dashboard/anomalies)가 필요 — app/ 영역이라 직접 구현 안 함. 시안은 더미
    데이터로 만들고, 승인되면 필요한 응답 스펙을 정리해 백엔드에 전달.
- 범위 (예정):
  - django_app/web/templates/web/_header.html (신규, 공유 파셜)
  - django_app/web/templates/web/dashboard.html (신규)
  - django_app/web/static/web/auth.js (신규, chat.js에서 로그인/세션 로직 분리)
  - django_app/web/static/web/dashboard.js (신규)
  - django_app/web/static/web/chat.js (로그인 로직 제거, auth.js 의존)
  - django_app/web/static/web/style.css (헤더 탭, 대시보드 카드/차트 스타일)
  - django_app/web/views.py, urls.py (dashboard 라우트 추가)
  - ui_preview/2026MMDD-dashboard.html (시안)
- 계획:
  - [ ] 1. 시안 제작 (더미 이상탐지 데이터로 대시보드 화면 + 헤더 탭)
  - [ ] 2. 시안 승인
  - [ ] 3. auth.js 분리 (기존 로그인 동작 회귀 없는지 검증 필수)
  - [ ] 4. dashboard 라우트/템플릿/JS 구현
  - [ ] 5. 백엔드에 전달할 API 스펙 문서 정리
  - [ ] 6. 검증
- 상태: 진행중 (시안 작성 단계)

## [2026-08-25 17:15] 이상탐지 대시보드 — 시안 승인, API 스펙 문서 전달
- 지시: 시안 그대로 진행 승인. 백엔드에 전달할 API 스펙 문서 요청.
- 결과: docs/team_share/09_dashboard_anomaly_api_spec.md 작성 완료. 기존
  03_cross_team_requests.md/04_chart_spec.md 형식(작성자/읽는 대상/근거/요청 내용/
  완료 기준)을 그대로 따름. GET /api/dashboard/anomalies 엔드포인트, 응답 스키마
  (KpiCard/Anomaly/TrendPoint/DashboardResponse), 항목별 계산 제안 표, hr 403 요구
  사항을 담음.
- 상태: 진행중 (다음: auth.js 분리 착수 전 사용자 확인)

## [2026-08-25 17:21] auth.js 분리 완료
- django_app/web/static/web/auth.js 신설: csrfHeaders/responseError/showLogin/
  showApplication/restoreSession/로그인폼·로그아웃 이벤트 전부 이관.
  window.onAuthStateCleared/onAuthStateReady 훅으로 chat.js(및 앞으로 dashboard.js)가
  로그인/로그아웃 시점에 자기 상태를 초기화하도록 위임.
- chat.js에서 해당 로직 제거, 훅 등록만 남김. index.html에 auth.js를 chat.js보다
  먼저 로드하도록 <script> 태그 추가.
- 검증: 실서버(8000)에서 showApplication()/showLogin() 직접 호출로 화면 전환 확인,
  로그인 폼 실제 제출 시 /api/auth/login에 진짜 요청이 나가고 401 에러 문구가
  #login-error에 정상 표시되는 것까지 확인(회귀 없음).
- 상태: 완료

## [2026-08-25 17:31] 이상탐지 대시보드 페이지 — 구현 완료
- 범위: django_app/web/views.py, urls.py, templates/web/_header.html(신규),
  templates/web/dashboard.html(신규), templates/web/index.html, static/web/auth.js,
  static/web/dashboard.js(신규), static/web/style.css
- 계획:
  - [x] 1. views.py에 dashboard 뷰 추가, urls.py에 /dashboard/ 라우트 추가
        (active_tab 컨텍스트로 헤더 탭 활성 표시)
  - [x] 2. _header.html 공유 파셜 작성(브랜드+탭+사용자명+로그아웃), index.html의
        기존 app-header에서 브랜드/user-menu를 걷어내고 include로 교체
  - [x] 3. dashboard.html 신규 템플릿(로그인 화면 포함, auth.js+dashboard.js 로드)
  - [x] 4. dashboard.js: DUMMY_DASHBOARD_DATA로 시안과 동일한 화면 렌더, role 기반
        접근 제어(hr → 접근 거부 화면), fetchDashboardData()는 TODO 주석과 함께
        더미 반환 — 09번 스펙 문서의 API가 생기면 이 함수만 교체하면 되도록 설계
  - [x] 5. style.css: .top-header/.top-tabs 등 공유 헤더 스타일, .dashboard-page 이하
        대시보드 전용 스타일, --warn/--warn-bg/--warn-line 토큰 신규 추가.
        body를 flex column(헤더+app-shell)으로 재구성, .app-shell--single 모디파이어로
        대시보드는 출처 패널 없는 1단 레이아웃
  - [x] 6. collectstatic + 재배포, 실서버(8000)에서 검증: /dashboard/ 200 응답,
        finance/admin 접근 시 KPI 4·이상탐지 카드 6·차트 2 정상 렌더, hr 접근 시
        탭 숨김+접근 거부 화면, 채팅 페이지(index)도 새 헤더 추가 후 스크롤 분리·
        웰컴 화면 회귀 없음 확인
- 결정: 서버 API가 없어 dashboard.js는 전량 더미 데이터. 실제 데이터 연동은
  docs/team_share/09_dashboard_anomaly_api_spec.md의 API가 만들어진 뒤 별도 작업.
- 발견한 버그(계획에 없던 추가 수정): auth.js와 dashboard.js가 둘 다 최상위 스코프에
  const DASHBOARD_ROLES를 선언해 SyntaxError로 dashboard.js 전체가 죽는 문제 발생.
  classic <script> 태그끼리는 최상위 let/const 스코프를 공유한다는 점을 놓쳤음.
  dashboard.js의 중복 선언을 제거하고 auth.js의 선언 하나만 남겨 해결.
- 상태: 완료

## [2026-08-25 17:39] 헤더 정리 + 리포트 탭 신설 (바로 실행 지시)
- 지시: (1) app-header 우측 햄버거 아이콘(출처 패널 토글 버튼) 삭제 — 데스크톱에서
  출처 패널이 항상 보여서 쓸모없음. (2) 세 번째 탭 "리포트 생성" 신설, 화면은 공란.
  (3) 탭 아이콘(이모지) 전부 제거, 텍스트만.
- 사용자가 계획 생략을 명시적으로 요청 — 시안 없이 바로 실행(오타 수정급 저위험 변경).
- 범위: index.html, chat.js, style.css, urls.py, views.py, _header.html,
  templates/web/report.html(신규), static/web/report.js(신규)
- 실행 내용:
  - index.html/chat.js/style.css: #sources-toggle(햄버거) 버튼과 관련 JS 이벤트·
    aria-expanded 처리·CSS 전부 제거. 데스크톱은 출처 패널이 항상 보여 토글이
    무의미했음.
  - _header.html: 탭 3개(채팅/대시보드/리포트 생성) 모두 이모지 제거하고 텍스트만.
  - urls.py에 report/ 라우트, views.py에 report 뷰, report.html(로그인 화면+헤더+
    빈 main), report.js(restoreSession() 호출만) 신규 — 지시대로 화면은 공란.
  - 리포트 탭은 역할 제한 없이 전체 공개(지시에 별도 언급 없어 채팅과 동일하게 처리).
- 검증: 실서버(8000)에서 햄버거 버튼 제거 확인, 탭 텍스트 3개 정상, /report/ 페이지
  로그인 게이트 정상 동작 + 본문 완전히 빈 상태 확인, hr 역할로도 대시보드 탭만
  숨겨지고 리포트 탭은 정상 노출 확인.
- 상태: 완료


## [2026-08-25 17:58] 챗봇 아이콘 2차 교체 (배경 포함 원본 아이콘, 둥근 정사각형 통일)
- 지시: 이전엔 배경을 투명 처리해서 썼는데, 이번엔 사용자가 새로 준 아이콘(어두운
  둥근 사각형 배경 포함, ui_preview/assets/2.png)을 배경째로 답변 아바타와 헤더
  브랜드 마크 둘 다에 적용. 시행착오 끝에 "둘 다 동일한 둥근 정사각형, radius는
  작게"로 확정.
- 결정: 아이콘 래스터 자체에 둥근 모서리를 굽지 않고, 컨테이너(.avatar,
  .top-brand-mark)에 border-radius:6px + overflow:hidden을 적용하고 이미지는
  object-fit:cover로 꽉 채우는 방식 선택 — 해상도가 달라져도 안 뭉개지고,
  아바타/브랜드마크 두 자리에 같은 정사각 원본 파일을 재사용할 수 있음.
  .avatar의 기존 원형(border-radius:50%)과 파란 테두리를 제거했지만
  background: var(--blue-soft)는 남겨둠 — 아이콘이 불투명이라 평소엔 안 보이고,
  오류 답변 행("!" 텍스트 아바타)에서만 배경으로 쓰여 그 케이스가 깨지지 않게 함.
- 범위:
  - django_app/web/static/web/img/chatbot-icon.png (덮어씀 — 377x374 원본을 정사각
    크롭 후 256x256로 리사이즈, 배경 포함)
  - django_app/web/static/web/style.css (.avatar, .avatar-icon, .top-brand-mark,
    .top-brand-mark img)
- 검증: 실서버(8000)에서 두 위치 모두 새 해시 파일(chatbot-icon.f8597f939dfa.png)
  로드 확인, computed style로 border-radius:6px·object-fit:cover 동일 적용 확인.
  브라우저 패널이 닫혀있어 스크린샷 대신 DOM 속성으로 대체 검증.
- 상태: 완료

## [2026-08-26 10:11] 이상탐지 API 연동 + 리포트 생성 기능 — 코드 리뷰 및 계획
- 지시: 팀원이 개발한 이상탐지(백엔드)/리포트 생성 기능을 ui 브랜치 merge 후 검토하고
  대시보드/리포트 탭에 반영할 계획을 세울 것.
- 리뷰 결과:
  - GET /api/anomalies: docs/team_share/09_anomaly_temp_dashboard_cleanup.md에 따르면
    "정식 대시보드 나올 때까지 쓰는 TEMP" 위젯. 프론트 반영분(index.html/chat.js/
    style.css TEMP 블록)은 ui 브랜치에 실제로 merge 안 됨 — 내 작업과 충돌 없음.
    응답이 우리 09번 스펙 문서(KpiCard/TrendPoint/DashboardResponse)와 다름: 단순
    flat list [{domain,type,entity,amount,detail,detected_at}], KPI·추이·심각도
    없음. hr 403은 구현됨.
  - GET /api/reports/templates, POST /api/reports/generate: TEMP 아님, 실사용
    기능. 템플릿 1개(sales_monthly), 기간 지정 후 .docx 스트리밍 다운로드.
    에러코드 400/403/404/422/502/503/500 전부 매핑되어 있음.
  - app/schemas/chat.py Source에는 여전히 url 필드 없음(웹 출처 fallback 로직은
    계속 필요).
  - app/static/index.html(죽은 파일, 이전에 삭제함)이 merge로 재등장함 — 이번
    작업 범위 밖이라 별도로 처리 예정, 우선 기록만.
- 결정: 실제 API 응답 형태에 맞춰 대시보드 목업을 다시 설계(KPI/추이 차트 제거 또는
  보류, 이상탐지 리스트 중심으로 재구성). 리포트 생성은 실제 API 그대로 연동.
- 다음: 아래 계획 사용자 승인 대기.
- 상태: 진행중 (계획 수립 단계)

## [2026-08-26 10:16] 이상탐지/리포트 생성 재구성 — 구조 승인, 시안 작성
- 지시: 백엔드가 실제로 만든 API(GET /api/anomalies, GET /api/reports/templates,
  POST /api/reports/generate)에 맞춰 대시보드 화면 재구성 시안 작성. hr 역할은
  대시보드·리포트 생성 탭 둘 다 숨김 처리(리포트 생성도 role-gate하기로 확정).
- 결정: 리포트 생성 탭도 DASHBOARD_ROLES(admin/finance)와 동일하게 hr에게 숨김.
  현재 유일한 템플릿이 sales_db 권한을 요구해 hr은 어차피 403이 나므로 일관성 있게
  미리 숨김.
- 다음: ui_preview에 실제 API 응답 형태 반영한 시안 작성 후 승인받고
  dashboard.js/report.js/report.html/style.css/_header.html에 이식.
- 상태: 진행중 (시안 작성 단계)

## [2026-08-26 10:30] 리포트 생성 탭 — 실 코드 이식 (대시보드는 보류)
- 지시: 대시보드는 추가로 손볼 게 있어 보류. 승인된 시안(20260826-dashboard-report-v2.html)
  중 리포트 생성 탭만 먼저 실 코드로 이식.
- 범위: django_app/web/templates/web/report.html, _header.html,
  django_app/web/static/web/report.js, style.css
- 계획:
  - [x] 1. _header.html: report-tab-link id 부여, auth.js의 role 토글 로직을
        RESTRICTED_TAB_IDS 배열로 일반화해 dashboard-tab-link와 함께 숨김
  - [x] 2. report.html: 기존 #report-root 컨테이너 그대로 사용(마크업은 report.js가
        동적 렌더 — dashboard.js와 동일 패턴)
  - [x] 3. report.js: GET /api/reports/templates 조회+렌더, POST
        /api/reports/generate → blob 응답 다운로드(handleDownload 패턴 재사용),
        상태코드별 에러 메시지 매핑(400/403/404/422/502/503/500 + 401 세션만료),
        role 접근 제어
  - [x] 4. style.css: template-list/template-card/date-row/generate-button/
        report-status 스타일 추가. 컨테이너는 dashboard.js가 쓰는 .dashboard/
        .dashboard-title/.dashboard-sub를 재사용(새 .page류 클래스 안 만듦)
  - [x] 5. collectstatic + 재배포, 실서버에서 검증
- 발견한 버그(계획에 없던 추가 수정):
  1. FastAPI가 아예 기동 못 하고 있었음 — app/services/docx_builder.py가 import하는
     matplotlib이 로컬 app/.venv에 미설치(모든 /api/* 502의 원인, 내 UI 문제 아님).
     app/requirements.txt에는 이미 선언돼 있어 uv로 개별 설치(matplotlib,
     python-docx, typing-extensions)해 동기화만 함 — 코드는 안 건드림.
  2. app/requirements.txt 자체에 인코딩 버그 발견: 팀원이 추가한 한글 주석 한 줄이
     UTF-8이 아니라 CP949로 저장돼 있어 uv가 파일 전체를 못 읽음. 백엔드 팀에 전달
     필요(아래 결정 참고). 이번엔 개별 패키지 설치로 우회.
  3. report.js 자체 버그: render()가 매번 #report-status를 빈 채로 재생성해서,
     생성 실패/성공 메시지가 뜨자마자 finally의 재렌더링에 지워짐. statusKind/
     statusText를 모듈 상태로 승격해 render()가 항상 현재 상태를 반영하도록 수정.
  4. 401(세션 만료) 응답에 대한 처리가 없어 그냥 일반 오류 메시지로만 떴음.
     chat.js와 동일하게 showLogin() 호출 + 안내 문구로 통일.
- 검증: 실서버(8000)에서 GET /api/reports/templates 실제 응답(템플릿 1개)으로 카드
  렌더 확인, POST /api/reports/generate 실제 401 응답에 로그인 화면 전환 + 에러
  문구 정상 표시 확인, hr 역할 대시보드·리포트 탭 둘 다 숨김 확인.
- 상태: 완료


## [2026-08-26 10:52] 대시보드 재구성 — 월별 추이 API 추가 확인, 시안 재작성
- 지시: app/services/monthly_trends_service.py, app/api/dashboard.py 신규 추가됨.
  이상탐지 재확인 + 이 두 파일로 대시보드 시안 재작성 요청.
- 리뷰 결과:
  - GET /api/dashboard/monthly-trends?year= → {sales:[{month,amount}],
    purchase:[{month,amount}]}. 도큐먼트 주석은 dashboard.js의 더미 필드명
    (period/value/is_anomaly)과 같다고 주장하나 실제 구현은 다름(month/amount,
    is_anomaly 없음) — docstring-코드 불일치 확인, 실제 코드 기준으로 반영하기로 함.
  - main.py에 include_router 없음, nginx에도 /api/dashboard 프록시 없음 — 아직
    미배선. app/main.py, deploy/nginx/local.conf는 편집 범위 밖이라 백엔드에 전달.
  - 이상탐지(/api/anomalies)는 지난 리뷰와 변경 없음.
- 결정: monthly-trends(실제 매출/구매 추이) + anomalies(이상 신호 리스트) 두 API를
  합쳐 KPI 카드(최근달 매출/구매/전월대비/연체총액/이상신호건수) + 추이 차트 +
  이상탐지 카드로 재구성. 추이 차트에 이상치 강조 점은 안 넣음(is_anomaly 필드
  실제로 없어 근거 없는 표시가 되므로).
- 다음: ui_preview 시안 작성 후 승인받고 dashboard.js/style.css에 이식.
- 상태: 진행중 (시안 작성 단계)

## [2026-08-26 11:26] 이상탐지+월별추이 대시보드 — nginx 배선 확인, 실 코드 이식 완료
- 지시: nginx에 /api/dashboard 프록시 추가함(사용자) → 확인 요청 2회. 확인 후 시안
  그대로 실 코드 이식 진행.
- nginx 배선 이슈 (사용자가 직접 고침, 내가 재현/확인만 함):
  1차: main.py엔 등록됐으나 nginx에 /api/dashboard 블록 자체가 없어 8000번 경유 시
  404(직접 8002는 401로 정상 — FastAPI 자체는 살아있음을 확인). 사용자가 블록 추가.
  2차: 블록은 추가됐지만 proxy_pass http://fastapi_local/; 처럼 끝에 슬래시가 있어
  nginx가 location 접두사를 그 경로로 치환 — /api/dashboard/monthly-trends 요청이
  FastAPI엔 /monthly-trends로 도착해 404. 다른 정상 블록(/api/anomalies 등)과
  동일하게 슬래시 제거하도록 안내, 사용자가 수정 후 재확인 → 정상(401) 확인.
- 실 코드 이식:
  - dashboard.js: DUMMY_DASHBOARD_DATA/TODO 제거. fetchDashboardData()가
    GET /api/anomalies + GET /api/dashboard/monthly-trends?year=<올해>를
    Promise.all로 병렬 호출. KPI 5개(최근달 매출/구매·전월대비, 연체총액,
    이상신호건수, 데이터기준월) 계산, 도메인별 추이 차트 + 이상탐지 카드 렌더.
    데이터 2개월 미만이면 안내 배너, API 실패 시 "불러오지 못했습니다" 안내로
    graceful degradation. role 미보유 시 접근거부 화면(기존 로직 유지).
  - style.css: kpi-row 4→5칸, kpi-delta를 kpi-sub 하위 요소로 정리, anomaly-card를
    실제 API 필드(entity/type/amount/detail/detected_at)에 맞춰 재작성 — 근거 없는
    severity/reason 표시는 제거. note-banner 스타일 추가.
- 검증: 실서버(8000)에서 hr 접근거부, finance 역할 시뮬레이션 시 두 API가 정확한
  URL(파라미터 포함)로 호출되고 401 응답에 graceful하게 에러 화면 표시되는 것까지
  확인. 실제 로그인 세션으로 200 응답 렌더링은 사용자가 확인 필요(내가 실 계정
  없음).
- 상태: 완료 (실 계정 최종 확인 대기)

## [2026-08-26 11:28] 이상탐지 카드 상위 4건만 표시 (바로 실행)
- 지시: 이상탐지 개수가 너무 많음 — 매출/구매 각 도메인별로 top 4만 화면에 표시.
- 저위험 단순 수정으로 판단, 시안 없이 바로 실행.
- 범위: django_app/web/static/web/dashboard.js, style.css
- 구현: domainSectionHtml()에서 도메인별 이상탐지 배열을 amount 내림차순 정렬 후
  상위 4건만 카드로 렌더(ANOMALY_DISPLAY_LIMIT=4). 배지 숫자는 전체 건수를 그대로
  유지(정보 누락처럼 보이지 않게), 4건 넘게 잘렸을 때만 "상위 N건만 표시합니다
  (전체 M건)" 안내 문구 추가.
- 검증: 매출 8건/구매 2건 더미로 확인 — 매출은 카드 4개만(금액 큰 순), 배지는 8
  유지, 안내 문구 정상. 구매는 2건 그대로(4 이하라 안내 없음).
- 상태: 완료



## [2026-08-26 16:00] hr 역할 탭 숨김이 CSS에 막혀 동작하지 않던 버그 수정
- 지시: hr 계정 접속 시 대시보드·리포트 생성 탭이 보이는 문제 확인 요청 → 두 탭을
  보이지 않게 하고 클릭도 못 하게 수정.
- 원인: auth.js는 `tab.hidden = !allowed`로 hidden 속성을 정상적으로 설정하고 있었으나,
  style.css의 `.top-tab { display: inline-flex; }`가 브라우저 UA 스타일시트의
  `[hidden] { display: none }`을 이겨서 무력화됨. 같은 파일 26행의
  `.login-screen[hidden] { display: none; }`은 이 문제를 이미 처리하고 있었는데
  탭에만 누락돼 있었음.
- 범위: django_app/web/static/web/style.css (1줄 추가)
- 실행 내용:
  - `.top-tab[hidden] { display: none; }` 을 `.top-tab` 규칙 바로 뒤에 추가.
    display:none이라 화면에서 사라지는 동시에 클릭·키보드 포커스 순서에서도 제외됨
    (별도 pointer-events나 tabindex 처리 불필요).
  - collectstatic 실행 후 로컬 gateway 재시작 — ManifestStaticFilesStorage가
    매니페스트를 프로세스 기동 시 메모리에 올리므로, 재시작 전에는 옛 해시 CSS가
    계속 서빙되어 수정이 반영되지 않았음.
- 검증: hr/admin 세션으로 실제 브라우저에서 확인.
  - hr: 대시보드·리포트 탭이 display:none, offsetParent null, 면적 0x0,
    elementFromPoint로 클릭 도달 불가, 키보드 순회 대상은 "채팅" 하나뿐.
  - admin: 세 탭 모두 display:flex로 정상 노출, 회귀 없음.
  - 이전 검증이 이 버그를 놓친 이유: `t.hidden`(DOM 속성)만 확인했는데 속성은
    정상적으로 true였음. 실제 렌더링 여부(offsetParent/computed display)를
    확인하지 않아 통과한 것으로 오판했음. 이번 검증 스크립트는 렌더링·클릭·
    포커스까지 함께 본다.
- 상태: 완료
