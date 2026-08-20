# Changelog

All notable changes are documented here. The project follows semantic versioning.

Software versions live in `pyproject.toml` and `.codex-plugin/plugin.json`. Deadline
rules keep a separate `rule_pack_version` and verification date; holiday calendars
are year-scoped files. A software patch must not silently expand legal rules.

## Unreleased

## 0.1.1 - 2026-08-20

Patch release: ships the post-0.1.0 onboarding and verification hardening that was
already on main. It does not expand the v0.1 legal rule pack or add Word table-cell
comment anchors.

- Added Codex plugin metadata and per-skill OpenAI interface metadata.
- Added a one-command cross-platform demo, verified screenshots, direct release links, and fresh-install instructions.
- Added Windows CI and aligned issue/security guidance with the repository settings.
- Hardened Word relationship resolution, full-body text verification, duplicate-comment matching, holiday metadata typing, and ICS newline escaping.
- Fixed demo `--clean` on Python 3.10/3.11, including Windows `Path.is_mount` `NotImplementedError`.
- Expanded CI to Python 3.10–3.12 on Ubuntu, Windows, and macOS.
- Added a reproducible `.skill` packer, `SHA256SUMS.txt`, and tag-triggered GitHub Releases.

## 0.1.0 - 2026-08-12

- Added `contract-comment-review` with native Word comments, exact anchors, structured risk comments, and body-text integrity verification.
- Added `legal-deadline-extractor` with evidence-linked facts, a versioned PRC rule pack, 2026 official holiday adjustments, and JSON/Markdown/ICS output.
- Added fictional fixtures, regression tests, privacy scans, CI, security and contribution guidance.
- Added a bilingual project overview, architecture note, official-source rule scope, and social preview artwork.
