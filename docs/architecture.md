# Architecture and trust boundaries

OpenLawKit separates language-model judgment from deterministic document operations.

## Contract review

The agent reads the contract, the represented party, and the requested depth. It produces a structured finding ledger. A local script then anchors each approved finding to existing text and writes native Word comments. A verifier compares the canonical text of every paragraph under the Word document body—including paragraphs inside tables—and checks that the required OOXML comment parts and relationships exist.

The verifier cannot prove that legal judgment is correct. It proves a narrower and important invariant: the review process did not silently rewrite the source contract, and every delivered comment has the required structure.

## Deadline extraction

The agent extracts event facts with the original excerpt and source locator. A deterministic calculator accepts only rule IDs from a versioned rule pack. It refuses to claim an exact date when the trigger event, procedural type, holiday calendar, or applicable rule is missing.

Rules are data, not hidden prompt prose. Each rule records its official source, article, verification date, calculation unit, and review conditions. This makes legal updates reviewable as ordinary code changes with regression cases.

## Data flow

OpenLawKit has no required hosted backend. Documents, intermediate JSON, and generated work products remain in the user's chosen local workspace. The user's agent or model provider may have separate data practices; those are outside this repository and must be assessed independently.

## Non-goals

- deciding legal strategy without a qualified human;
- guessing service dates or procedural classifications;
- embedding live client files in tests or bug reports;
- treating a passing structural test as proof that legal advice is correct;
- supporting every jurisdiction or document type in v0.1.
