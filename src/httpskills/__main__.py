"""Entrypoint: `python -m httpskills` starts the real MCP HTTP server.

Reads HTTPSKILLS_SKILLS_ROOT and HTTPSKILLS_TOKENS (see composition_root.py),
plus optional HTTPSKILLS_HOST / HTTPSKILLS_PORT, and serves until interrupted.
"""

import os

from httpskills.adapters.composition_root import build_server_from_env


def main() -> None:
    server = build_server_from_env()
    host = os.environ.get("HTTPSKILLS_HOST", "127.0.0.1")
    port = int(os.environ.get("HTTPSKILLS_PORT", "8000"))
    server.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()
