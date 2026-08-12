#!/usr/bin/env python3
"""Deterministic legal-deadline calculator for OpenLawKit.

This module deliberately does not extract legal facts from prose. It accepts
reviewed facts JSON, applies only an exact verified rule, and emits auditable
JSON, Markdown, and iCalendar files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD): {value!r}") from exc


@dataclass(frozen=True)
class HolidayCalendar:
    calendar_id: str
    coverage_start: date
    coverage_end: date
    complete: bool
    non_working_dates: frozenset[date]
    working_weekend_dates: frozenset[date]
    source_url: str | None
    verified_at: str | None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "HolidayCalendar":
        required = {
            "calendar_id",
            "coverage_start",
            "coverage_end",
            "complete",
            "non_working_dates",
            "working_weekend_dates",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"Holiday calendar is missing: {', '.join(missing)}")
        start = parse_date(data["coverage_start"], "coverage_start")
        end = parse_date(data["coverage_end"], "coverage_end")
        if start > end:
            raise ValueError("Holiday calendar coverage_start is after coverage_end")
        return cls(
            calendar_id=str(data["calendar_id"]),
            coverage_start=start,
            coverage_end=end,
            complete=bool(data["complete"]),
            non_working_dates=frozenset(
                parse_date(item, "non_working_dates[]")
                for item in data["non_working_dates"]
            ),
            working_weekend_dates=frozenset(
                parse_date(item, "working_weekend_dates[]")
                for item in data["working_weekend_dates"]
            ),
            source_url=data.get("source_url"),
            verified_at=data.get("verified_at"),
        )

    def is_non_working(self, day: date) -> bool:
        if day in self.working_weekend_dates:
            return False
        if day in self.non_working_dates:
            return True
        return day.weekday() >= 5

    def covers(self, start: date, end: date) -> bool:
        lower, upper = sorted((start, end))
        return self.complete and self.coverage_start <= lower and upper <= self.coverage_end


def default_weekend_calendar(start: date, end: date) -> HolidayCalendar:
    return HolidayCalendar(
        calendar_id="weekends-only-unverified",
        coverage_start=min(start, end),
        coverage_end=max(start, end),
        complete=False,
        non_working_dates=frozenset(),
        working_weekend_dates=frozenset(),
        source_url=None,
        verified_at=None,
    )


def add_years(start: date, years: int) -> date:
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        # 29 February has no direct anniversary in a non-leap year.
        return start.replace(year=start.year + years, month=2, day=28)


def add_working_days(start: date, amount: int, calendar: HolidayCalendar) -> date:
    current = start
    counted = 0
    while counted < amount:
        current += timedelta(days=1)
        if not calendar.is_non_working(current):
            counted += 1
    return current


def roll_forward(day: date, calendar: HolidayCalendar) -> date:
    current = day
    while calendar.is_non_working(current):
        current += timedelta(days=1)
    return current


def nested_value(event: dict[str, Any], dotted_key: str) -> Any:
    value: Any = event
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def condition_errors(event: dict[str, Any], rule: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if event.get("procedure_type") != rule.get("procedure_type"):
        errors.append("procedure_type_mismatch")
    if event.get("event_type") != rule.get("event_type"):
        errors.append("event_type_mismatch")
    for key, constraint in rule.get("conditions", {}).items():
        actual = nested_value(event, key)
        if "equals" in constraint and actual != constraint["equals"]:
            errors.append(f"condition_mismatch:{key}")
        elif "one_of" in constraint and actual not in constraint["one_of"]:
            errors.append(f"condition_mismatch:{key}")
        elif constraint.get("required") is True and actual is None:
            errors.append(f"condition_missing:{key}")
    return errors


def result_shell(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "procedure_type": event.get("procedure_type"),
        "participant_role": event.get("participant_role"),
        "status": "needs_confirmation",
        "due_date": None,
        "original_excerpt": event.get("original_excerpt"),
        "source_locator": event.get("source_locator"),
        "rule_id": event.get("rule_id"),
        "rule_title": None,
        "official_sources": [],
        "confidence": event.get("confidence", "low"),
        "reason_codes": [],
        "warnings": [],
        "calculation": {
            "trigger_date": event.get("trigger_date"),
            "duration_value": None,
            "duration_unit": None,
            "unadjusted_due_date": None,
            "adjusted_due_date": None,
            "calendar_id": None,
        },
    }


def calculate_event(
    event: dict[str, Any],
    rules_by_id: dict[str, dict[str, Any]],
    holiday_calendar: HolidayCalendar | None,
) -> dict[str, Any]:
    result = result_shell(event)
    trigger_status = event.get("trigger_date_status")
    trigger_value = event.get("trigger_date")

    if trigger_status != "confirmed" or not trigger_value:
        result["reason_codes"].append(
            "missing_trigger_date" if not trigger_value else "uncertain_trigger_date"
        )
        result["warnings"].append(
            "触发日期缺失或未确认，因此未输出精确期限。"
        )
        return result

    try:
        trigger = parse_date(trigger_value, "trigger_date")
    except ValueError:
        result["reason_codes"].append("invalid_trigger_date")
        result["warnings"].append("触发日期格式无效，因此未输出精确期限。")
        return result

    rule_id = event.get("rule_id")
    if not rule_id:
        result["reason_codes"].append("missing_rule")
        result["warnings"].append("没有匹配的规则，因此未输出精确期限。")
        return result
    rule = rules_by_id.get(rule_id)
    if rule is None:
        result["reason_codes"].append("rule_not_found")
        result["warnings"].append("规则包中不存在该 rule_id，因此未输出精确期限。")
        return result
    result["rule_title"] = rule.get("title")
    result["official_sources"] = rule.get("official_sources", [])
    if rule.get("verification", {}).get("status") != "verified":
        result["reason_codes"].append("rule_unverified")
        result["warnings"].append("规则尚未核验，因此未输出精确期限。")
        return result

    mismatches = condition_errors(event, rule)
    if mismatches:
        result["reason_codes"].extend(mismatches)
        result["warnings"].append("事件事实不满足规则的全部条件，因此未输出精确期限。")
        return result

    duration = rule.get("duration", {})
    amount = duration.get("value")
    unit = duration.get("unit")
    if not isinstance(amount, int) or amount <= 0 or unit not in {
        "calendar_days",
        "working_days",
        "years",
    }:
        result["reason_codes"].append("invalid_rule_duration")
        result["warnings"].append("规则的期限参数无效，因此未输出精确期限。")
        return result

    # A missing calendar still permits a conservative mechanical calculation,
    # but never a confirmed result when holiday handling matters.
    provisional = False
    calendar = holiday_calendar or default_weekend_calendar(
        trigger, trigger + timedelta(days=max(amount * 3, 32))
    )
    result["calculation"]["calendar_id"] = calendar.calendar_id

    if unit == "calendar_days":
        unadjusted = trigger + timedelta(days=amount)
    elif unit == "working_days":
        unadjusted = add_working_days(trigger, amount, calendar)
    else:
        unadjusted = add_years(trigger, amount)

    adjusted = unadjusted
    roll_required = bool(rule.get("calculation", {}).get("roll_forward_if_nonworking"))
    if roll_required:
        adjusted = roll_forward(unadjusted, calendar)

    calendar_needed = unit == "working_days" or roll_required
    if calendar_needed and not calendar.covers(trigger, adjusted):
        provisional = True
        result["reason_codes"].append("holiday_calendar_incomplete")
        result["warnings"].append(
            "节假日表缺失或未完整覆盖计算区间；该日期仅为暂定结果。"
        )

    if rule.get("requires_review"):
        provisional = True
        result["reason_codes"].append("substantive_review_required")
        review_reason = rule.get("review_reason") or "该规则要求额外的实体或程序事实审查。"
        result["warnings"].append(review_reason)

    result["status"] = "provisional" if provisional else "confirmed"
    result["due_date"] = adjusted.isoformat()
    result["calculation"].update(
        {
            "duration_value": amount,
            "duration_unit": unit,
            "unadjusted_due_date": unadjusted.isoformat(),
            "adjusted_due_date": adjusted.isoformat(),
        }
    )
    if provisional and CONFIDENCE_ORDER.get(result["confidence"], 0) > 1:
        result["confidence"] = "medium"
    return result


def validate_facts(facts: dict[str, Any]) -> None:
    if facts.get("schema_version") != "1.0":
        raise ValueError("facts.schema_version must be '1.0'")
    if not facts.get("matter_id"):
        raise ValueError("facts.matter_id is required")
    events = facts.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("facts.events must be a non-empty array")
    required = {
        "event_id",
        "event_type",
        "procedure_type",
        "participant_role",
        "trigger_date",
        "trigger_date_status",
        "original_excerpt",
        "source_locator",
        "rule_id",
        "confidence",
    }
    seen: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"events[{index}] must be an object")
        missing = sorted(required - event.keys())
        if missing:
            raise ValueError(f"events[{index}] is missing: {', '.join(missing)}")
        event_id = str(event["event_id"])
        if event_id in seen:
            raise ValueError(f"Duplicate event_id: {event_id}")
        seen.add(event_id)
        if not event.get("original_excerpt"):
            raise ValueError(f"events[{index}].original_excerpt is required")
        locator = event.get("source_locator")
        if not isinstance(locator, dict) or not locator.get("file_name") or not locator.get("location"):
            raise ValueError(f"events[{index}].source_locator is incomplete")
        if event.get("trigger_date_status") not in {"confirmed", "uncertain", "missing"}:
            raise ValueError(f"events[{index}].trigger_date_status is invalid")
        if event.get("confidence") not in CONFIDENCE_ORDER:
            raise ValueError(f"events[{index}].confidence is invalid")


def calculate_all(
    facts: dict[str, Any],
    rule_pack: dict[str, Any],
    holiday_calendar: HolidayCalendar | None,
) -> dict[str, Any]:
    validate_facts(facts)
    rules = rule_pack.get("rules")
    if not isinstance(rules, list):
        raise ValueError("rules.json must contain a rules array")
    rules_by_id: dict[str, dict[str, Any]] = {}
    for rule in rules:
        rule_id = rule.get("rule_id")
        if not rule_id:
            raise ValueError("Every rule must have a rule_id")
        if rule_id in rules_by_id:
            raise ValueError(f"Duplicate rule_id: {rule_id}")
        rules_by_id[rule_id] = rule

    results = [
        calculate_event(event, rules_by_id, holiday_calendar)
        for event in facts["events"]
    ]
    counts = {
        status: sum(result["status"] == status for result in results)
        for status in ("confirmed", "provisional", "needs_confirmation")
    }
    return {
        "schema_version": "1.0",
        "matter_id": facts["matter_id"],
        "source_document": facts.get("source_document"),
        "rule_pack_version": rule_pack.get("rule_pack_version"),
        "rule_pack_verified_at": rule_pack.get("verified_at"),
        "holiday_calendar": (
            {
                "calendar_id": holiday_calendar.calendar_id,
                "complete": holiday_calendar.complete,
                "coverage_start": holiday_calendar.coverage_start.isoformat(),
                "coverage_end": holiday_calendar.coverage_end.isoformat(),
                "source_url": holiday_calendar.source_url,
                "verified_at": holiday_calendar.verified_at,
            }
            if holiday_calendar
            else None
        ),
        "summary": counts,
        "results": results,
        "disclaimer": "期限结果仅供人工复核；请核对原文、现行法、送达事实、节假日和具体程序类型。",
    }


def markdown_escape(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def to_markdown(output: dict[str, Any]) -> str:
    lines = [
        "# 法律期限提取结果",
        "",
        f"- 事项：`{markdown_escape(output['matter_id'])}`",
        f"- 规则包：`{markdown_escape(output.get('rule_pack_version'))}`（核验日：{markdown_escape(output.get('rule_pack_verified_at'))}）",
        f"- 结果：确认 {output['summary']['confirmed']}；暂定 {output['summary']['provisional']}；待确认 {output['summary']['needs_confirmation']}",
        "",
        "> 仅供人工复核。必须核对原文、现行法、真实送达日期、法定节假日和具体程序类型。",
        "",
        "| 事件 | 状态 | 期限日 | 规则 | 置信度 | 原文依据 | 位置 |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in output["results"]:
        locator = result.get("source_locator") or {}
        location = f"{locator.get('file_name', '')} · {locator.get('location', '')}"
        lines.append(
            "| "
            + " | ".join(
                markdown_escape(value)
                for value in (
                    result.get("event_id"),
                    result.get("status"),
                    result.get("due_date") or "—",
                    result.get("rule_id") or "—",
                    result.get("confidence"),
                    result.get("original_excerpt"),
                    location,
                )
            )
            + " |"
        )
        if result.get("warnings"):
            lines.extend(
                ["", f"## {markdown_escape(result.get('event_id'))}", ""]
                + [f"- {warning}" for warning in result["warnings"]]
            )
    lines.append("")
    return "\n".join(lines)


def ics_escape(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_ics_line(line: str, limit: int = 75) -> list[str]:
    """Fold an iCalendar content line without splitting UTF-8 characters.

    RFC 5545 measures the 75-octet recommendation after UTF-8 encoding. A
    continuation line begins with one space, which is included in that limit.
    """
    if limit < 5:
        raise ValueError("ICS fold limit must fit one UTF-8 character and a space")
    if len(line.encode("utf-8")) <= limit:
        return [line]

    parts: list[str] = []
    prefix = ""
    current: list[str] = []
    current_bytes = 0
    available = limit

    for character in line:
        character_bytes = len(character.encode("utf-8"))
        if current and current_bytes + character_bytes > available:
            parts.append(prefix + "".join(current))
            prefix = " "
            current = []
            current_bytes = 0
            available = limit - 1
        if character_bytes > available:
            raise ValueError("ICS fold limit is too small for a UTF-8 character")
        current.append(character)
        current_bytes += character_bytes

    if current:
        parts.append(prefix + "".join(current))
    return parts


def to_ics(output: dict[str, Any]) -> str:
    raw_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OpenLawKit//Legal Deadline Extractor 0.1//ZH-CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for result in output["results"]:
        if not result.get("due_date"):
            continue
        due = parse_date(result["due_date"], "due_date")
        uid_source = f"{output['matter_id']}|{result['event_id']}|{result['due_date']}"
        uid = hashlib.sha256(uid_source.encode("utf-8")).hexdigest()[:32]
        description_parts = [
            f"状态：{result['status']}",
            f"规则：{result.get('rule_id') or '—'}",
            f"原文：{result.get('original_excerpt') or '—'}",
        ]
        description_parts.extend(result.get("warnings") or [])
        raw_lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}@openlawkit.local",
                f"DTSTAMP:{str(output.get('rule_pack_verified_at') or '1970-01-01').replace('-', '')}T000000Z",
                f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(due + timedelta(days=1)).strftime('%Y%m%d')}",
                f"SUMMARY:{ics_escape('法律期限：' + (result.get('rule_title') or result['event_id']))}",
                f"DESCRIPTION:{ics_escape(chr(10).join(description_parts))}",
                "STATUS:TENTATIVE" if result["status"] == "provisional" else "STATUS:CONFIRMED",
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
        )
    raw_lines.append("END:VCALENDAR")
    folded: list[str] = []
    for line in raw_lines:
        folded.extend(fold_ics_line(line))
    return "\r\n".join(folded) + "\r\n"


def write_outputs(output: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "deadlines.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "deadlines.md").write_text(to_markdown(output), encoding="utf-8")
    (output_dir / "deadlines.ics").write_text(to_ics(output), encoding="utf-8", newline="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate auditable deadlines from reviewed OpenLawKit facts JSON."
    )
    parser.add_argument("facts", type=Path, help="Path to facts JSON")
    parser.add_argument("--rules", type=Path, required=True, help="Path to verified rules JSON")
    parser.add_argument("--holidays", type=Path, help="Optional reviewed holiday calendar JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("deadline-output"),
        help="Directory for deadlines.json, deadlines.md, and deadlines.ics",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    facts = load_json(args.facts)
    rule_pack = load_json(args.rules)
    holiday_calendar = (
        HolidayCalendar.from_json(load_json(args.holidays)) if args.holidays else None
    )
    output = calculate_all(facts, rule_pack, holiday_calendar)
    write_outputs(output, args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir.resolve()),
                "summary": output["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
