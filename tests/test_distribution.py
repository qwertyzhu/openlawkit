from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import zipfile
from pathlib import Path
import sys
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = ROOT / "scripts" / "run_demo.py"
PACK_SCRIPT = ROOT / "scripts" / "pack_skills.py"

DEMO_SPEC = importlib.util.spec_from_file_location("openlawkit_run_demo", DEMO_SCRIPT)
assert DEMO_SPEC is not None and DEMO_SPEC.loader is not None
run_demo = importlib.util.module_from_spec(DEMO_SPEC)
sys.modules[DEMO_SPEC.name] = run_demo
DEMO_SPEC.loader.exec_module(run_demo)

PACK_SPEC = importlib.util.spec_from_file_location("openlawkit_pack_skills", PACK_SCRIPT)
assert PACK_SPEC is not None and PACK_SPEC.loader is not None
pack_skills = importlib.util.module_from_spec(PACK_SPEC)
sys.modules[PACK_SPEC.name] = pack_skills
PACK_SPEC.loader.exec_module(pack_skills)


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match is not None, "pyproject.toml missing project version"
    return match.group(1)


def test_plugin_manifest_points_to_real_components() -> None:
    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "openlawkit"
    assert manifest["version"] == _pyproject_version()
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


def test_demo_clean_falls_back_when_is_mount_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = tmp_path / "demo-output"
    selected.mkdir()
    (selected / "must-survive.txt").write_text("keep", encoding="utf-8")

    def boom(self: Path) -> bool:
        raise NotImplementedError("Path.is_mount() is unsupported on this system")

    monkeypatch.setattr(Path, "is_mount", boom, raising=False)

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


def test_pack_skills_builds_reproducible_runtime_archives(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    archives = pack_skills.pack_skills(ROOT, first, expect_version=_pyproject_version())
    pack_skills.pack_skills(ROOT, second, expect_version=_pyproject_version())

    names = [path.name for path in archives]
    assert names == [
        "contract-comment-review.skill",
        "legal-deadline-extractor.skill",
    ]

    checksums = (first / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
    assert checksums == (second / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()

    for archive in archives:
        replica = second / archive.name
        assert archive.read_bytes() == replica.read_bytes()
        digest = hashlib.sha256(archive.read_bytes()).hexdigest().upper()
        assert f"{digest}  {archive.name}" in checksums

        with zipfile.ZipFile(archive) as package:
            members = package.namelist()
        assert f"{archive.stem}/SKILL.md" in members
        assert all(member.startswith(f"{archive.stem}/") for member in members)
        assert all("\\" not in member for member in members)
        assert not any("/evals/" in member or member.endswith(".pyc") for member in members)
        assert any(member.startswith(f"{archive.stem}/scripts/") for member in members)
        assert any(member.startswith(f"{archive.stem}/agents/") for member in members)

    notes = (first / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert notes.startswith(f"OpenLawKit {_pyproject_version()}")
    assert f"## {_pyproject_version()}" in notes
    assert "reproducible `.skill` packer" in notes
    assert "No silent changes to contract body text." in notes


def test_packed_deadline_skill_still_calculates_confirmed_fixture(tmp_path: Path) -> None:
    archives = {
        path.name: path
        for path in pack_skills.pack_skills(ROOT, tmp_path / "dist")
    }
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archives["legal-deadline-extractor.skill"]) as package:
        package.extractall(extracted)

    output_dir = tmp_path / "deadlines"
    result = subprocess.run(
        [
            sys.executable,
            str(extracted / "legal-deadline-extractor" / "scripts" / "calculate_deadlines.py"),
            str(ROOT / "examples" / "deadline-extractor" / "fictional-labor-facts.json"),
            "--rules",
            str(extracted / "legal-deadline-extractor" / "references" / "rules.json"),
            "--holidays",
            str(extracted / "legal-deadline-extractor" / "references" / "holidays-cn-2026.json"),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads((output_dir / "deadlines.json").read_text(encoding="utf-8"))
    item = payload["results"][0]
    assert item["status"] == "confirmed"
    assert item["due_date"] == "2026-06-23"


def test_packed_contract_skill_still_adds_native_comments(tmp_path: Path) -> None:
    archives = {
        path.name: path
        for path in pack_skills.pack_skills(ROOT, tmp_path / "dist")
    }
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archives["contract-comment-review.skill"]) as package:
        package.extractall(extracted)

    reviewed = tmp_path / "reviewed.docx"
    added = subprocess.run(
        [
            sys.executable,
            str(extracted / "contract-comment-review" / "scripts" / "add_comments.py"),
            str(ROOT / "examples" / "contract-review" / "fictional-service-contract.docx"),
            str(ROOT / "examples" / "contract-review" / "fictional-findings.json"),
            "-o",
            str(reviewed),
            "--timestamp",
            "2026-01-01T00:00:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert added.returncode == 0, added.stderr

    report = tmp_path / "verification.json"
    verified = subprocess.run(
        [
            sys.executable,
            str(extracted / "contract-comment-review" / "scripts" / "verify_comments.py"),
            str(ROOT / "examples" / "contract-review" / "fictional-service-contract.docx"),
            str(reviewed),
            str(ROOT / "examples" / "contract-review" / "fictional-findings.json"),
            "--report",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert verified.returncode == 0, verified.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["new_comment_count"] == 5


def test_pack_skills_rejects_version_mismatch(tmp_path: Path) -> None:
    with pytest.raises(pack_skills.PackError, match="expected '0.0.0'"):
        pack_skills.pack_skills(ROOT, tmp_path, expect_version="0.0.0")


def test_pack_skills_rejects_plugin_version_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pack_skills, "plugin_version", lambda root: "9.9.9")
    with pytest.raises(pack_skills.PackError, match="plugin.json has '9.9.9'"):
        pack_skills.pack_skills(ROOT, tmp_path)


def test_changelog_section_matches_dated_headings() -> None:
    body = pack_skills.changelog_section(
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        _pyproject_version(),
    )
    assert body.startswith(f"## {_pyproject_version()}")
    assert "reproducible `.skill` packer" in body


def test_pack_skills_project_version_matches_pyproject() -> None:
    assert pack_skills.project_version(ROOT) == _pyproject_version()


def test_project_version_ignores_non_project_tables(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[build-system]\nrequires = ["setuptools>=69"]\n\n'
        '[project]\nname = "openlawkit"\nversion = "9.9.9"\n',
        encoding="utf-8",
    )
    assert pack_skills.project_version(tmp_path) == "9.9.9"


def test_changelog_section_rejects_missing_version() -> None:
    with pytest.raises(pack_skills.PackError, match="missing a 0.0.0 section"):
        pack_skills.changelog_section("# Changelog\n\n## 1.0.0\n\n- x\n", "0.0.0")
