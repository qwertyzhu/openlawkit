from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tomllib
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = ROOT / "scripts" / "run_demo.py"
SPEC = importlib.util.spec_from_file_location("openlawkit_run_demo", DEMO_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
run_demo = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run_demo
SPEC.loader.exec_module(run_demo)


def test_plugin_manifest_points_to_real_components() -> None:
    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "openlawkit"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["version"] == project["project"]["version"]
    skills_path = (ROOT / manifest["skills"]).resolve()
    assert skills_path == (ROOT / "skills").resolve()
    assert (skills_path / "contract-comment-review" / "SKILL.md").is_file()
    assert (skills_path / "legal-deadline-extractor" / "SKILL.md").is_file()


def test_openai_skill_metadata_exists() -> None:
    for skill in ("contract-comment-review", "legal-deadline-extractor"):
        metadata = ROOT / "skills" / skill / "agents" / "openai.yaml"
        text = metadata.read_text(encoding="utf-8")
        assert "display_name:" in text
        assert "default_prompt:" in text
        assert "allow_implicit_invocation: true" in text


def test_demo_clean_refuses_symlink_without_deleting_target(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "must-survive.txt"
    sentinel.write_text("keep", encoding="utf-8")
    linked_output = tmp_path / "demo-output"
    try:
        linked_output.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable on this platform: {exc}")

    with pytest.raises(ValueError, match="refuses a symlink"):
        run_demo.clean_demo_output(linked_output, linked_output)

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_demo_clean_falls_back_when_is_mount_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = tmp_path / "demo-output"
    selected.mkdir()
    sentinel = selected / "must-survive.txt"
    sentinel.write_text("keep", encoding="utf-8")

    monkeypatch.delattr(Path, "is_mount", raising=False)

    run_demo.clean_demo_output(selected, selected)

    assert not selected.exists()


def test_demo_clean_refuses_any_other_lexical_directory(tmp_path: Path) -> None:
    selected = tmp_path / "outside"
    selected.mkdir()

    with pytest.raises(ValueError, match="limited to"):
        run_demo.clean_demo_output(selected, tmp_path / "demo-output")

    assert selected.is_dir()


def test_demo_clean_refuses_windows_junction_marker(tmp_path: Path) -> None:
    selected = tmp_path / "demo-output"
    selected.mkdir()
    sentinel = selected / "must-survive.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with mock.patch.object(
        type(selected), "is_junction", return_value=True, create=True
    ):
        with pytest.raises(ValueError, match="junction"):
            run_demo.clean_demo_output(selected, selected)

    assert sentinel.read_text(encoding="utf-8") == "keep"
