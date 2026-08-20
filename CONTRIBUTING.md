# Contributing

Contributions are welcome when they remain small, testable, and safe for public reuse.

## Development setup

OpenLawKit requires Python 3.10 or newer. From a fresh clone:

```console
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python scripts/run_demo.py --clean
```

The test suite must pass, and the demo must produce a reviewed DOCX, an integrity report, and JSON/Markdown/ICS deadline outputs under `demo-output/`.

## Contribution rules

1. Use only fictional or irreversibly de-identified fixtures.
2. Link every legal rule change to a current official primary source and record the verification date.
3. Add a regression case for every new rule or bug fix.
4. Keep deterministic code separate from model judgment.
5. Never weaken the two core invariants: no silent contract-text mutation, and no exact deadline without a verified trigger and rule.

Before opening a pull request, run the test suite and include only the smallest relevant fictional generated artifacts. Do not submit live client materials, active case numbers, credentials, personal contact details, local machine paths, Word lock files, or model transcripts containing private data.

## Versioning

Software versions follow semantic versioning in `pyproject.toml` and `.codex-plugin/plugin.json`. The deadline rule pack uses its own `rule_pack_version` and verification date; holiday calendars are year-scoped files. A software patch must not silently expand legal rules or weaken the two core invariants.

## Cutting a release

1. Move `CHANGELOG.md` Unreleased notes into `X.Y.Z` and set that same version in `pyproject.toml` and `.codex-plugin/plugin.json`.
2. Merge to `main`, push, and wait for CI.
3. Create an annotated tag and push it. GitHub Actions packs reproducible `.skill` archives, writes `SHA256SUMS.txt`, and publishes the GitHub Release:

```console
git tag -a vX.Y.Z -m "OpenLawKit vX.Y.Z"
git push origin vX.Y.Z
```

To pack archives locally before tagging:

```console
python scripts/pack_skills.py --output-dir dist --expect-version X.Y.Z
```
