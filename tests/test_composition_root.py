"""Coverage for the composition root: `build_server_from_env`.

Not tied to a numbered acceptance criterion — this is wiring/infrastructure
(the D7 requirement that tokens live in the environment, never the repo),
covered here directly rather than via check-traceability.
"""

import socket
import threading
import time

import anyio
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.auth import BearerAuth

from httpskills.adapters.composition_root import build_server_from_env


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"server did not start listening on port {port} in time")


def test_build_server_from_env_wires_a_working_authenticated_server(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("HTTPSKILLS_SKILLS_ROOT", str(tmp_path))
    monkeypatch.setenv("HTTPSKILLS_TOKENS", "token-a,token-b")

    mcp = build_server_from_env()

    assert isinstance(mcp, FastMCP)

    port = _free_port()
    thread = threading.Thread(
        target=lambda: mcp.run(transport="http", host="127.0.0.1", port=port),
        daemon=True,
    )
    thread.start()
    _wait_for_port(port)

    async def call() -> list[dict[str, object]]:
        async with Client(
            f"http://127.0.0.1:{port}/mcp", auth=BearerAuth("token-b")
        ) as client:
            result = await client.call_tool("list_skills", {})
            return result.data

    listing = anyio.run(call)

    # An empty tmp_path skills root has no skills to list, but the call
    # succeeding at all (authenticated with the second comma-separated
    # token) proves the server was wired end-to-end from the environment.
    assert listing == []
