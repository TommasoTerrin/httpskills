"""MCP HTTP adapter exposing a SkillLibrary over FastMCP with bearer-token auth."""

from collections.abc import Sequence

from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier

from httpskills.domain.library import SkillLibrary


def create_server(library: SkillLibrary, tokens: Sequence[str]) -> FastMCP:
    verifier = StaticTokenVerifier(
        tokens={token: {"client_id": token} for token in tokens}
    )
    mcp: FastMCP = FastMCP(name="httpskills", auth=verifier)

    @mcp.tool
    def list_skills() -> list[dict[str, str]]:
        return [
            {"name": summary.name.value, "description": summary.description}
            for summary in library.list_skills()
        ]

    @mcp.tool
    def get_skill(name: str) -> str:
        return library.get_skill(name).source_text

    @mcp.tool
    def get_resource(name: str, path: str) -> str:
        return library.get_resource(name, path).decode("utf-8")

    return mcp
