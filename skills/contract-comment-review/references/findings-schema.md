# Findings JSON schema

Use UTF-8 JSON with this top-level shape:

```json
{
  "document": "service-contract.docx",
  "language": "zh-CN",
  "review_context": {
    "contract_type": "信息技术服务合同",
    "represented_party": "甲方",
    "review_depth": "standard",
    "assumptions": ["双方均为依法设立并有效存续的企业"]
  },
  "findings": [
    {
      "finding_id": "C-001",
      "paragraph_text": "合同中的完整段落原文",
      "paragraph_occurrence": 1,
      "anchor_text": "要批注的最短准确原文",
      "anchor_occurrence": 1,
      "risk": "High",
      "issue_type": "价款条款矛盾",
      "risk_reason": "具体说明对所代表一方的后果。",
      "revision_suggestion": "给出可执行的修改方向或替代文字。"
    }
  ]
}
```

## Required finding fields

- `finding_id`: unique stable identifier.
- `paragraph_text`: exact complete text of one main-document paragraph.
- `anchor_text`: exact non-empty substring of that paragraph.
- `risk`: exactly `High`, `Medium`, or `Low`.
- `issue_type`, `risk_reason`, `revision_suggestion`: non-empty strings.

`paragraph_occurrence` and `anchor_occurrence` are optional positive, one-based integers. Omit them only when the relevant text occurs once. If text is duplicated and no occurrence is provided, the writer refuses to guess.

The writer constructs the three required comment headings. Do not place the headings inside the individual JSON values.

## Locator rules

- Copy text from the actual `.docx`; do not retype punctuation from memory.
- Prefer the shortest anchor that identifies the problem.
- Do not create overlapping anchors in the same paragraph in v0.1.
- If the target is outside an ordinary main-body paragraph, record it as unsupported and handle it manually.
