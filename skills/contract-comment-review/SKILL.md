---
name: contract-comment-review
description: 从既定审查立场审查中文或英文 .docx 合同，只添加结构化的 Microsoft Word 原生批注、不改合同正文，并校验 OOXML。凡用户要求 Word 合同批注、合同红旗、只加批注审查、comment-only review 或 reviewed DOCX 时使用。
---

# 合同批注审查

产出一份律师可复核的 `.docx`：合同正文与输入完全一致，问题以 Microsoft Word 原生批注呈现。

## 不可妥协的规则

1. 本地处理。不要把合同或其中事实上传到公开 Issue。
2. 不得改动、删除、重排或静默规范化任何合同正文。只加批注。
3. 不得编造当事人事实、商业条款、法条、案例、日期或缺失附件。把缺失材料标成核验项。
4. 批注全文使用合同的主导语言。
5. 每条批注必须按此顺序包含三个字段：
   - 中文：`【问题类型】` / `【风险原因】` / `【修订建议】`
   - 英文：`[Issue Type]` / `[Risk Reason]` / `[Revision Suggestion]`
6. 风险等级写在批注作者里，不用 emoji 或颜色声称：
   - `High` -> `OpenLawKit-High`
   - `Medium` -> `OpenLawKit-Medium`
   - `Low` -> `OpenLawKit-Low`
7. 把每条批注锚定到仍能说明问题的最短精确文本。
8. 结构校验通过不等于法律分析正确。使用前必须人工复核。

## 先确定的输入

先确定并记录：

- 合同类型；
- 代理的当事人与审查立场；
- 交易目的与已知商业背景；
- 预期读者；
- 审查深度：快速、标准或深入；
- 合同语言。

若代理的当事人或其他事实会实质改变审查结论，先问。若用户明确要求先推进，把狭窄假设写进伴随的 findings 文件；不要把假设写成事实。

## 审查工作流

### 1. 安全查看

确认输入是 `.docx`。保留原件。阅读主文档、表格、页眉、页脚、脚注，以及必要时已有批注。随附写入器只把批注锚定在普通正文段落和简单表体单元格。若目标条款位于合并/嵌套表格、页眉、页脚、文本框、域或修订容器，报告该限制，不要假装已经批注。

### 2. 四层审查

使用 [references/methodology.md](references/methodology.md)：

1. 主体与权限；
2. 文本与文书完整性；
3. 商业分配与可执行性；
4. 法律效力与救济。

把事实、判断和建议分开。保留被引用条款原文。引用法条前核验现行文本；否则写 `需核验法条原文` / `verify current legal text`。

### 3. 编写 findings JSON

遵循 [references/findings-schema.md](references/findings-schema.md)。每条 finding 必须指向一个精确的正文段落或简单表格单元格段落，以及一个精确锚点。避免锚点重叠。

### 4. 添加原生批注

在本 skill 目录下运行：

```powershell
python scripts/add_comments.py input.docx findings.json -o reviewed.docx
```

脚本拒绝歧义段落/锚点匹配，以及不支持的复杂锚点。先修好定位；不要为了让命令通过，把锚点扩到无关段落。

### 5. 交付前校验

```powershell
python scripts/verify_comments.py input.docx reviewed.docx findings.json --report verification.json
```

交付必须同时满足：

- 输入与输出的正文段落文本相同；
- 正文规范文本哈希一致；
- 每条预期批注的结构化文本和风险作者正确；
- 每条批注有一个起始标记、一个结束标记和一个引用；
- 每个锚定文本等于请求的锚点；
- 存在 `word/comments.xml`、其文档关系和 content-type override；
- 输出能打开，并已做版式目视检查。

任一项失败，都不得把文档当作已完成交付。

## 交付包

返回：

- 已批注的 `.docx`；
- findings `.json`（或等价的可读问题清单）；
- 校验报告；
- 简短说明：代理的当事人、假设、未能批注的位置，以及需要法律/事实确认的事项。

是否接受修订建议，由用户而不是工具决定。

## 公开数据边界

样例、测试、截图、仓库历史和缺陷报告只用虚构或已充分脱敏材料。去掉文件名不等于脱敏：还要检查文档属性、批注、关系、页眉、页脚和嵌入对象。

## 来源

本公开工作流为独立实现，方法来源见 [references/third-party-notices.md](references/third-party-notices.md)。
