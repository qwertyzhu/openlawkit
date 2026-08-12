# Safe Legal-Rule Contribution Example #3

## Primary Source
- Source: National People's Congress
- Article: 188
- Effective date: October 1, 2017
- Verification date: August 12, 2026
- Note: Article 188 was first enacted in the 2017 *General Provisions of the Civil Law*. That law was repealed and folded into the *Civil Code* (effective January 1, 2021), which carries the same article number and identical operative text. For any claim arising on or after January 1, 2021, cite the Civil Code, Book One (General Part), Article 188 — not the repealed 2017 instrument — even though the substantive rule is unchanged.

## Triggering Facts
- Jurisdiction: PRC
- Claim type: Civil-law right
- Date of harm: YYYY-MM-DD
- Date claimant knew of harm: YYYY-MM-DD
- Obligor identified: Yes/No

## Inclusion Conditions
- Claim type is a general civil-rights claim with no special statutory limitation period (Article 188 applies only "unless otherwise provided by law")
- Both "date claimant knew of harm" and "obligor identified = Yes" are resolvable — the 3-year clock starts only once the claimant knows (or should have known) both the infringement and the obligor's identity
- Elapsed time from "date of harm" to the evaluation date is ≤ 20 years (the absolute long-stop bar, independent of discovery)

## Exclusions
- Claim type falls under a special statutory limitation period that overrides the general 3-year rule (e.g., 1-year for labor disputes, 4-year for international sale-of-goods contracts) — Article 188 explicitly yields to these
- Obligor identified = No — the limitation start date cannot be fixed, so the 3-year clock cannot be computed
- More than 20 years have elapsed since the date of harm — Article 188's long-stop applies (courts may extend this only on application and "under special circumstances," which this rule cannot evaluate automatically)
- Date of harm or date claimant knew of harm is missing/unresolvable

## Fictional Regression Case
**Case A — within limitation**
- Claimant: "Huitong Textiles Co." (fictional)
- Obligor: "Anlong Trading Co." (fictional)
- Claim type: Civil-law right (property damage)
- Date of harm: 2022-03-15
- Date claimant knew of harm: 2022-03-20
- Obligor identified: Yes (same date)
- Evaluation date: 2024-11-01
- Expected result: `within_limitation` — 3-year period runs 2022-03-20 → 2025-03-20; evaluation date falls inside it, and only ~2.6 years have passed since the date of harm (well under the 20-year cap)

**Case B — needs_confirmation**
- Same facts as Case A, except Obligor identified: No
- Expected result: `needs_confirmation` — the limitation start date cannot be fixed without knowing when the obligor's identity became known, so no time-barred/within-limitation determination can be made

## Needs Confirmation
If the required facts cannot be established reliably, the result must remain
`needs_confirmation`.

## Scope
This example is documentation-only and does not modify the shipped rule pack.