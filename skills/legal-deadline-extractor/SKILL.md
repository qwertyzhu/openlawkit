---
name: legal-deadline-extractor
description: 从中国劳动仲裁与民事执行文书中抽取法律相关触发日期，保留原文与出处，仅在已核实规则精确匹配时计算期限。凡用户要求从通知书、裁决、裁定或已结构化的 facts JSON 中 extract / calculate / audit / calendar 法律期限时使用。
---

# 法律期限提取

把源文书变成可审计的期限登记。抽取与计算分开：Agent 抽取事实和证据；随附脚本按版本化规则包做日期运算。

## 不可妥协的边界

- 本地处理文件，除非用户明确要求其他去向。
- 不得编造送达日、生效日、当事人角色、程序类型、规则、节假日或期限。
- 文书上印着的日期，不等于送达日或签收日。
- 触发日期缺失或不确定、规则缺失、规则未核验、或事件与规则条件不匹配时，不输出确定到期日。
- 规则按工作日计算、或从非工作日顺延时，节假日表不完整或缺失则结果视为暂定。
- 每个抽取事件都要在 `original_excerpt` 保留原文，并给出可复现的 `source_locator`。
- 除非用户另行要求，不要写入案件管理系统、日历、邮件或外部服务。
- 结果是律师复核辅助，不是法律意见替代品。

## 工作流

### 1. 识别文书与范围

确定文书类型、作出机关、案号、当事人、相关参与人角色和程序类型。若源文件是纯图片 PDF，先 OCR，但保留页码并标出 OCR 不确定性。

公开 v0.1 规则包只覆盖 `references/rules.json` 中明确列出的事件。不要把邻近规则套到不同当事人、裁决类型、救济或程序阶段。

### 2. 抽取事实，不抽结论

按 `schemas/facts.schema.json` 编写 JSON。对每个可能的期限事件记录：

- `event_type` 与 `procedure_type`；
- 相关参与人角色及必要分类，例如裁决是否终局；
- 仅在源材料能证明法律要求的触发事件时填写 `trigger_date`；
- `trigger_date_status` 为 `confirmed`、`uncertain` 或 `missing`；
- 精确的 `original_excerpt` 与 `source_locator`；
- 全部规则条件匹配后才填写精确 `rule_id`；
- 抽取 `confidence` 以及关于歧义的短注。

重要事件缺少触发日期时，仍应纳入并设 `trigger_date: null`。这样缺失事实可见，而不是被静默丢掉。

### 3. 匹配已核实规则

阅读 `references/rules.json`。把事件与全部 `conditions` 匹配，包括当事人角色和文书分类。规则仅在同时满足时可用：

1. `verification.status` 为 `verified`；
2. 每条条件都被抽取事实满足；
3. 规则描述的触发事件，就是源摘录支持的事件。

任一项失败，把 `rule_id` 设为 `null`，或只把候选留在 `notes`；计算器会返回 `needs_confirmation` 且没有确定日期。

### 4. 确定性计算

在本 skill 目录下运行：

```powershell
python scripts/calculate_deadlines.py <facts.json> --rules references/rules.json --output-dir <output-directory>
```

工作日规则、或从非工作日顺延的规则，还需提供已复核的节假日文件：

```powershell
python scripts/calculate_deadlines.py <facts.json> --rules references/rules.json --holidays <holidays.json> --output-dir <output-directory>
```

脚本写出：

- `deadlines.json`：机器可读结果与警告；
- `deadlines.md`：人类可读审计表；
- `deadlines.ics`：仅为已算出日期的结果生成日历事件。

不得手工把 `needs_confirmation` 结果换成猜测日期。`provisional` 结果只能当作提醒，用于核验官方节假日表和源事实。

### 5. 交付前复核

对每条结果核验：

- 引用的触发原文存在于所述出处；
- 触发日期是规则要求的事件，而不仅是附近印着的日期；
- 当事人角色、裁决类型和程序类型满足该条规则；
- 除非规则另有规定，计算从触发事件的次日开始；
- 需要时，节假日表覆盖完整计算区间；
- JSON、Markdown 与 ICS 日期一致；
- 所有缺失事实和暂定结果都醒目。

## 结果含义

- `confirmed`：由已确认触发、已核实且匹配的规则，以及所需完整节假日表算出的确定日期。
- `provisional`：机械上算出了日期，但节假日覆盖或另一项已标明的非触发事实仍不完整。
- `needs_confirmation`：因触发或已核实匹配规则缺失/不确定，不输出确定日期。

## 随附资源

- `schemas/facts.schema.json`：抽取约定。
- `references/rules.json`：窄范围、带版本的规则包与官方法源。
- `references/holidays.schema.json`：可选节假日表约定。
- `scripts/calculate_deadlines.py`：确定性计算器与 JSON/Markdown/ICS 导出。
- `evals/evals.json`：仅使用虚构材料的回归提示。
