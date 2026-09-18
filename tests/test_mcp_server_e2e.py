"""End-to-end coverage of the shipped demo-skill fixture, over the real MCP transport.

Deliberately not the in-process `Client(fastmcp_instance)` shortcut the spec
calls an "in-process stub": every call here goes over a real socket speaking
real HTTP, exercising `skills/demo-skill/` exactly as a real client would.
"""

import socket
import threading
import time
from pathlib import Path

import anyio
from fastmcp import Client
from fastmcp.client.auth import BearerAuth

from httpskills.adapters.filesystem_storage import FilesystemSkillStorage
from httpskills.adapters.mcp_server import create_server
from httpskills.domain.library import SkillLibrary

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"

# Known content of the shipped fixture, from an independent source (the
# literal bytes written when the fixture was created) rather than recomputed
# by re-reading through the same code paths under test.
DEMO_SKILL_DESCRIPTION = (
    "A minimal fixture skill shipped with httpskills, demonstrating "
    "references and assets."
)
DEMO_SKILL_MD = (
    "---\n"
    "name: demo-skill\n"
    "description: A minimal fixture skill shipped with httpskills, demonstrating references and assets.\n"
    "license: MIT\n"
    "---\n"
    "\n"
    "# Demo Skill\n"
    "\n"
    "This is the one test skill shipped with the httpskills feature. It exists\n"
    "to be served end-to-end over the real MCP transport.\n"
)
DEMO_NOTES_MD = (
    "# Reference Notes\n"
    "\n"
    "This is a small reference file for the demo-skill fixture.\n"
)
DEMO_EXAMPLE_TXT = "This is a small asset file for the demo-skill fixture.\n"


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


def _start_server() -> int:
    storage = FilesystemSkillStorage(SKILLS_ROOT)
    library = SkillLibrary(storage)
    mcp = create_server(library, ["a-test-token"])
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


# AC-FEAT-001-027
def test_ac_feat_001_027_the_shipped_demo_skill_is_served_end_to_end_over_real_transport() -> (
    None
):
    port = _start_server()

    async def call_all() -> tuple[list[dict[str, object]], str, str, str]:
        async with Client(_url(port), auth=BearerAuth("a-test-token")) as client:
            listing = await client.call_tool("list_skills", {})
            skill_md = await client.call_tool("get_skill", {"name": "demo-skill"})
            notes = await client.call_tool(
                "get_resource",
                {"name": "demo-skill", "path": "references/notes.md"},
            )
            example = await client.call_tool(
                "get_resource",
                {"name": "demo-skill", "path": "assets/example.txt"},
            )
            return listing.data, skill_md.data, notes.data, example.data

    listing, skill_md, notes, example = anyio.run(call_all)

    assert {"name": "demo-skill", "description": DEMO_SKILL_DESCRIPTION} in listing
    assert skill_md == DEMO_SKILL_MD
    assert notes == DEMO_NOTES_MD
    assert example == DEMO_EXAMPLE_TXT
