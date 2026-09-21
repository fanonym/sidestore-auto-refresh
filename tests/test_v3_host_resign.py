"""Exercise repair generation against the exact embedded revision, without an iOS build."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("host_resign_patch", ROOT / "scripts/patch_v3_host_resign.py")
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
FILES = ["AltStore/AppDelegate.swift", "AltStore/Managing Apps/AppManager.swift"] + [
    "SideStore/Core/Operations/" + name + ".swift"
    for name in ("OperationContexts", "PipelineRunner", "PipelineExecutor")]


class HostResignPatchTests(unittest.TestCase):
    def test_real_identity_guard_and_pipeline_exclusion(self):
        if not shutil.which("swiftc"):
            self.skipTest("Requires Swift compiler")
        guard = repair.TEMPLATE.read_text().split("extension V3AuthCenter {")[0]
        harness = (ROOT / "tests/fixtures/host_resign_guard_harness.swift").read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.swift"
            source.write_text(harness.replace("// INSERT_REAL_GUARD", guard))
            compile_result = subprocess.run(["swiftc", "-parse-as-library", "-module-cache-path", str(root / "module-cache"),
                                            str(source), "-o", str(root / "guard-check")],
                                            capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(root / "guard-check")], check=True, capture_output=True, text=True)
            self.assertIn("checks passed", result.stdout)

    def fixture(self, root):
        source = os.environ.get("EMBEDDED_SIDESTORE_TEST_SOURCE")
        if not source:
            self.skipTest("Requires pinned embedded source checkout")
        for name in FILES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(subprocess.check_output(["git", "-C", source, "show", repair.PIN + ":" + name]))
        app = root / FILES[0]
        app.write_text(app.read_text() + "\n" + "\n".join(
            (ROOT / "scripts/templates" / name).read_text()
            for name in ("v3_wire_contract.swift", "v3_sidestore_service.swift", "v3_headless_runtime.swift")))

    def apply(self, root):
        with patch.object(repair.subprocess, "check_output", return_value=repair.PIN):
            repair.patch(root)

    def test_apply_replay_parse_and_drift_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            self.apply(root)
            before = {p: (root / p).read_bytes() for p in FILES}
            self.apply(root)
            self.assertEqual(before, {p: (root / p).read_bytes() for p in FILES})
            if shutil.which("swiftc"):
                for name in FILES:
                    subprocess.run(["swiftc", "-frontend", "-parse", str(root / name)], check=True,
                                   capture_output=True, text=True)
            app = root / FILES[0]
            app.write_text(app.read_text() + "\n// drift\n")
            with self.assertRaisesRegex(ValueError, "drifted"):
                self.apply(root)

    def test_anchor_failure_leaves_all_sources_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / "SideStore/Core/Operations/PipelineExecutor.swift"
            path.write_text(path.read_text().replace("case .updateAppCertificate:", "case .changedStep:"))
            before = {p: (root / p).read_bytes() for p in FILES}
            with self.assertRaises(ValueError):
                self.apply(root)
            self.assertEqual(before, {p: (root / p).read_bytes() for p in FILES})
            self.assertFalse((root / ".v3-host-resign.json").exists())


if __name__ == "__main__":
    unittest.main()
