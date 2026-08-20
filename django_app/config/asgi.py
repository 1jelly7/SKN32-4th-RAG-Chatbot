"""Django ASGI 서버 진입점."""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.config.settings")

application = get_asgi_application()
