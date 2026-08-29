from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = ROOT / "scripts" / "run_demo.py"
READMES = (ROOT / "README.md", ROOT / "README.zh-CN.md")
SKILL_PATHS = (
    "skills/contract-comment-review",
    "skills/legal-deadline-extractor",
)
_MD_LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_RELEASE_ASSET = re.compile(
    r"https://github.com/qwertyzhu/openlawkit/releases/latest/download/([A-Za-z0-9._-]+)"
)
_INSTALL_TOKENS = (
    "python -m pip install -e .",
    "python scripts/run_demo.py --clean",
    "demo-output/reviewed.docx",
    "demo-output/contract-verification.json",
    "2026-06-23",
    *SKILL_PATHS,
    "contract-comment-review.skill",
    "legal-deadline-extractor.skill",
    "SHA256SUMS.txt",
    "原生批注",
    "触发事实",
)


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match is not None, "pyproject.toml missing project version"
    return match.group(1)


def _readme_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _local_markdown_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for raw in _MD_LINK.findall(markdown):
        if raw.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = raw.split("#", 1)[0]
        if path:
            targets.append(path)
    return targets


def _shipped_release_assets() -> set[str]:
    skills = {
        path.name + ".skill"
        for path in sorted((ROOT / "skills").iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    return skills | {"SHA256SUMS.txt"}


def _run_demo(output_dir: Path) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(DEMO_SCRIPT), "--output-dir", str(output_dir)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_public_versions_agree() -> None:
    version = _pyproject_version()
    plugin = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert plugin["version"] == version
    assert re.search(rf"(?m)^## {re.escape(version)}(?: |$)", changelog)


def test_readme_relative_paths_exist() -> None:
    missing: list[str] = []
    for readme in READMES:
        for target in _local_markdown_targets(_readme_text(readme)):
            destination = (ROOT / target).resolve()
            try:
                destination.relative_to(ROOT.resolve())
            except ValueError:
                missing.append(f"{readme.name}: {target} escapes repository root")
                continue
            if not (ROOT / target).exists():
                missing.append(f"{readme.name}: {target}")
    assert not missing, "README points at missing local paths:\n" + "\n".join(missing)


def test_readme_release_assets_match_shipped_skills() -> None:
    allowed = _shipped_release_assets()
    for readme in READMES:
        assets = _RELEASE_ASSET.findall(_readme_text(readme))
        assert assets, f"{readme.name} has no GitHub Release download links"
        unexpected = sorted(set(assets) - allowed)
        assert not unexpected, f"{readme.name} names missing release assets: {unexpected}"
        for required in allowed:
            assert required in _readme_text(readme), f"{readme.name} omits {required}"


def test_readme_bilingual_install_and_demo_claims() -> None:
    for readme in READMES:
        text = _readme_text(readme)
        for token in _INSTALL_TOKENS:
            assert token in text, f"{readme.name} is missing {token!r}"
        for skill in SKILL_PATHS:
            assert (ROOT / skill / "SKILL.md").is_file()
        assert (ROOT / "scripts" / "run_demo.py").is_file()


def test_public_descriptions_include_chinese() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    plugin = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert "中国法" in pyproject
    assert "中国法" in plugin["description"]
    assert "原生批注" in plugin["interface"]["shortDescription"]
    contract_meta = (
        ROOT / "skills" / "contract-comment-review" / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
    deadline_meta = (
        ROOT / "skills" / "legal-deadline-extractor" / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
    assert "原生批注" in contract_meta
    assert "可审计中国法期限" in deadline_meta


def test_readme_good_first_issue_claim_is_bilingual() -> None:
    mentions = ["good first issue" in _readme_text(path) for path in READMES]
    assert mentions[0] == mentions[1], "README EN/ZH disagree about good first issue"


def test_run_demo_script_produces_documented_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo-output"
    result = _run_demo(output_dir)
    assert result.returncode == 0, result.stderr or result.stdout

    reviewed = output_dir / "reviewed.docx"
    verification = output_dir / "contract-verification.json"
    deadlines_json = output_dir / "deadlines" / "deadlines.json"
    deadlines_md = output_dir / "deadlines" / "deadlines.md"

    assert reviewed.is_file() and reviewed.stat().st_size > 0
    with zipfile.ZipFile(reviewed) as package:
        names = package.namelist()
    assert "word/document.xml" in names
    assert "word/comments.xml" in names

    payload = json.loads(verification.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["new_comment_count"] >= 1

    deadline_payload = json.loads(deadlines_json.read_text(encoding="utf-8"))
    item = deadline_payload["results"][0]
    assert item["status"] == "confirmed"
    assert item["due_date"] == "2026-06-23"
    assert item["rule_id"]
    assert "2026-06-23" in deadlines_md.read_text(encoding="utf-8")
