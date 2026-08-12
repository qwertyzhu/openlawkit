---
name: contract-comment-review
description: Review a Chinese or English .docx contract from a stated party's position, add structured native Microsoft Word comments without changing the contract body text, and verify the resulting OOXML. Use when the user asks for Word contract comments, contract red flags, comment-only review, or a reviewed DOCX.
---

# Contract Comment Review

Produce a lawyer-reviewable `.docx` whose contract body text is identical to the input and whose issues appear as native Microsoft Word comments.

## Non-negotiable rules

1. Work locally. Do not upload the contract or copy its facts into a public issue.
2. Do not change, delete, reorder, or silently normalize any contract body text. Add comments only.
3. Never invent a party fact, commercial term, law, case, date, or missing annex. Mark missing material as a verification item.
4. Use the contract's dominant language throughout the comments.
5. Every comment must contain these three fields in this order:
   - Chinese: `【问题类型】` / `【风险原因】` / `【修订建议】`
   - English: `[Issue Type]` / `[Risk Reason]` / `[Revision Suggestion]`
6. Encode severity in the comment author, not with emoji or color claims:
   - `High` -> `OpenLawKit-High`
   - `Medium` -> `OpenLawKit-Medium`
   - `Low` -> `OpenLawKit-Low`
7. Anchor each comment to the shortest exact text span that still makes the issue understandable.
8. A structurally valid file is not proof that the legal analysis is correct. Require human review before use.

## Inputs to establish first

Determine and record:

- contract type;
- represented party and review position;
- transaction purpose and known commercial context;
- intended reader;
- review depth: quick, standard, or deep;
- contract language.

If the represented party or another fact would materially change the review, ask for it. If the user explicitly requests progress without answering, state a narrow assumption in the accompanying findings file; do not present the assumption as fact.

## Review workflow

### 1. Inspect safely

Confirm that the input is a `.docx`. Preserve the original file. Read the main document, tables, headers, footers, footnotes, and existing comments when they matter. The bundled writer currently anchors comments only in main-document paragraphs; if a target clause is in a table, header, footer, text box, field, or tracked-change container, report that limitation and do not pretend it was commented.

### 2. Review in four layers

Use [references/methodology.md](references/methodology.md):

1. entity and authority;
2. text and document integrity;
3. business allocation and operability;
4. legal enforceability and remedies.

Separate fact, judgment, and recommendation. Preserve the exact quoted clause. Verify current law before relying on a citation; otherwise write `需核验法条原文` / `verify current legal text`.

### 3. Create findings JSON

Follow [references/findings-schema.md](references/findings-schema.md). Each finding must identify one exact main-body paragraph and one exact anchor. Avoid overlapping anchors.

### 4. Add native comments

Run from this skill directory:

```powershell
python scripts/add_comments.py input.docx findings.json -o reviewed.docx
```

The script refuses ambiguous paragraph or anchor matches and unsupported complex anchors. Resolve the locator; do not expand the anchor to an unrelated paragraph merely to make the command pass.

### 5. Verify before delivery

```powershell
python scripts/verify_comments.py input.docx reviewed.docx findings.json --report verification.json
```

Delivery requires all of the following:

- input and output main-body paragraph texts are identical;
- the canonical main-body text hashes match;
- every expected comment has the correct structured text and risk author;
- every comment has one start marker, one end marker, and one reference;
- every anchored text span equals the requested anchor;
- `word/comments.xml`, its document relationship, and its content-type override exist;
- the output opens and has been visually rendered for layout inspection.

If any check fails, do not deliver the document as complete.

## Output package

Return:

- the reviewed `.docx`;
- the findings `.json` (or an equivalent human-readable issue list);
- the verification report;
- a short statement of represented party, assumptions, unsupported locations, and items requiring legal/factual confirmation.

The user, not the tool, decides whether to accept a proposed revision.

## Public-data boundary

Use only fictional or fully de-identified material in examples, tests, screenshots, repository history, and bug reports. Removing a file name is not sufficient de-identification: inspect document properties, comments, relationships, headers, footers, and embedded objects as well.

## Provenance

This public workflow is independently implemented and informed by the methodology identified in [references/third-party-notices.md](references/third-party-notices.md).
