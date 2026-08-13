#!/usr/bin/env python3
"""Verify DOCX native comments and the contract-body zero-text-change invariant."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from add_comments import (
    COMMENTS_CONTENT_TYPE,
    COMMENTS_REL_TYPE,
    CT_NS,
    NS,
    REL_NS,
    RISK_AUTHOR,
    W_NS,
    CommentWriterError,
    canonical_body_text,
    comment_lines,
    comments_relationship_target,
    load_findings,
    paragraph_text,
    _plan_comments,
)


def _qn(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _parse(payload: bytes, label: str) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)
    try:
        return etree.fromstring(payload, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise CommentWriterError(f"invalid XML in {label}: {exc}") from exc


def _package(path: Path) -> dict[str, bytes]:
    if not path.is_file():
        raise CommentWriterError(f"DOCX not found: {path}")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise CommentWriterError(f"{path.name} contains a corrupt member: {bad_member}")
            return {name: archive.read(name) for name in archive.namelist()}
    except (OSError, zipfile.BadZipFile) as exc:
        raise CommentWriterError(f"cannot open {path}: {exc}") from exc


def _comment_ids(comments_root: etree._Element | None) -> set[str]:
    if comments_root is None:
        return set()
    ids = [comment.get(_qn("id"), "") for comment in comments_root.xpath("./w:comment", namespaces=NS)]
    if "" in ids:
        raise CommentWriterError("a comment is missing w:id")
    if len(ids) != len(set(ids)):
        raise CommentWriterError("word/comments.xml contains duplicate comment IDs")
    return set(ids)


def _comment_text(comment: etree._Element) -> list[str]:
    return [
        "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        for paragraph in comment.xpath("./w:p", namespaces=NS)
    ]


def _marker_ids(document_root: etree._Element, local_name: str) -> list[str]:
    return [
        node.get(_qn("id"), "")
        for node in document_root.xpath(f".//w:{local_name}", namespaces=NS)
    ]


def _anchored_text(
    document_root: etree._Element, comment_id: str
) -> tuple[str, int, int]:
    found: list[tuple[str, int, int]] = []
    paragraphs = document_root.xpath("/w:document/w:body/w:p", namespaces=NS)
    for paragraph_number, paragraph in enumerate(paragraphs, start=1):
        active = False
        pieces: list[str] = []
        cursor = 0
        range_start = 0
        for child in paragraph:
            if child.tag == _qn("commentRangeStart") and child.get(_qn("id")) == comment_id:
                if active:
                    raise CommentWriterError(f"comment {comment_id} has nested duplicate starts")
                active = True
                range_start = cursor
                continue
            if child.tag == _qn("commentRangeEnd") and child.get(_qn("id")) == comment_id:
                if not active:
                    continue
                found.append(("".join(pieces), paragraph_number, range_start))
                active = False
                pieces = []
                continue
            child_text = child.xpath(".//w:t/text()", namespaces=NS)
            if active:
                pieces.extend(child_text)
            cursor += sum(len(piece) for piece in child_text)
        if active:
            raise CommentWriterError(f"comment {comment_id} range crosses a paragraph boundary")
    if len(found) != 1:
        raise CommentWriterError(
            f"comment {comment_id} must have one complete range; found {len(found)}"
        )
    return found[0]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify(input_path: Path, output_path: Path, findings_path: Path) -> dict[str, Any]:
    language, findings = load_findings(findings_path)
    input_package = _package(input_path)
    output_package = _package(output_path)
    required_output_parts = {
        "word/document.xml",
        "word/comments.xml",
        "word/_rels/document.xml.rels",
        "[Content_Types].xml",
    }
    missing = sorted(required_output_parts.difference(output_package))
    if missing:
        raise CommentWriterError(f"output is missing required parts: {', '.join(missing)}")
    if "word/document.xml" not in input_package:
        raise CommentWriterError("input is missing word/document.xml")

    input_document = _parse(input_package["word/document.xml"], "input word/document.xml")
    output_document = _parse(output_package["word/document.xml"], "output word/document.xml")
    expected_plans = {
        plan.finding["finding_id"]: plan
        for plan in _plan_comments(input_document, findings, first_comment_id=0)
    }
    input_top_level_paragraphs = [
        paragraph_text(p)
        for p in input_document.xpath("/w:document/w:body/w:p", namespaces=NS)
    ]
    output_top_level_paragraphs = [
        paragraph_text(p)
        for p in output_document.xpath("/w:document/w:body/w:p", namespaces=NS)
    ]
    if input_top_level_paragraphs != output_top_level_paragraphs:
        mismatch = next(
            (
                index
                for index, (before, after) in enumerate(
                    zip(input_top_level_paragraphs, output_top_level_paragraphs), start=1
                )
                if before != after
            ),
            min(len(input_top_level_paragraphs), len(output_top_level_paragraphs)) + 1,
        )
        raise CommentWriterError(
            f"main-body paragraph text changed (first mismatch at paragraph {mismatch})"
        )
    input_text = canonical_body_text(input_document)
    output_text = canonical_body_text(output_document)
    input_hash = _sha256(input_text)
    output_hash = _sha256(output_text)
    if input_hash != output_hash:
        raise CommentWriterError("canonical main-body text hash changed")

    input_comments = (
        _parse(input_package["word/comments.xml"], "input word/comments.xml")
        if "word/comments.xml" in input_package
        else None
    )
    output_comments = _parse(output_package["word/comments.xml"], "output word/comments.xml")
    input_ids = _comment_ids(input_comments)
    output_ids = _comment_ids(output_comments)
    new_ids = output_ids.difference(input_ids)
    if len(new_ids) != len(findings):
        raise CommentWriterError(
            f"expected {len(findings)} new comments; found {len(new_ids)}"
        )

    relationships = _parse(
        output_package["word/_rels/document.xml.rels"],
        "output word/_rels/document.xml.rels",
    )
    comment_relationships = relationships.xpath(
        "./pr:Relationship[@Type=$kind]",
        namespaces={"pr": REL_NS},
        kind=COMMENTS_REL_TYPE,
    )
    if len(comment_relationships) != 1:
        raise CommentWriterError(
            f"expected one comments relationship; found {len(comment_relationships)}"
        )
    target = comment_relationships[0].get("Target", "")
    resolved_target = comments_relationship_target(
        target, comment_relationships[0].get("TargetMode")
    )
    if resolved_target not in output_package:
        raise CommentWriterError(
            f"comments relationship target is missing from the package: {resolved_target}"
        )

    content_types = _parse(output_package["[Content_Types].xml"], "output [Content_Types].xml")
    overrides = content_types.xpath(
        "./ct:Override[@PartName='/word/comments.xml']", namespaces={"ct": CT_NS}
    )
    if len(overrides) != 1 or overrides[0].get("ContentType") != COMMENTS_CONTENT_TYPE:
        raise CommentWriterError("comments.xml content-type override is missing or invalid")

    starts = _marker_ids(output_document, "commentRangeStart")
    ends = _marker_ids(output_document, "commentRangeEnd")
    references = _marker_ids(output_document, "commentReference")
    output_comment_nodes = output_comments.xpath("./w:comment", namespaces=NS)
    unused_new_ids = set(new_ids)
    verified_comments: list[dict[str, Any]] = []

    for finding in findings:
        expected_lines = comment_lines(language, finding)
        expected_author, expected_initials = RISK_AUTHOR[finding["risk"]]
        candidates = [
            comment
            for comment in output_comment_nodes
            if comment.get(_qn("id")) in unused_new_ids
            and comment.get(_qn("author")) == expected_author
            and comment.get(_qn("initials")) == expected_initials
            and _comment_text(comment) == expected_lines
        ]
        expected_plan = expected_plans[finding["finding_id"]]
        anchored_candidates: list[tuple[etree._Element, int, int]] = []
        for candidate in candidates:
            candidate_id = candidate.get(_qn("id"), "")
            anchor, paragraph_number, anchor_start = _anchored_text(
                output_document, candidate_id
            )
            if (
                anchor == finding["anchor_text"]
                and paragraph_number == expected_plan.paragraph_number
                and anchor_start == expected_plan.start
            ):
                anchored_candidates.append((candidate, paragraph_number, anchor_start))
        if len(anchored_candidates) != 1:
            raise CommentWriterError(
                f"{finding['finding_id']}: expected exactly one structured comment; "
                f"found {len(anchored_candidates)} at the expected anchor"
            )
        comment, paragraph_number, anchor_start = anchored_candidates[0]
        comment_id = comment.get(_qn("id"), "")
        unused_new_ids.remove(comment_id)
        for label, values in (
            ("start", starts),
            ("end", ends),
            ("reference", references),
        ):
            count = values.count(comment_id)
            if count != 1:
                raise CommentWriterError(
                    f"{finding['finding_id']}: comment {comment_id} has {count} {label} markers"
                )
        anchor, _, _ = _anchored_text(output_document, comment_id)
        if anchor != finding["anchor_text"]:
            raise CommentWriterError(
                f"{finding['finding_id']}: anchored text mismatch: {anchor!r}"
            )
        if output_top_level_paragraphs[paragraph_number - 1] != finding["paragraph_text"]:
            raise CommentWriterError(
                f"{finding['finding_id']}: comment is anchored in the wrong paragraph"
            )
        verified_comments.append(
            {
                "finding_id": finding["finding_id"],
                "comment_id": comment_id,
                "author": expected_author,
                "paragraph_number": paragraph_number,
                "anchor_start": anchor_start,
                "anchor_text": anchor,
            }
        )

    if unused_new_ids:
        raise CommentWriterError(f"unmatched new comments remain: {sorted(unused_new_ids)}")

    return {
        "status": "ok",
        "input": str(input_path),
        "output": str(output_path),
        "findings": str(findings_path),
        "checks": {
            "docx_zip_integrity": True,
            "main_body_paragraphs_identical": True,
            "main_body_text_hash_identical": True,
            "comments_xml_present": True,
            "comments_relationship_valid": True,
            "comments_content_type_valid": True,
            "comment_markers_complete": True,
            "exact_anchors_verified": True,
        },
        "body_text_sha256": input_hash,
        "paragraph_count": len(input_top_level_paragraphs),
        "new_comment_count": len(new_ids),
        "comments": verified_comments,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("findings", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.input, args.output, args.findings)
    except CommentWriterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
