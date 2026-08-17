#!/usr/bin/env python3
"""Dependency-free Prometheus dispatcher for XPolicyLab policy adapters.

XPolicyLab is a policy zoo, not one trainer. This adapter selects exactly one
existing ``policy/<NAME>`` directory, validates the name and stage script, and
executes that script with an argv array. It does not duplicate XPolicyLab's
robot/action registries or infer per-policy capabilities.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
POLICY_ROOT = ROOT / "policy"
CAPABILITIES_PATH = Path(__file__).with_name("capabilities.json")
POLICY_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
STAGE_SCRIPTS = {
    "prepare": "process_data.sh",
    "train": "train.sh",
    "eval": "eval.sh",
    "serve": "setup_eval_policy_server.sh",
}
REQUIRED_ROOT_PATHS = (
    Path("AGENTS.md"),
    Path("XPolicyLab.py"),
    Path("pyproject.toml"),
    Path("policy"),
)


def capabilities() -> dict[str, object]:
    payload = json.loads(CAPABILITIES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "prometheus_source_adapter_v1":
        raise RuntimeError("unsupported Prometheus source-adapter schema")
    return payload


def resolve_policy(policy_name: str) -> Path:
    if not POLICY_NAME_RE.fullmatch(policy_name):
        raise ValueError(
            "policy_name must contain only ASCII letters, digits, underscore, and hyphen"
        )
    candidate = (POLICY_ROOT / policy_name).resolve()
    if candidate.parent != POLICY_ROOT.resolve() or not candidate.is_dir():
        raise ValueError(f"unknown XPolicyLab policy: {policy_name!r}")
    return candidate


def doctor(policy_name: str | None = None) -> dict[str, object]:
    missing = [path.as_posix() for path in REQUIRED_ROOT_PATHS if not (ROOT / path).exists()]
    declared = capabilities()
    if declared["capabilities"]["hardware_rollout_authorized"] is not False:  # type: ignore[index]
        raise RuntimeError("training source must not authorize hardware rollout")
    if declared["dataset"]["robot_schema_owner"] != "selected_policy_and_parent_workspace":  # type: ignore[index]
        raise RuntimeError("XPolicyLab robot schemas must remain source-owned")
    if missing:
        raise RuntimeError(f"missing required XPolicyLab paths: {missing}")

    report: dict[str, object] = {
        "ok": True,
        "policy_id": declared["policy_id"],
        "checked_paths": [path.as_posix() for path in REQUIRED_ROOT_PATHS],
        "imports_policy_stack": False,
        "copies_robot_registry": False,
    }
    if policy_name is not None:
        policy_dir = resolve_policy(policy_name)
        report["policy_name"] = policy_name
        report["available_stages"] = {
            stage: (policy_dir / script).is_file()
            for stage, script in STAGE_SCRIPTS.items()
        }
    return report


def build_argv(stage: str, policy_name: str, native_args: Sequence[str]) -> list[str]:
    if stage not in STAGE_SCRIPTS:
        raise ValueError(
            f"unsupported generic stage {stage!r}; resume and export are policy-specific"
        )
    policy_dir = resolve_policy(policy_name)
    script = policy_dir / STAGE_SCRIPTS[stage]
    if not script.is_file():
        raise RuntimeError(f"policy {policy_name!r} does not provide {script.name}")
    args = list(native_args)
    if args[:1] == ["--"]:
        args.pop(0)
    # Use a repository-relative path so the planned argv is portable. Bash is
    # an explicit argv element; no command is assembled as a shell string.
    relative_script = script.relative_to(ROOT).as_posix()
    return ["bash", relative_script, *args]


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _stage_parser(subparsers: argparse._SubParsersAction, name: str) -> None:
    parser = subparsers.add_parser(name)
    parser.add_argument("--policy-name", required=True)
    parser.add_argument("--plan", action="store_true", help="print argv instead of executing")
    parser.add_argument("native_args", nargs=argparse.REMAINDER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("capabilities")
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--policy-name")
    for stage in STAGE_SCRIPTS:
        _stage_parser(subparsers, stage)
    args = parser.parse_args(argv)

    if args.command == "capabilities":
        _print_json(capabilities())
        return 0
    if args.command == "doctor":
        _print_json(doctor(args.policy_name))
        return 0

    command = build_argv(args.command, args.policy_name, args.native_args)
    if args.plan:
        _print_json({"argv": command, "cwd": str(ROOT), "shell": False})
        return 0
    os.chdir(ROOT)
    os.execvp(command[0], command)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
