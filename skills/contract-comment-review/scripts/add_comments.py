#!/usr/bin/env python3
"""Add exact, native Word comments to ordinary main-body DOCX paragraphs.

This module intentionally refuses complex or ambiguous anchors. It never edits
the visible contract text; it only splits simple text runs at comment boundaries
and adds the standard OOXML comment parts and markers.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_NS = "http://www.w3.org/XML/1998/namespace"
COMMENTS_REL_TYPE = f"{OFFICE_REL_NS}/comments"
COMMENTS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
)
NS = {"w": W_NS, "pr": REL_NS, "ct": CT_NS}
RISK_AUTHOR = {
    "High": ("OpenLawKit-High", "OWK-H"),
    "Medium": ("OpenLawKit-Medium", "OWK-M"),
    "Low": ("OpenLawKit-Low", "OWK-L"),
}


class CommentWriterError(ValueError):
    """Raised when adding a comment would be ambiguous or unsafe."""


@dataclass
class PlannedComment:
    finding: dict[str, Any]
    paragraph: etree._Element
    paragraph_number: int
    start: int
    end: int
    comment_id: int


def _qn(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _parse_xml(payload: bytes, label: str) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)
    try:
        return etree.fromstring(payload, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise CommentWriterError(f"invalid XML in {label}: {exc}") from exc


def paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def canonical_body_text(document_root: etree._Element) -> str:
    paragraphs = document_root.xpath("/w:document/w:body/w:p", namespaces=NS)
    return "\n".join(paragraph_text(p) for p in paragraphs)


def _positive_int(value: Any, field: str, finding_id: str) -> int:
    if isinstance(value, bool):
        raise CommentWriterError(f"{finding_id}: {field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CommentWriterError(
            f"{finding_id}: {field} must be a positive integer"
        ) from exc
    if parsed < 1:
        raise CommentWriterError(f"{finding_id}: {field} must be a positive integer")
    return parsed


def load_findings(path: Path) -> tuple[str, list[dict[str, Any]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommentWriterError(f"cannot read findings JSON: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        raise CommentWriterError("findings JSON must contain a top-level findings array")
    language = data.get("language", "zh-CN")
    if not isinstance(language, str) or not language.strip():
        raise CommentWriterError("language must be a non-empty string")

    required = (
        "finding_id",
        "paragraph_text",
        "anchor_text",
        "risk",
        "issue_type",
        "risk_reason",
        "revision_suggestion",
    )
    seen: set[str] = set()
    findings: list[dict[str, Any]] = []
    for raw in data["findings"]:
        if not isinstance(raw, dict):
            raise CommentWriterError("each finding must be an object")
        missing = [key for key in required if not isinstance(raw.get(key), str) or not raw[key].strip()]
        if missing:
            label = raw.get("finding_id", "<unknown>")
            raise CommentWriterError(f"{label}: missing non-empty fields: {', '.join(missing)}")
        finding = dict(raw)
        finding_id = finding["finding_id"].strip()
        if finding_id in seen:
            raise CommentWriterError(f"duplicate finding_id: {finding_id}")
        seen.add(finding_id)
        finding["finding_id"] = finding_id
        if finding["risk"] not in RISK_AUTHOR:
            raise CommentWriterError(
                f"{finding_id}: risk must be High, Medium, or Low"
            )
        for occurrence_field in ("paragraph_occurrence", "anchor_occurrence"):
            if occurrence_field in finding:
                finding[occurrence_field] = _positive_int(
                    finding[occurrence_field], occurrence_field, finding_id
                )
        findings.append(finding)
    if not findings:
        raise CommentWriterError("findings array is empty")
    return language, findings


def _all_occurrences(text: str, needle: str) -> list[int]:
    positions: list[int] = []
    cursor = 0
    while True:
        position = text.find(needle, cursor)
        if position < 0:
            return positions
        positions.append(position)
        cursor = position + 1


def _select_occurrence(
    matches: list[Any], explicit: Any, label: str, finding_id: str
) -> Any:
    if not matches:
        raise CommentWriterError(f"{finding_id}: {label} not found")
    if explicit is None:
        if len(matches) != 1:
            raise CommentWriterError(
                f"{finding_id}: {label} is ambiguous ({len(matches)} matches); "
                "set the corresponding one-based occurrence"
            )
        return matches[0]
    index = _positive_int(explicit, f"{label}_occurrence", finding_id)
    if index > len(matches):
        raise CommentWriterError(
            f"{finding_id}: {label} occurrence {index} exceeds {len(matches)} matches"
        )
    return matches[index - 1]


def _existing_comment_ids(comments_root: etree._Element | None) -> set[int]:
    if comments_root is None:
        return set()
    ids: set[int] = set()
    for comment in comments_root.xpath("./w:comment", namespaces=NS):
        raw = comment.get(_qn("id"))
        try:
            ids.add(int(raw))
        except (TypeError, ValueError) as exc:
            raise CommentWriterError(f"existing comment has invalid w:id: {raw!r}") from exc
    return ids


def _plan_comments(
    document_root: etree._Element,
    findings: list[dict[str, Any]],
    first_comment_id: int,
) -> list[PlannedComment]:
    paragraphs = document_root.xpath("/w:document/w:body/w:p", namespaces=NS)
    paragraph_strings = [paragraph_text(p) for p in paragraphs]
    plans: list[PlannedComment] = []

    for offset, finding in enumerate(findings):
        finding_id = finding["finding_id"]
        p_matches = [
            (index, paragraph)
            for index, (paragraph, text) in enumerate(zip(paragraphs, paragraph_strings), start=1)
            if text == finding["paragraph_text"]
        ]
        p_number, paragraph = _select_occurrence(
            p_matches,
            finding.get("paragraph_occurrence"),
            "paragraph_text",
            finding_id,
        )
        text = paragraph_strings[p_number - 1]
        positions = _all_occurrences(text, finding["anchor_text"])
        start = _select_occurrence(
            positions,
            finding.get("anchor_occurrence"),
            "anchor_text",
            finding_id,
        )
        end = start + len(finding["anchor_text"])
        plans.append(
            PlannedComment(
                finding=finding,
                paragraph=paragraph,
                paragraph_number=p_number,
                start=start,
                end=end,
                comment_id=first_comment_id + offset,
            )
        )

    for index, left in enumerate(plans):
        for right in plans[index + 1 :]:
            if left.paragraph is not right.paragraph:
                continue
            if max(left.start, right.start) < min(left.end, right.end):
                raise CommentWriterError(
                    f"overlapping anchors are unsupported: "
                    f"{left.finding['finding_id']} and {right.finding['finding_id']}"
                )
    return plans


def _run_text(run: etree._Element) -> str:
    return "".join(run.xpath(".//w:t/text()", namespaces=NS))


def _simple_text_runs(paragraph: etree._Element) -> list[tuple[etree._Element, int, int, str]]:
    result: list[tuple[etree._Element, int, int, str]] = []
    cursor = 0
    for child in paragraph:
        if child.tag != _qn("r"):
            continue
        text = _run_text(child)
        if not text:
            continue
        allowed = {_qn("rPr"), _qn("t")}
        if any(grandchild.tag not in allowed for grandchild in child):
            raise CommentWriterError(
                "anchor intersects a complex Word run (field, drawing, break, or other non-text content)"
            )
        result.append((child, cursor, cursor + len(text), text))
        cursor += len(text)
    if cursor != len(paragraph_text(paragraph)):
        raise CommentWriterError(
            "paragraph contains nested/complex text (for example hyperlink or tracked change); "
            "v0.1 refuses to guess the comment range"
        )
    return result


def _new_text_element(value: str) -> etree._Element:
    text = etree.Element(_qn("t"))
    if value[:1].isspace() or value[-1:].isspace():
        text.set(f"{{{XML_NS}}}space", "preserve")
    text.text = value
    return text


def _copy_run_with_text(run: etree._Element, value: str) -> etree._Element:
    clone = copy.deepcopy(run)
    run_properties = clone.find(_qn("rPr"))
    for child in list(clone):
        clone.remove(child)
    if run_properties is not None:
        clone.append(run_properties)
    clone.append(_new_text_element(value))
    return clone


def _split_run(run: etree._Element, offset: int) -> tuple[etree._Element | None, etree._Element | None]:
    text = _run_text(run)
    if offset <= 0:
        return None, run
    if offset >= len(text):
        return run, None
    parent = run.getparent()
    if parent is None:
        raise CommentWriterError("internal error: detached Word run")
    index = parent.index(run)
    left = _copy_run_with_text(run, text[:offset])
    right = _copy_run_with_text(run, text[offset:])
    parent.remove(run)
    parent.insert(index, left)
    parent.insert(index + 1, right)
    return left, right


def _insert_comment_range(plan: PlannedComment) -> None:
    paragraph = plan.paragraph
    spans = _simple_text_runs(paragraph)
    try:
        end_run, end_start, _, end_text = next(
            span for span in spans if span[1] < plan.end <= span[2]
        )
    except StopIteration as exc:
        raise CommentWriterError(
            f"{plan.finding['finding_id']}: cannot map anchor end to a simple run"
        ) from exc
    end_offset = plan.end - end_start
    if end_offset < len(end_text):
        _split_run(end_run, end_offset)

    spans = _simple_text_runs(paragraph)
    try:
        start_run, start_at, _, _ = next(
            span for span in spans if span[1] <= plan.start < span[2]
        )
    except StopIteration as exc:
        raise CommentWriterError(
            f"{plan.finding['finding_id']}: cannot map anchor start to a simple run"
        ) from exc
    start_offset = plan.start - start_at
    if start_offset:
        _split_run(start_run, start_offset)

    spans = _simple_text_runs(paragraph)
    covered = [
        (run, start, end, text)
        for run, start, end, text in spans
        if start >= plan.start and end <= plan.end and end > plan.start
    ]
    if not covered or "".join(item[3] for item in covered) != plan.finding["anchor_text"]:
        raise CommentWriterError(
            f"{plan.finding['finding_id']}: exact anchor could not be isolated safely"
        )

    first_run = covered[0][0]
    last_run = covered[-1][0]
    comment_id = str(plan.comment_id)

    range_end = etree.Element(_qn("commentRangeEnd"))
    range_end.set(_qn("id"), comment_id)
    end_index = paragraph.index(last_run) + 1
    paragraph.insert(end_index, range_end)

    reference_run = etree.Element(_qn("r"))
    reference_properties = etree.SubElement(reference_run, _qn("rPr"))
    style = etree.SubElement(reference_properties, _qn("rStyle"))
    style.set(_qn("val"), "CommentReference")
    reference = etree.SubElement(reference_run, _qn("commentReference"))
    reference.set(_qn("id"), comment_id)
    paragraph.insert(end_index + 1, reference_run)

    range_start = etree.Element(_qn("commentRangeStart"))
    range_start.set(_qn("id"), comment_id)
    paragraph.insert(paragraph.index(first_run), range_start)


def comment_lines(language: str, finding: dict[str, Any]) -> list[str]:
    if language.lower().startswith("zh"):
        return [
            f"【问题类型】{finding['issue_type'].strip()}",
            f"【风险原因】{finding['risk_reason'].strip()}",
            f"【修订建议】{finding['revision_suggestion'].strip()}",
        ]
    return [
        f"[Issue Type] {finding['issue_type'].strip()}",
        f"[Risk Reason] {finding['risk_reason'].strip()}",
        f"[Revision Suggestion] {finding['revision_suggestion'].strip()}",
    ]


def _append_comment(
    comments_root: etree._Element,
    plan: PlannedComment,
    language: str,
    timestamp: str,
) -> None:
    author, initials = RISK_AUTHOR[plan.finding["risk"]]
    comment = etree.SubElement(comments_root, _qn("comment"))
    comment.set(_qn("id"), str(plan.comment_id))
    comment.set(_qn("author"), author)
    comment.set(_qn("initials"), initials)
    comment.set(_qn("date"), timestamp)

    for line_number, line in enumerate(comment_lines(language, plan.finding)):
        paragraph = etree.SubElement(comment, _qn("p"))
        p_properties = etree.SubElement(paragraph, _qn("pPr"))
        p_style = etree.SubElement(p_properties, _qn("pStyle"))
        p_style.set(_qn("val"), "CommentText")
        if line_number == 0:
            annotation_run = etree.SubElement(paragraph, _qn("r"))
            annotation_properties = etree.SubElement(annotation_run, _qn("rPr"))
            annotation_style = etree.SubElement(annotation_properties, _qn("rStyle"))
            annotation_style.set(_qn("val"), "CommentReference")
            etree.SubElement(annotation_run, _qn("annotationRef"))
        run = etree.SubElement(paragraph, _qn("r"))
        run_text = etree.SubElement(run, _qn("t"))
        run_text.text = line


def _iso_timestamp(raw: str | None) -> str:
    if raw is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    candidate = raw.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommentWriterError("--timestamp must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_comments_relationship(rels_root: etree._Element) -> None:
    existing = rels_root.xpath(
        "./pr:Relationship[@Type=$kind]", namespaces=NS, kind=COMMENTS_REL_TYPE
    )
    if existing:
        target = existing[0].get("Target", "")
        if target.replace("\\", "/").split("/")[-1] != "comments.xml":
            raise CommentWriterError(
                f"existing comments relationship uses unsupported target: {target}"
            )
        return
    numeric_ids: list[int] = []
    all_ids = {node.get("Id", "") for node in rels_root}
    for relationship_id in all_ids:
        if relationship_id.startswith("rId") and relationship_id[3:].isdigit():
            numeric_ids.append(int(relationship_id[3:]))
    next_id = max(numeric_ids, default=0) + 1
    relationship_id = f"rId{next_id}"
    while relationship_id in all_ids:
        next_id += 1
        relationship_id = f"rId{next_id}"
    relationship = etree.SubElement(rels_root, f"{{{REL_NS}}}Relationship")
    relationship.set("Id", relationship_id)
    relationship.set("Type", COMMENTS_REL_TYPE)
    relationship.set("Target", "comments.xml")


def _ensure_comments_content_type(content_types_root: etree._Element) -> None:
    existing = content_types_root.xpath(
        "./ct:Override[@PartName='/word/comments.xml']", namespaces=NS
    )
    if existing:
        if existing[0].get("ContentType") != COMMENTS_CONTENT_TYPE:
            raise CommentWriterError("existing /word/comments.xml has an unexpected content type")
        return
    override = etree.SubElement(content_types_root, f"{{{CT_NS}}}Override")
    override.set("PartName", "/word/comments.xml")
    override.set("ContentType", COMMENTS_CONTENT_TYPE)


def _serialise(root: etree._Element) -> bytes:
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def _write_package(
    input_path: Path,
    output_path: Path,
    replacements: dict[str, bytes],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(input_path, "r") as source:
        infos = source.infolist()
        names = {info.filename for info in infos}
        payloads = {info.filename: source.read(info.filename) for info in infos}
    payloads.update(replacements)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w") as target:
            for info in infos:
                target.writestr(info, payloads[info.filename])
            for name in replacements:
                if name in names:
                    continue
                new_info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                new_info.compress_type = zipfile.ZIP_DEFLATED
                target.writestr(new_info, payloads[name])
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def add_comments(
    input_path: Path,
    findings_path: Path,
    output_path: Path,
    timestamp: str | None = None,
) -> dict[str, Any]:
    if input_path.suffix.lower() != ".docx" or output_path.suffix.lower() != ".docx":
        raise CommentWriterError("input and output must use the .docx extension")
    if input_path.resolve() == output_path.resolve():
        raise CommentWriterError("output must be a new file; the input is preserved")
    if not input_path.is_file():
        raise CommentWriterError(f"input DOCX not found: {input_path}")
    language, findings = load_findings(findings_path)
    timestamp_value = _iso_timestamp(timestamp)

    try:
        with zipfile.ZipFile(input_path, "r") as package:
            bad_member = package.testzip()
            if bad_member:
                raise CommentWriterError(f"input DOCX contains a corrupt member: {bad_member}")
            required_parts = (
                "word/document.xml",
                "word/_rels/document.xml.rels",
                "[Content_Types].xml",
            )
            missing = [part for part in required_parts if part not in package.namelist()]
            if missing:
                raise CommentWriterError(f"input is missing required DOCX parts: {', '.join(missing)}")
            document_root = _parse_xml(package.read("word/document.xml"), "word/document.xml")
            rels_root = _parse_xml(
                package.read("word/_rels/document.xml.rels"),
                "word/_rels/document.xml.rels",
            )
            content_types_root = _parse_xml(package.read("[Content_Types].xml"), "[Content_Types].xml")
            if "word/comments.xml" in package.namelist():
                comments_root = _parse_xml(package.read("word/comments.xml"), "word/comments.xml")
                if comments_root.tag != _qn("comments"):
                    raise CommentWriterError("word/comments.xml has an unexpected root element")
            else:
                comments_root = etree.Element(_qn("comments"), nsmap={"w": W_NS})
    except (OSError, zipfile.BadZipFile) as exc:
        raise CommentWriterError(f"cannot open input DOCX: {exc}") from exc

    before_text = canonical_body_text(document_root)
    existing_ids = _existing_comment_ids(comments_root)
    first_comment_id = max(existing_ids, default=-1) + 1
    plans = _plan_comments(document_root, findings, first_comment_id)

    for plan in sorted(
        plans, key=lambda item: (item.paragraph_number, item.start), reverse=True
    ):
        _insert_comment_range(plan)
    if canonical_body_text(document_root) != before_text:
        raise CommentWriterError("safety invariant failed: main-body text changed while adding comments")

    for plan in plans:
        _append_comment(comments_root, plan, language, timestamp_value)
    _ensure_comments_relationship(rels_root)
    _ensure_comments_content_type(content_types_root)

    replacements = {
        "word/document.xml": _serialise(document_root),
        "word/comments.xml": _serialise(comments_root),
        "word/_rels/document.xml.rels": _serialise(rels_root),
        "[Content_Types].xml": _serialise(content_types_root),
    }
    _write_package(input_path, output_path, replacements)
    return {
        "status": "ok",
        "input": str(input_path),
        "output": str(output_path),
        "comments_added": len(plans),
        "comment_ids": [plan.comment_id for plan in plans],
        "body_text_unchanged": True,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("findings", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--timestamp", help="optional deterministic ISO-8601 comment timestamp")
    args = parser.parse_args()
    try:
        result = add_comments(args.input, args.findings, args.output, args.timestamp)
    except CommentWriterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
