"""이전 진입점의 얇은 shim.

구매 ETL의 정식 진입점은 이제 `etl.purchase.run_all`이다(sales와 통일).
이 파일은 `python -m etl.purchase.main`에 익숙한 사람이 실수로 옛 경로를
불러도 조용히 실패하지 않도록 남겨둔 안내용 shim이며, 다음 정리 때 삭제 대상이다.

    python -m etl.purchase.main [xlsx_path]
"""
from __future__ import annotations

import sys

from etl.purchase.run_all import run_all

if __name__ == "__main__":
    print(
        "이 진입점은 etl.purchase.run_all로 대체되었습니다. "
        "앞으로는 'python -m etl.purchase.run_all'을 사용하세요.",
        file=sys.stderr,
    )
    run_all()
