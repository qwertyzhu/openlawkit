# 贡献指南

欢迎小范围、可测试、可公开复用的贡献。英文原文见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 开发环境

OpenLawKit 需要 Python 3.10 或更高版本。从全新克隆开始：

```console
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python scripts/run_demo.py --clean
```

测试必须通过；demo 必须在 `demo-output/` 下生成带批注的 DOCX、完整性校验报告，以及 JSON/Markdown/ICS 期限结果。

## 贡献规则

1. 样例只能使用虚构材料，或已不可逆脱敏的材料。
2. 每一条法律规则变更都必须链接现行官方法源，并记录核验日期。
3. 每条新规则或 bug 修复都要加回归测试。
4. 确定性代码与模型判断分开。
5. 不得削弱两条核心验收条件：不静默改动合同正文；没有已核实触发事实和规则时不输出确定期限。

提交 pull request 前请跑测试，只附带最小的、相关的虚构生成物。不要提交真实客户材料、在办案号、账号口令、个人联系方式、本机路径、Word 锁文件，或含有隐私的模型对话。

## 版本

软件版本遵循 `pyproject.toml` 和 `.codex-plugin/plugin.json` 中的语义化版本。期限规则包使用独立的 `rule_pack_version` 和核验日期；节假日表按年份分文件。软件补丁不得静默扩充法律规则，也不得削弱上述两条核心验收条件。

## 发布

1. 把 `CHANGELOG.md` 的 Unreleased 写入 `X.Y.Z`，并在 `pyproject.toml` 与 `.codex-plugin/plugin.json` 中设置同一版本。
2. 合并到 `main`，推送，等待 CI。
3. 打附注标签并推送。GitHub Actions 会打包可复现的 `.skill` 归档、写 `SHA256SUMS.txt`，并发布 GitHub Release：

```console
git tag -a vX.Y.Z -m "OpenLawKit vX.Y.Z"
git push origin vX.Y.Z
```

打标签前如需本地打包：

```console
python scripts/pack_skills.py --output-dir dist --expect-version X.Y.Z
```
