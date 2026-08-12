---
name: legal-deadline-extractor
description: Extract legally relevant trigger dates from Chinese labor-arbitration and civil-enforcement documents, preserve verbatim evidence and source locations, and calculate only deadlines supported by an exact verified rule. Use when a user asks to extract, calculate, audit, or calendar legal deadlines from a notice, award, ruling, or an already structured facts JSON file.
---

# Legal Deadline Extractor

Turn source documents into an auditable deadline register. Keep extraction and calculation separate: the agent extracts facts and evidence; the bundled script performs date arithmetic from a versioned rule pack.

## Non-negotiable safeguards

- Process files locally unless the user explicitly requests another destination.
- Never invent a delivery date, effective date, party role, procedure type, rule, holiday, or deadline.
- A date printed on a document is not automatically the date of service or receipt.
- Output no exact due date when the trigger date is missing or uncertain, the rule is missing, the rule is unverified, or the event does not match the rule conditions.
- Treat an incomplete or absent holiday calendar as provisional whenever a rule counts working days or rolls a deadline forward from a non-working day.
- Preserve the exact source wording in `original_excerpt` and a reproducible `source_locator` for every extracted event.
- Do not write to a case-management system, calendar, email, or external service unless the user separately asks for that action.
- Describe results as an aid for lawyer review, not as a substitute for legal advice.

## Workflow

### 1. Identify the document and scope

Determine the document type, issuing body, case number, parties, relevant participant role, and procedure type. If the source is an image-only PDF, obtain OCR text but retain the page reference and flag OCR uncertainty.

The public v0.1 rule pack covers only events explicitly present in `references/rules.json`. Do not stretch a nearby rule to a different party, award type, remedy, or procedural stage.

### 2. Extract facts, not conclusions

Create JSON conforming to `schemas/facts.schema.json`. For each possible deadline event, record:

- `event_type` and `procedure_type`;
- the relevant participant role and any required classifier, such as whether an award is final;
- `trigger_date` only when the source establishes the legally required trigger event;
- `trigger_date_status` as `confirmed`, `uncertain`, or `missing`;
- an exact `original_excerpt` and `source_locator`;
- an exact `rule_id` only after all rule conditions match;
- extraction `confidence` and a short note about ambiguity.

When a potentially important event lacks a trigger date, still include it with `trigger_date: null`. This makes the missing fact visible instead of silently dropping the deadline.

### 3. Match a verified rule

Read `references/rules.json`. Match the event against all listed `conditions`, including party role and document classification. A rule is usable only when:

1. its `verification.status` is `verified`;
2. every condition is satisfied by the extracted fact;
3. the trigger event described by the rule is the event supported by the source excerpt.

If any requirement fails, set `rule_id` to `null` or keep the candidate only in `notes`; the calculator will return `needs_confirmation` without an exact date.

### 4. Calculate deterministically

Run from the skill directory:

```powershell
python scripts/calculate_deadlines.py <facts.json> --rules references/rules.json --output-dir <output-directory>
```

For working-day rules or rules that roll forward from a non-working day, also provide a reviewed holiday file:

```powershell
python scripts/calculate_deadlines.py <facts.json> --rules references/rules.json --holidays <holidays.json> --output-dir <output-directory>
```

The script writes:

- `deadlines.json`: machine-readable results and warnings;
- `deadlines.md`: a human-readable audit table;
- `deadlines.ics`: calendar events only for results that have a computed date.

Never manually replace a `needs_confirmation` result with a guessed date. A `provisional` result may be used only as a reminder to verify the official holiday calendar and source facts.

### 5. Review before delivery

For every result, verify:

- the quoted trigger text exists in the stated source location;
- the trigger date is the rule's required event, not merely a nearby printed date;
- party role, award type, and procedure type satisfy the exact rule;
- the calculation starts on the day after the trigger event unless the rule states otherwise;
- a holiday calendar covers the full calculation range when required;
- JSON, Markdown, and ICS dates agree;
- all missing facts and provisional results are prominent.

## Result meanings

- `confirmed`: exact date calculated from a confirmed trigger, a verified matching rule, and any required complete holiday calendar.
- `provisional`: a date was mechanically calculated, but holiday coverage or another expressly identified non-trigger fact remains incomplete.
- `needs_confirmation`: no exact date is output because a trigger or verified matching rule is missing or uncertain.

## Included resources

- `schemas/facts.schema.json`: extraction contract.
- `references/rules.json`: narrow, versioned rule pack with official sources.
- `references/holidays.schema.json`: optional holiday-calendar contract.
- `scripts/calculate_deadlines.py`: deterministic calculator and JSON/Markdown/ICS exporter.
- `evals/evals.json`: regression prompts using only fictional material.

