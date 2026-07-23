"""Production WSGI entrypoint with eager runtime activation."""

from backend.app_factory import create_app


app = create_app()
