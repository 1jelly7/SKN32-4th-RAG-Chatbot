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

    # ------------------------------------------------------------------
    # 문서 메타데이터 + 경로 테이블 (RAG가 docs 폴더 대신 여기서 목록을 가져옵니다)
    # ------------------------------------------------------------------
    #
    # 실제 파일(PDF 바이트)은 DB가 아니라 파일시스템(또는 S3 등 객체 스토리지)에 그대로 두고,
    # MySQL에는 "그 파일이 어디 있는지(file_path)"와 부서/업로드일 같은 메타데이터만 저장합니다.
    # DB에 파일 원본을 통째로 BLOB로 넣는 방식은 DB 용량/백업이 급격히 커지고 조회 성능도
    # 나빠져서 실무에서는 잘 쓰지 않고, "경로 포인터 + 메타데이터"가 표준적인 방식입니다.

    # documents 테이블을 생성합니다.
    def initialize_documents_table(self) -> dict:
        """문서 경로/메타데이터 테이블을 생성합니다."""

        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    filename VARCHAR(255) NOT NULL UNIQUE,
                    file_path VARCHAR(500) NOT NULL,
                    department VARCHAR(100),
                    category VARCHAR(100),
                    version_date DATE,
                    allowed_departments VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()
            return {"message": "documents 테이블 준비 완료"}
        finally:
            connection.close()

    # 문서 메타데이터를 등록하거나 갱신합니다.
    def upsert_document(
        self,
        filename: str,
        file_path: str,
        department: str | None = None,
        category: str | None = None,
        version_date: str | None = None,
        allowed_departments: str | None = None,
    ) -> dict:
        """문서 1건의 경로와 메타데이터를 등록(또는 갱신)합니다.

        allowed_departments: 이 문서를 열람할 수 있는 부서를 콤마로 구분해 적습니다.
        비워두면(None) "전체 공개" 문서로 취급되어 모든 부서가 열람할 수 있습니다.
        예: "인사팀,재무팀" 으로 지정하면 두 부서만 검색 결과에 노출됩니다.
        """

        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO documents
                    (filename, file_path, department, category, version_date, allowed_departments)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    file_path = VALUES(file_path),
                    department = VALUES(department),
                    category = VALUES(category),
                    version_date = VALUES(version_date),
                    allowed_departments = VALUES(allowed_departments)
                """,
                (filename, file_path, department, category, version_date, allowed_departments),
            )
            connection.commit()
            return {"filename": filename, "file_path": file_path}
        finally:
            connection.close()

    # RAG 인덱싱이 참조할 활성 문서 목록(경로 포함)을 조회합니다.
    def list_documents(self, active_only: bool = True) -> list[dict]:
        """documents 테이블에서 파일 경로 + 메타데이터 목록을 조회합니다."""

        connection = self._connect()
        try:
            cursor = connection.cursor(dictionary=True)
            query = (
                "SELECT id, filename, file_path, department, category, "
                "version_date, allowed_departments, uploaded_at FROM documents"
            )
            if active_only:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY filename"
            cursor.execute(query)
            return cursor.fetchall()
        finally:
            connection.close()

    # 단일 문서의 메타데이터를 파일명으로 조회합니다.
    def get_document(self, filename: str) -> dict | None:
        """파일명으로 문서 1건의 메타데이터(경로 포함)를 조회합니다."""

        connection = self._connect()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, filename, file_path, department, category, "
                "version_date, allowed_departments FROM documents WHERE filename = %s",
                (filename,),
            )
            return cursor.fetchone()
        finally:
            connection.close()
