from __future__ import annotations

from pathlib import Path
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".json", ".toml", ".yml", ".yaml", ".txt", ".ics"}


class PublicSafetyTests(unittest.TestCase):
    def test_public_files_do_not_contain_private_environment_markers(self) -> None:
        forbidden = {
            "c:\\users\\",
            "zhejiang tianran",
            "浙江天冉",
            ".hermes",
            "qwertyzhu",
        }
        findings: list[str] = []

        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            if any(part in {".git", ".venv", "__pycache__", "eval-workspace"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for marker in forbidden:
                if marker in text:
                    findings.append(f"{path.relative_to(ROOT)}: {marker}")

        self.assertFalse(findings, "Private environment markers found:\n" + "\n".join(findings))

    def test_current_enforcement_rule_does_not_reintroduce_obsolete_installment_logic(self) -> None:
        obsolete = "按每次履行期间的最后一日起分别判断"
        findings: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if obsolete in text:
                findings.append(str(path.relative_to(ROOT)))

        self.assertFalse(
            findings,
            "Obsolete installment-enforcement logic found; current PRC Civil Procedure Law Article 250 uses the last installment: "
            + ", ".join(findings),
        )

    def test_public_docx_xml_does_not_contain_private_environment_markers(self) -> None:
        forbidden = (
            "c:" + "\\users\\",
            "zhejiang " + "tianran",
            "浙江" + "天冉",
            "." + "hermes",
            "qwerty" + "zhu",
        )
        findings: list[str] = []
        for path in ROOT.rglob("*.docx"):
            if any(part in {".git", ".venv", "eval-workspace"} for part in path.parts):
                continue
            with zipfile.ZipFile(path, "r") as package:
                for member in package.namelist():
                    if not member.endswith((".xml", ".rels")):
                        continue
                    text = package.read(member).decode("utf-8", errors="ignore").lower()
                    for marker in forbidden:
                        if marker in text:
                            findings.append(f"{path.relative_to(ROOT)}::{member}: {marker}")

        self.assertFalse(findings, "Private environment markers found inside DOCX:\n" + "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
