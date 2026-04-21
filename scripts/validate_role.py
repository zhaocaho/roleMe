from __future__ import annotations

import argparse

from tools.role_ops import doctor_role


def validate_role(role_name: str) -> None:
    report = doctor_role(role_name)
    for missing in report.missing_files:
        print(f"missing: {missing}")
    for warning in report.warnings:
        print(f"warning: {warning}")
    if report.missing_files or report.warnings:
        raise SystemExit(1)
    print(f"ok: {role_name}")


parser = argparse.ArgumentParser()
parser.add_argument("role_name")
args = parser.parse_args()

validate_role(args.role_name)
