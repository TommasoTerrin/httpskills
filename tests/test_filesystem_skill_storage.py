"""Integration tests for FilesystemSkillStorage against a real temp directory.

FilesystemSkillStorage(skills_root: Path) is the adapter under test: constructed
with the skills root as a `pathlib.Path`. This is adapter infrastructure, not a
numbered acceptance criterion, so no AC id is attached to these tests.
"""

from pathlib import Path

import pytest

from httpskills.adapters.filesystem_storage import FilesystemSkillStorage
from httpskills.domain.errors import ResourceNotFound


def _build_layout(tmp_path: Path) -> None:
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: A demo skill for adapter tests.\n---\n\nBody text.\n",
        encoding="utf-8",
    )

    references_dir = skill_dir / "references"
    references_dir.mkdir()
    (references_dir / "notes.md").write_bytes(b"Reference notes content.\n")

    assets_dir = skill_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "empty.txt").write_bytes(b"")

    not_a_skill_dir = tmp_path / "not-a-skill"
    not_a_skill_dir.mkdir()
    (not_a_skill_dir / "readme.txt").write_text("Not a skill.\n", encoding="utf-8")


def test_list_candidates_yields_only_directories_containing_skill_md(tmp_path: Path) -> None:
    _build_layout(tmp_path)
    storage = FilesystemSkillStorage(tmp_path)

    candidates = storage.list_candidates()

    assert len(candidates) == 1
    assert candidates[0].directory_name == "demo-skill"
    assert candidates[0].skill_md_text == (tmp_path / "demo-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "not-a-skill" not in [candidate.directory_name for candidate in candidates]


def test_resolve_returns_segments_pointing_at_the_real_target_and_skill_root(tmp_path: Path) -> None:
    _build_layout(tmp_path)
    storage = FilesystemSkillStorage(tmp_path)

    pair = storage.resolve("demo-skill", "references/notes.md")

    expected_notes_path = (tmp_path / "demo-skill" / "references" / "notes.md").resolve()
    expected_skill_root = (tmp_path / "demo-skill").resolve()

    assert Path(*pair.target) == expected_notes_path
    assert Path(*pair.skill_root) == expected_skill_root


def test_read_resource_returns_the_real_files_bytes(tmp_path: Path) -> None:
    _build_layout(tmp_path)
    storage = FilesystemSkillStorage(tmp_path)

    pair = storage.resolve("demo-skill", "references/notes.md")

    assert storage.read_resource(pair.target) == b"Reference notes content.\n"


def test_read_resource_on_an_existing_empty_file_returns_empty_bytes_not_an_error(tmp_path: Path) -> None:
    _build_layout(tmp_path)
    storage = FilesystemSkillStorage(tmp_path)

    pair = storage.resolve("demo-skill", "assets/empty.txt")

    assert storage.read_resource(pair.target) == b""


def test_read_resource_on_a_location_that_does_not_exist_raises_resource_not_found(tmp_path: Path) -> None:
    _build_layout(tmp_path)
    storage = FilesystemSkillStorage(tmp_path)

    pair = storage.resolve("demo-skill", "references/missing.md")

    with pytest.raises(ResourceNotFound):
        storage.read_resource(pair.target)
