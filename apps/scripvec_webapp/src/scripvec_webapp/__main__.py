"""Entry point for `python -m scripvec_webapp` / `scripvec-web`."""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the scripvec web front-end.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (dev only).",
    )
    args = parser.parse_args()

    uvicorn.run(
        "scripvec_webapp.main:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
