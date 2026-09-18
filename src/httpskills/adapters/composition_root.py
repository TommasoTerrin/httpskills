"""Composition root: wires adapters and environment into a runnable server.

Environment (skills root path, token set) is resolved here, at the edge, and
passed as arguments into the core — never read inside the domain.
"""

import os
from pathlib import Path

from fastmcp import FastMCP

from httpskills.adapters.filesystem_storage import FilesystemSkillStorage
from httpskills.adapters.mcp_server import create_server
from httpskills.domain.library import SkillLibrary

SKILLS_ROOT_ENV_VAR = "HTTPSKILLS_SKILLS_ROOT"
TOKENS_ENV_VAR = "HTTPSKILLS_TOKENS"


def build_server_from_env() -> FastMCP:
    skills_root = Path(os.environ[SKILLS_ROOT_ENV_VAR])

    raw_tokens = os.environ.get(TOKENS_ENV_VAR, "")
    tokens = [token for token in raw_tokens.split(",") if token]
    if not tokens:
        raise ValueError(
            f"{TOKENS_ENV_VAR} must contain at least one comma-separated bearer "
            "token; a server nobody can authenticate against is not a valid "
            "configuration."
        )

    storage = FilesystemSkillStorage(skills_root)
    library = SkillLibrary(storage)
    return create_server(library, tokens)
