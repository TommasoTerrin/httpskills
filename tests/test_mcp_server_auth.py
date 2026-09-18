"""Auth behaviour of the MCP HTTP adapter, over the real transport.

Deliberately not the in-process `Client(fastmcp_instance)` shortcut the spec
calls an "in-process stub": that path never goes through HTTP, so it cannot
prove anything about bearer-token enforcement at the wire level. Every test
here binds a real socket and speaks real HTTP.
"""

import socket
import threading
import time
from pathlib import Path

import anyio
import pytest
from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from mcp.shared.exceptions import MCPError

from httpskills.adapters.filesystem_storage import FilesystemSkillStorage
from httpskills.adapters.mcp_server import create_server
from httpskills.domain.library import SkillLibrary


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


def _start_server(tmp_path: Path, tokens: list[str]) -> int:
    """Start create_server(...) over real HTTP in a background thread; return its port."""
    storage = FilesystemSkillStorage(tmp_path)
    library = SkillLibrary(storage)
    mcp = create_server(library, tokens)
    port = _free_port()

    thread = threading.Thread(
        target=lambda: mcp.run(transport="http", host="127.0.0.1", port=port),
        daemon=True,
    )
    thread.start()
    _wait_for_port(port)
    return port


def _url(port: int) -> str:
    return f"http://127.0.0.1:{port}/mcp"


# AC-FEAT-001-024
def test_no_bearer_token_is_rejected_before_any_catalogue_content_is_returned(
    tmp_path: Path,
) -> None:
    port = _start_server(tmp_path, ["token-a"])

    async def call() -> None:
        async with Client(_url(port)) as client:
            await client.call_tool("list_skills", {})

    with pytest.raises(MCPError):
        anyio.run(call)


# AC-FEAT-001-025
def test_token_absent_from_the_registry_is_rejected_like_no_token_at_all(
    tmp_path: Path,
) -> None:
    port = _start_server(tmp_path, ["token-a"])

    async def call() -> None:
        async with Client(_url(port), auth=BearerAuth("token-b")) as client:
            await client.call_tool("list_skills", {})

    with pytest.raises(MCPError):
        anyio.run(call)


# AC-FEAT-001-026
def test_every_registered_token_behaves_identically_across_all_three_tools(
    tmp_path: Path,
) -> None:
    port = _start_server(tmp_path, ["token-a", "token-b"])

    async def call_all(token: str) -> tuple[object, Exception | None, Exception | None]:
        async with Client(_url(port), auth=BearerAuth(token)) as client:
            listing = await client.call_tool("list_skills", {})

            skill_error: Exception | None = None
            try:
                await client.call_tool("get_skill", {"name": "does-not-exist"})
            except Exception as exc:  # domain-level rejection, not auth
                skill_error = exc

            resource_error: Exception | None = None
            try:
                await client.call_tool(
                    "get_resource", {"name": "does-not-exist", "path": "a.txt"}
                )
            except Exception as exc:  # domain-level rejection, not auth
                resource_error = exc

            return listing.data, skill_error, resource_error

    listing_a, skill_error_a, resource_error_a = anyio.run(call_all, "token-a")
    listing_b, skill_error_b, resource_error_b = anyio.run(call_all, "token-b")

    assert listing_a == listing_b == []
    assert skill_error_a is not None and skill_error_b is not None
    assert not isinstance(skill_error_a, MCPError)
    assert not isinstance(skill_error_b, MCPError)
    assert type(skill_error_a) is type(skill_error_b)
    assert resource_error_a is not None and resource_error_b is not None
    assert not isinstance(resource_error_a, MCPError)
    assert not isinstance(resource_error_b, MCPError)
    assert type(resource_error_a) is type(resource_error_b)
