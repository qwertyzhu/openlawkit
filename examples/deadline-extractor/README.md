# 法律期限提取虚构样例

这里的主体、案号、文书和日期全部为虚构，仅用于演示和回归测试。

- `fictional-labor-award.txt`：一份虚构的非终局劳动仲裁裁决书片段。
- `fictional-labor-facts.json`：对该片段人工复核后的结构化事实。
- `fictional-missing-service-date.txt`：文书写明作出日期，但没有实际送达日期。
- `fictional-missing-service-facts.json`：保留“待确认”，不得据文书作出日期计算起诉期限。
- `fictional-enforcement-facts.json`：虚构执行申请事实，结果必须因中止/中断风险标为暂定。

从仓库根目录运行：

```powershell
python skills/legal-deadline-extractor/scripts/calculate_deadlines.py examples/deadline-extractor/fictional-labor-facts.json --rules skills/legal-deadline-extractor/references/rules.json --holidays skills/legal-deadline-extractor/references/holidays-cn-2026.json --output-dir examples/deadline-extractor/output
```

