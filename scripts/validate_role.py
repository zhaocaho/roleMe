from __future__ import annotations

import argparse

from tools.role_ops import doctor_role


parser = argparse.ArgumentParser()
parser.add_argument("role_name")
args = parser.parse_args()
print(doctor_role(args.role_name))
