from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = Path(__file__).with_name("adapter.py")
SPEC = importlib.util.spec_from_file_location("prometheus_xpolicy_lab_adapter", ADAPTER_PATH)
assert SPEC and SPEC.loader
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


class AdapterTest(unittest.TestCase):
    def test_doctor_is_structural_and_hardware_closed(self) -> None:
        report = ADAPTER.doctor("demo_policy")
        declared = ADAPTER.capabilities()
        self.assertTrue(report["ok"])
        self.assertFalse(report["imports_policy_stack"])
        self.assertFalse(report["copies_robot_registry"])
        self.assertFalse(declared["capabilities"]["hardware_rollout_authorized"])
        self.assertEqual(declared["capabilities"]["resume"], "per_policy")

    def test_policy_name_cannot_escape_policy_root(self) -> None:
        for value in ("../ACT", "ACT/train.sh", ".", "ACT;touch-owned", "ACT space"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ADAPTER.resolve_policy(value)

    def test_dispatch_is_an_explicit_argv_array(self) -> None:
        command = ADAPTER.build_argv("train", "demo_policy", ["bench", "run name"])
        self.assertEqual(command[:2], ["bash", "policy/demo_policy/train.sh"])
        self.assertEqual(command[-1], "run name")

    def test_missing_policy_stage_fails_closed(self) -> None:
        policy_dirs = [path for path in (ROOT / "policy").iterdir() if path.is_dir()]
        without_prepare = next(
            path for path in policy_dirs if not (path / "process_data.sh").is_file()
        )
        with self.assertRaisesRegex(RuntimeError, "does not provide process_data.sh"):
            ADAPTER.build_argv("prepare", without_prepare.name, [])

    def test_no_generic_resume_export_or_registry_copy(self) -> None:
        declared = ADAPTER.capabilities()
        self.assertFalse(declared["stages"]["resume"])
        self.assertFalse(declared["stages"]["export"])
        files = {path.name for path in Path(__file__).parent.iterdir()}
        self.assertNotIn("_robot_info.json", files)
        self.assertFalse(any("registry" in name.lower() for name in files))

    def test_cli_plan_does_not_run_policy_code(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                str(ADAPTER_PATH),
                "train",
                "--policy-name",
                "demo_policy",
                "--plan",
                "--",
                "RoboDojo",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(process.stdout)
        self.assertFalse(payload["shell"])
        self.assertEqual(payload["argv"][:2], ["bash", "policy/demo_policy/train.sh"])


if __name__ == "__main__":
    unittest.main()
