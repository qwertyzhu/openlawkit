# Fictional contract-review example

All names, facts, numbers, and clauses in this folder are fictional and exist only for repeatable software testing.

- `fictional-service-contract.docx`: generated test input.
- `fictional-findings.json`: example findings from the fictional purchaser's position.
- `fictional-service-contract-reviewed.docx`: generated example with native Word comments.
- `verification.json`: machine-readable invariant checks.
- `build_fixture.py`: recreates the input document.

Rebuild and verify from the repository root:

```powershell
python examples/contract-review/build_fixture.py examples/contract-review/fictional-service-contract.docx
python skills/contract-comment-review/scripts/add_comments.py examples/contract-review/fictional-service-contract.docx examples/contract-review/fictional-findings.json -o examples/contract-review/fictional-service-contract-reviewed.docx --timestamp 2026-01-01T00:00:00Z
python skills/contract-comment-review/scripts/verify_comments.py examples/contract-review/fictional-service-contract.docx examples/contract-review/fictional-service-contract-reviewed.docx examples/contract-review/fictional-findings.json --report examples/contract-review/verification.json
```
