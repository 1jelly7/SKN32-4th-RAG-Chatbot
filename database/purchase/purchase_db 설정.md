# 구매(Purchase) DB 설정 요약

```bash
# 1. 패키지 설치
pip install mysql-connector-python

# 2. DB + 관리자 계정 생성
mysql -u root -p < database/purchase/create_purchase_db.sql

# 3. 테이블 생성 + 데이터 적재
python etl/purchase/main.py    # ✓ Success: 5/5 확인

# 4. 조회용 View 생성 (아래 SQL 파일 실행)
mysql -u JangGGo -p1234 -h 127.0.0.1 purchase_db < database/purchase/views.sql

# 5. 조회 전용 계정(purchase_reader) 권한 부여
mysql -u JangGGo -p purchase_db < database/purchase/grants_reader.sql
```

```
# 6. .env에 추가
PURCHASE_DB_HOST=127.0.0.1
PURCHASE_DB_USER=purchase
PURCHASE_DB_PASSWORD=1234
PURCHASE_DB_DATABASE=purchase_db
PURCHASE_READ_USER=purchase_reader
PURCHASE_READ_PASSWORD=purchase_read_1234
```

```bash
# 7. 확인 (성공 / Access denied 각각 정상)
mysql -u purchase_reader -ppurchase_read_1234 -h 127.0.0.1 purchase_db -e "SELECT COUNT(*) FROM v_purchase_order;"
mysql -u purchase_reader -ppurchase_read_1234 -h 127.0.0.1 purchase_db -e "SELECT * FROM vendors LIMIT 1;"

# 8. 앱 실행 후 구매 관련 질문으로 최종 확인
uvicorn app.main:app --reload
```

> `database/purchase/schema.sql`, `scripts/Create purchase views.py`, `scripts/load_purchase_data.py`는 쓰지 않습니다(실제 스키마와 불일치).
