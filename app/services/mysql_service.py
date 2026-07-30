"""
MySQL 연결과 예제 지식 테이블 조회 기능을 제공합니다.
"""

# MySQL 서버에 연결하기 위해 mysql.connector를 가져옵니다.
import mysql.connector

# 설정 모델을 가져옵니다.
from app.config.settings import Settings


# MySQL 서비스 클래스를 정의합니다.
class MySQLService:
    """MySQL 연결 상태 확인과 안전한 예제 조회를 담당합니다."""

    # 설정 객체를 전달받습니다.
    def __init__(self, settings: Settings) -> None:
        # 설정을 저장합니다.
        self.settings = settings

    # MySQL 연결 객체를 생성합니다.
    def _connect(self):
        """환경설정에 지정된 MySQL 서버에 연결합니다."""

        # MySQL 기능이 비활성화되어 있으면 명확한 오류를 발생시킵니다.
        if not self.settings.mysql_enabled:
            raise RuntimeError("MYSQL_ENABLED=false입니다. .env에서 MySQL 기능을 활성화하세요.")

        # 환경설정 값으로 MySQL 연결을 생성하여 반환합니다.
        return mysql.connector.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            database=self.settings.mysql_database,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
        )

    # 예제 테이블을 생성합니다.
    def initialize(self) -> dict:
        """지식 저장용 knowledge_items 테이블을 생성합니다."""

        # MySQL 연결을 엽니다.
        connection = self._connect()

        # SQL 실행 후에도 연결이 닫히도록 try/finally를 사용합니다.
        try:
            # 커서를 생성합니다.
            cursor = connection.cursor()

            # 테이블이 없을 때만 생성하는 SQL을 실행합니다.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # 테이블 생성 작업을 확정합니다.
            connection.commit()

            # 성공 결과를 반환합니다.
            return {"message": "knowledge_items 테이블 준비 완료"}
        finally:
            # 열린 MySQL 연결을 항상 닫습니다.
            connection.close()

    # 모든 예제 지식 데이터를 조회합니다.
    def list_items(self) -> list[dict]:
        """knowledge_items 테이블의 데이터를 최신 순으로 조회합니다."""

        # MySQL 연결을 엽니다.
        connection = self._connect()

        # 조회 후에도 연결이 닫히도록 try/finally를 사용합니다.
        try:
            # 조회 결과를 딕셔너리로 받는 커서를 생성합니다.
            cursor = connection.cursor(dictionary=True)

            # 전체 데이터를 최신 ID 순으로 조회합니다.
            cursor.execute(
                "SELECT id, title, content, created_at "
                "FROM knowledge_items ORDER BY id DESC"
            )

            # 모든 행을 가져와 반환합니다.
            return cursor.fetchall()
        finally:
            # 열린 MySQL 연결을 항상 닫습니다.
            connection.close()

    # 예제 지식 데이터를 추가합니다.
    def add_item(self, title: str, content: str) -> dict:
        """제목과 본문을 MySQL에 안전하게 저장합니다."""

        # MySQL 연결을 엽니다.
        connection = self._connect()

        # 저장 후에도 연결이 닫히도록 try/finally를 사용합니다.
        try:
            # 커서를 생성합니다.
            cursor = connection.cursor()

            # 파라미터 바인딩 방식으로 SQL Injection 위험을 낮춥니다.
            cursor.execute(
                "INSERT INTO knowledge_items(title, content) VALUES (%s, %s)",
                (title, content),
            )

            # INSERT 작업을 확정합니다.
            connection.commit()

            # 생성된 기본키 값을 반환합니다.
            return {"id": cursor.lastrowid, "title": title, "content": content}
        finally:
            # 열린 MySQL 연결을 항상 닫습니다.
            connection.close()
