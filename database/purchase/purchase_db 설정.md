# 구매(Purchase) DB 설정 요약

> **2026-08-03 수정**: DB 이름이 `purchase_db`로 잘못 적혀 있었다(실제는 `purchase`
> — `etl/purchase/config.py`의 `DB_CONFIG['database']` 기준). 4번 단계 계정도
> `JangGGo`가 아니라 ETL 계정 `purchase`로, 5번 단계는 `CREATE USER`가 전역 권한이라
> `root`로 바로잡았다. Windows PowerShell에서는 `<` 리다이렉션이 안 되므로
> `Get-Content 파일 | mysql ...` 형태를 함께 적었다.

```bash
# 1. 패키지 설치
pip install mysql-connector-python

# 2. DB + ETL 계정 생성 (root로 실행)
mysql -u root -p < database/purchase/create_purchase_db.sql
```
```powershell
Get-Content database/purchase/create_purchase_db.sql | mysql -u root -p
```

```bash
# 3. 테이블 생성 + 데이터 적재
python -m etl.purchase.main    # ✓ Success: 5/5 확인
```

```bash
# 4. 조회용 View 생성 (ETL 계정 purchase로 — CREATE VIEW는 DB 소유 권한만 있으면 됨)
mysql -u purchase -p1234 -h 127.0.0.1 purchase < database/purchase/views.sql
```
```powershell
Get-Content database/purchase/views.sql | mysql -u purchase -p1234 -h 127.0.0.1 purchase
```

```bash
# 5. 조회 전용 계정(purchase_reader) 권한 부여 (root로 실행 — CREATE USER는 전역 권한)
mysql -u root -p purchase < database/purchase/grants_reader.sql
```
```powershell
Get-Content database/purchase/grants_reader.sql | mysql -u root -p purchase
```

```
# 6. .env에 추가
PURCHASE_DB_HOST=127.0.0.1
PURCHASE_DB_USER=purchase
PURCHASE_DB_PASSWORD=1234
PURCHASE_DB_DATABASE=purchase
PURCHASE_READ_USER=purchase_reader
PURCHASE_READ_PASSWORD=purchase_read_1234
```

```bash
# 7. 확인 (성공 / Access denied 각각 정상)
mysql -u purchase_reader -ppurchase_read_1234 -h 127.0.0.1 purchase -e "SELECT COUNT(*) FROM v_purchase_order;"
mysql -u purchase_reader -ppurchase_read_1234 -h 127.0.0.1 purchase -e "SELECT * FROM vendors LIMIT 1;"
```

```bash
# 8. 앱 실행 후 구매 관련 질문으로 최종 확인
uvicorn app.main:app --reload
```

> `database/purchase/schema.sql`, `scripts/Create purchase views.py`, `scripts/load_purchase_data.py`는 쓰지 않습니다(실제 스키마와 불일치).
>
> **주의**: 5번을 실행하기 전에 예전에 수동으로 만든 `'purchase_reader'@'localhost'`
> 계정(있다면)을 정리해야 한다. 5번은 `'purchase_reader'@'%'`를 만드는데, 호스트가
> 달라서 둘 다 남아있으면 어느 쪽으로 접속되는지 헷갈릴 수 있다:
> `DROP USER IF EXISTS 'purchase_reader'@'localhost';` (root로 실행)
