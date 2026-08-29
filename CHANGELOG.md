# 更新日志

此处记录值得注意的变更。项目遵循语义化版本。

软件版本写在 `pyproject.toml` 与 `.codex-plugin/plugin.json`。期限规则另有
`rule_pack_version` 与核验日期；节假日表按年份分文件。软件补丁不得静默扩充法律规则。

## Unreleased

- 社区文件（贡献指南 / 安全说明 / 行为准则 / Issue 与 PR 模板）改为中文优先；两个 Skill 入口改为简体中文。

## 0.2.1 - 2026-08-29

补丁发布：中文优先的公开落地页、已核验的 2025 节假日表，
以及页眉页脚批注拒绝时的具名报错。不扩充 v0.1 法律规则包，
也不新增页眉页脚 / 合并表格批注锚点。

- 默认 README 改为简体中文；英文放在 `README.en.md`。
- 保留中英 About / plugin 文案，以及诚实的未完成事项列表。
- 新增 `holidays-cn-2025.json`，来源国办发明电〔2024〕12号，不改 `rules.json`。
- 页眉页脚批注锚点在写入报错中具名，不再使用笼统的缺段落提示。
- 为版本、README 路径和 `run_demo.py` 增加落地页回归测试。

## 0.2.0 - 2026-08-27

Minor release: simple Word table-cell comment anchors and documented fresh-clone
verification. It does not expand the v0.1 legal rule pack.

- Allow exact native comment anchors in simple (non-merged, non-nested) body-table cells.
- Still refuse merged cells, nested tables, ambiguous table content, headers/footers, text boxes, fields, and overlapping anchors.
- Keep full-body text integrity verification, including table text.
- Record the documented fresh-clone demo on Ubuntu 24.04 (WSL2); macOS and Windows continue to run the same demo in CI.

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
