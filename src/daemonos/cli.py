"""DaemonOS CLI."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="daemonos", description="DaemonOS control plane")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Start the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)

    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn
        from daemonos.api import create_app

        app = create_app()
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
