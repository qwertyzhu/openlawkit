"""Run both deterministic fictional OpenLawKit demos from any supported OS."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    printable = " ".join(command)
    print(f"\n> {printable}")
    subprocess.run(command, cwd=ROOT, check=True)


def absolute_without_resolving(path: Path) -> Path:
    """Return a lexical absolute path without following a link at the target."""
    return Path(os.path.abspath(os.fspath(path)))


def clean_demo_output(output_dir: Path, expected_output: Path) -> None:
    """Remove only the real, fixed demo directory; never follow link-like paths."""
    if output_dir != expected_output:
        raise ValueError("--clean is limited to the repository demo-output directory")
    is_junction = getattr(output_dir, "is_junction", lambda: False)
    if output_dir.is_symlink() or is_junction() or output_dir.is_mount():
        raise ValueError("--clean refuses a symlink, junction, or mount-point output directory")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError("--clean output exists but is not a directory")
        shutil.rmtree(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo-output",
        help="Output directory (default: demo-output under the repository root)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the selected output directory before running (only demo-output is accepted)",
    )
    args = parser.parse_args()
    output_dir = absolute_without_resolving(args.output_dir)
    default_output = absolute_without_resolving(ROOT / "demo-output")

    if args.clean:
        try:
            clean_demo_output(output_dir, default_output)
        except ValueError as exc:
            parser.error(str(exc))

    output_dir.mkdir(parents=True, exist_ok=True)
    reviewed = output_dir / "reviewed.docx"
    verification = output_dir / "contract-verification.json"
    deadlines = output_dir / "deadlines"

    run(
        [
            sys.executable,
            "skills/contract-comment-review/scripts/add_comments.py",
            "examples/contract-review/fictional-service-contract.docx",
            "examples/contract-review/fictional-findings.json",
            "-o",
            str(reviewed),
        ]
    )
    run(
        [
            sys.executable,
            "skills/contract-comment-review/scripts/verify_comments.py",
            "examples/contract-review/fictional-service-contract.docx",
            str(reviewed),
            "examples/contract-review/fictional-findings.json",
            "--report",
            str(verification),
        ]
    )
    run(
        [
            sys.executable,
            "skills/legal-deadline-extractor/scripts/calculate_deadlines.py",
            "examples/deadline-extractor/fictional-labor-facts.json",
            "--rules",
            "skills/legal-deadline-extractor/references/rules.json",
            "--holidays",
            "skills/legal-deadline-extractor/references/holidays-cn-2026.json",
            "--output-dir",
            str(deadlines),
        ]
    )

    print("\nDemo complete:")
    print(f"- Word review: {reviewed}")
    print(f"- Integrity report: {verification}")
    print(f"- Deadline JSON/Markdown/ICS: {deadlines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
