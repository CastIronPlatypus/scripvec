"""scripvec webapp — FastAPI shell wrapping the scripvec CLI (CR-010)."""

from .main import create_app

__all__ = ["create_app"]
