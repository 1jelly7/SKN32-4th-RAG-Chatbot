"""Django 관리 명령 진입점."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    """프로젝트 루트를 import 경로에 추가하고 Django 명령을 실행한다."""
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.config.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
