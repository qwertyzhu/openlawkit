from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "examples" / "contract-review" / "build_fixture.py"
FINDINGS = ROOT / "examples" / "contract-review" / "fictional-findings.json"
ADD_COMMENTS = (
    ROOT / "skills" / "contract-comment-review" / "scripts" / "add_comments.py"
)
VERIFY_COMMENTS = (
    ROOT / "skills" / "contract-comment-review" / "scripts" / "verify_comments.py"
)
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def run_cli(*arguments: object) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, *(str(argument) for argument in arguments)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def document_body_text(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as package:
        root = etree.fromstring(package.read("word/document.xml"))
    paragraphs = root.xpath("/w:document/w:body/w:p", namespaces=NS)
    return "\n".join(
        "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        for paragraph in paragraphs
    )


class ContractCommentReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.work = Path(self._temporary.name)
        self.input_docx = self.work / "input.docx"
        built = run_cli(BUILDER, self.input_docx)
        self.assertEqual(built.returncode, 0, built.stderr)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def test_native_comments_preserve_body_text_and_exact_anchors(self) -> None:
        reviewed = self.work / "reviewed.docx"
        added = run_cli(
            ADD_COMMENTS,
            self.input_docx,
            FINDINGS,
            "-o",
            reviewed,
            "--timestamp",
            "2026-01-01T00:00:00Z",
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertTrue(reviewed.is_file())

        report_path = self.work / "verification.json"
        verified = run_cli(
            VERIFY_COMMENTS,
            self.input_docx,
            reviewed,
            FINDINGS,
            "--report",
            report_path,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["new_comment_count"], 5)
        self.assertTrue(all(report["checks"].values()))

        before = document_body_text(self.input_docx)
        after = document_body_text(reviewed)
        self.assertEqual(before, after)
        self.assertEqual(
            hashlib.sha256(before.encode("utf-8")).hexdigest(),
            report["body_text_sha256"],
        )

        with zipfile.ZipFile(reviewed, "r") as package:
            self.assertIn("word/comments.xml", package.namelist())
            comments_root = etree.fromstring(package.read("word/comments.xml"))
        comments = comments_root.xpath("./w:comment", namespaces=NS)
        self.assertEqual(len(comments), 5)
        authors = [comment.get(f"{{{W_NS}}}author") for comment in comments]
        self.assertEqual(authors.count("OpenLawKit-High"), 4)
        self.assertEqual(authors.count("OpenLawKit-Medium"), 1)
        for comment in comments:
            text = "\n".join(
                "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
                for paragraph in comment.xpath("./w:p", namespaces=NS)
            )
            self.assertIn("【问题类型】", text)
            self.assertIn("【风险原因】", text)
            self.assertIn("【修订建议】", text)

    def test_ambiguous_anchor_is_rejected_without_output(self) -> None:
        data = json.loads(FINDINGS.read_text(encoding="utf-8"))
        finding = data["findings"][1]
        finding["anchor_text"] = "甲方"
        finding.pop("anchor_occurrence", None)
        data["findings"] = [finding]
        ambiguous_findings = self.work / "ambiguous.json"
        ambiguous_findings.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        output = self.work / "must-not-exist.docx"

        result = run_cli(
            ADD_COMMENTS,
            self.input_docx,
            ambiguous_findings,
            "-o",
            output,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("ambiguous", result.stderr)
        self.assertFalse(output.exists())

    def test_verifier_detects_body_text_tampering(self) -> None:
        reviewed = self.work / "reviewed.docx"
        added = run_cli(ADD_COMMENTS, self.input_docx, FINDINGS, "-o", reviewed)
        self.assertEqual(added.returncode, 0, added.stderr)

        tampered = self.work / "tampered.docx"
        with zipfile.ZipFile(reviewed, "r") as source:
            infos = source.infolist()
            payloads = {info.filename: source.read(info.filename) for info in infos}
        original = "服务期限自2026年3月1日".encode("utf-8")
        replacement = "服务期限自2026年3月2日".encode("utf-8")
        self.assertIn(original, payloads["word/document.xml"])
        payloads["word/document.xml"] = payloads["word/document.xml"].replace(
            original, replacement, 1
        )
        with zipfile.ZipFile(tampered, "w") as target:
            for info in infos:
                target.writestr(info, payloads[info.filename])

        result = run_cli(VERIFY_COMMENTS, self.input_docx, tampered, FINDINGS)
        self.assertEqual(result.returncode, 2)
        self.assertIn("paragraph text changed", result.stderr)


if __name__ == "__main__":
    unittest.main()
