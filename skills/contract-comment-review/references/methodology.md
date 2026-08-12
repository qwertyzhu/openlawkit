# Contract review methodology

## Start from the review position

The same clause can be favourable to one party and unacceptable to the other. Record the represented party before assigning severity. Do not flatten a negotiated commercial compromise into a generic statement that a clause is “unfair”. Explain who bears which risk and under what event.

## Four layers

### 1. Entity and authority

Check names, registration identifiers if supplied, signatory authority, affiliates, guarantors, notice details, and whether an annex or licence is said to exist. A missing fact is a verification item, not an invitation to invent it.

### 2. Text and document integrity

Check numbering, definitions, cross-references, amount and date conflicts, blank fields, annex references, priority clauses, signature blocks, and internal inconsistencies. Prefer objective comparisons: quote both conflicting values or provisions.

### 3. Business allocation and operability

Trace the transaction from performance to acceptance, invoice, payment, change, suspension, termination, handover, and post-termination duties. Ask whether each trigger is observable, each deadline is calculable, and each responsible party is identifiable.

### 4. Legal enforceability and remedies

Review liability exclusions, liquidated damages, intellectual property, confidentiality, personal information and data, force majeure, termination, dispute resolution, governing law, evidence, and mandatory rules relevant to the transaction. Verify current primary legal sources before giving a definitive citation.

## Comment quality

Each comment should be independently useful:

- `【问题类型】` gives a short classification;
- `【风险原因】` links the quoted language to a concrete consequence for the represented party;
- `【修订建议】` gives an executable edit direction or replacement wording.

Use `High` when the issue can defeat the transaction purpose, create material uncapped exposure, invalidate a core mechanism, or block an important remedy. Use `Medium` for meaningful but negotiable ambiguity or operational exposure. Use `Low` for clarity, consistency, and drafting hygiene that is unlikely by itself to alter the deal.

Severity is contextual. Do not infer monetary materiality without the user's threshold.

## Evidence discipline

Keep these separate:

1. **Fact:** exact contract language or supplied external fact.
2. **Judgment:** why it creates a risk from the chosen position.
3. **Recommendation:** the proposed mitigation.

When a legal proposition has not been checked against a current primary source, say so. Never fabricate an article number or court practice.

## Technical boundary in v0.1

The bundled comment writer supports exact anchors in ordinary main-document paragraphs made of simple Word text runs. It deliberately refuses tables, headers, footers, text boxes, fields, hyperlinks, drawings, tracked-change containers, and overlapping comment ranges. A refusal is safer than a comment attached to the wrong clause.
