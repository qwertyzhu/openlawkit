from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "legal-deadline-extractor"
SCRIPT = SKILL / "scripts" / "calculate_deadlines.py"
RULES = SKILL / "references" / "rules.json"
HOLIDAYS = SKILL / "references" / "holidays-cn-2026.json"
EXAMPLES = ROOT / "examples" / "deadline-extractor"

SPEC = importlib.util.spec_from_file_location("openlawkit_deadline_calculator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
calculator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = calculator
SPEC.loader.exec_module(calculator)


class DeadlineExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = calculator.load_json(RULES)
        cls.holidays = calculator.HolidayCalendar.from_json(
            calculator.load_json(HOLIDAYS)
        )

    def test_confirmed_nonfinal_award_deadline(self) -> None:
        facts = calculator.load_json(EXAMPLES / "fictional-labor-facts.json")
        output = calculator.calculate_all(facts, self.rules, self.holidays)
        result = output["results"][0]

        self.assertEqual("confirmed", result["status"])
        self.assertEqual("2026-06-23", result["due_date"])
        self.assertEqual(
            "CN-LAB-ARBITRATION-NONFINAL-AWARD-LAWSUIT-15CD",
            result["rule_id"],
        )
        self.assertIn("签收", result["original_excerpt"])
        self.assertEqual("fictional-labor-award.txt", result["source_locator"]["file_name"])

    def test_missing_service_date_never_outputs_exact_date(self) -> None:
        facts = calculator.load_json(
            EXAMPLES / "fictional-missing-service-facts.json"
        )
        output = calculator.calculate_all(facts, self.rules, self.holidays)
        result = output["results"][0]

        self.assertEqual("needs_confirmation", result["status"])
        self.assertIsNone(result["due_date"])
        self.assertIn("missing_trigger_date", result["reason_codes"])
        self.assertNotIn("2026-06-18", calculator.to_markdown(output))
        self.assertNotIn("BEGIN:VEVENT", calculator.to_ics(output))

    def test_unknown_rule_never_outputs_exact_date(self) -> None:
        facts = calculator.load_json(EXAMPLES / "fictional-labor-facts.json")
        facts["events"][0]["rule_id"] = "DOES-NOT-EXIST"
        output = calculator.calculate_all(facts, self.rules, self.holidays)
        result = output["results"][0]

        self.assertEqual("needs_confirmation", result["status"])
        self.assertIsNone(result["due_date"])
        self.assertIn("rule_not_found", result["reason_codes"])

    def test_condition_mismatch_never_outputs_exact_date(self) -> None:
        facts = calculator.load_json(EXAMPLES / "fictional-labor-facts.json")
        facts["events"][0]["classifiers"]["award_type"] = "final"
        output = calculator.calculate_all(facts, self.rules, self.holidays)
        result = output["results"][0]

        self.assertEqual("needs_confirmation", result["status"])
        self.assertIsNone(result["due_date"])
        self.assertIn(
            "condition_mismatch:classifiers.award_type", result["reason_codes"]
        )

    def test_working_days_include_official_makeup_saturdays(self) -> None:
        facts = {
            "schema_version": "1.0",
            "matter_id": "FICTIONAL-WORKDAY",
            "events": [
                {
                    "event_id": "defense",
                    "event_type": "arbitration_application_copy_received",
                    "procedure_type": "labor_arbitration",
                    "participant_role": "respondent",
                    "classifiers": {},
                    "trigger_date": "2026-02-10",
                    "trigger_date_status": "confirmed",
                    "original_excerpt": "虚构送达回证：2026年2月10日签收申请书副本。",
                    "source_locator": {
                        "file_name": "fictional-notice.txt",
                        "location": "送达回证",
                    },
                    "rule_id": "CN-LAB-ARBITRATION-RESPONDENT-DEFENSE-10WD",
                    "confidence": "high",
                }
            ],
        }
        output = calculator.calculate_all(facts, self.rules, self.holidays)
        result = output["results"][0]

        self.assertEqual("confirmed", result["status"])
        self.assertEqual("2026-03-02", result["due_date"])

        rule = next(
            item
            for item in self.rules["rules"]
            if item["rule_id"] == "CN-LAB-ARBITRATION-RESPONDENT-DEFENSE-10WD"
        )
        procedural_source = next(
            item
            for item in rule["official_sources"]
            if item["title"] == "劳动人事争议仲裁办案规则"
        )
        self.assertEqual("第三十三条、第八十条", procedural_source["article"])

    def test_missing_holiday_calendar_makes_date_provisional(self) -> None:
        facts = calculator.load_json(EXAMPLES / "fictional-labor-facts.json")
        output = calculator.calculate_all(facts, self.rules, None)
        result = output["results"][0]

        self.assertEqual("provisional", result["status"])
        self.assertEqual("2026-06-23", result["due_date"])
        self.assertIn("holiday_calendar_incomplete", result["reason_codes"])

    def test_enforcement_date_is_provisional_due_to_substantive_review(self) -> None:
        facts = calculator.load_json(EXAMPLES / "fictional-enforcement-facts.json")
        output = calculator.calculate_all(facts, self.rules, self.holidays)
        result = output["results"][0]

        self.assertEqual("provisional", result["status"])
        self.assertEqual("2028-07-31", result["due_date"])
        self.assertIn("substantive_review_required", result["reason_codes"])
        self.assertIn("STATUS:TENTATIVE", calculator.to_ics(output))

    def test_enforcement_rule_uses_current_last_installment_trigger(self) -> None:
        rules_text = RULES.read_text(encoding="utf-8")
        rule = next(
            item
            for item in self.rules["rules"]
            if item["rule_id"] == "CN-CIVIL-ENFORCEMENT-APPLICATION-2Y"
        )

        self.assertNotIn("每次履行期间", rules_text)
        self.assertNotIn("each_installment_last_day", rules_text)
        self.assertIn(
            "installment_plan_last_day",
            rule["conditions"]["classifiers.trigger_basis"]["one_of"],
        )
        self.assertIn("最后一期履行期限届满", rule["review_reason"])
        self.assertEqual(
            "https://www.npc.gov.cn/npc/c2/c30834/202401/P020240108541839745616.pdf",
            rule["official_sources"][0]["url"],
        )

    def test_all_three_outputs_are_written_and_consistent(self) -> None:
        facts = calculator.load_json(EXAMPLES / "fictional-labor-facts.json")
        output = calculator.calculate_all(facts, self.rules, self.holidays)
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder)
            calculator.write_outputs(output, destination)
            json_output = json.loads(
                (destination / "deadlines.json").read_text(encoding="utf-8")
            )
            markdown_output = (destination / "deadlines.md").read_text(
                encoding="utf-8"
            )
            ics_output = (destination / "deadlines.ics").read_text(
                encoding="utf-8"
            )

        self.assertEqual("2026-06-23", json_output["results"][0]["due_date"])
        self.assertIn("2026-06-23", markdown_output)
        self.assertIn("DTSTART;VALUE=DATE:20260623", ics_output)
        self.assertIn("STATUS:CONFIRMED", ics_output)

    def test_ics_folding_uses_utf8_octets_and_unfolds_losslessly(self) -> None:
        source = "DESCRIPTION:" + "中文期限审计；" * 20
        folded = calculator.fold_ics_line(source)

        self.assertGreater(len(folded), 1)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in folded))
        self.assertTrue(all(line.startswith(" ") for line in folded[1:]))
        unfolded = folded[0] + "".join(line[1:] for line in folded[1:])
        self.assertEqual(source, unfolded)

    def test_ics_escape_normalises_cr_and_lf_without_property_injection(self) -> None:
        value = "original\rATTENDEE:mailto:attacker@example.test\r\nnext\nlast"
        escaped = calculator.ics_escape(value)

        self.assertNotIn("\r", escaped)
        self.assertNotIn("\n", escaped)
        self.assertEqual(
            "original\\nATTENDEE:mailto:attacker@example.test\\nnext\\nlast",
            escaped,
        )

    def test_holiday_complete_must_be_a_json_boolean(self) -> None:
        data = calculator.load_json(HOLIDAYS)
        data["complete"] = "false"

        with self.assertRaisesRegex(ValueError, "complete must be a boolean"):
            calculator.HolidayCalendar.from_json(data)


if __name__ == "__main__":
    unittest.main()
