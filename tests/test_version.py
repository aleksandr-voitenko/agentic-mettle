"""Keep the advertised, protocol, and executable versions in sync."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import mettle


ROOT = Path(mettle.__file__).resolve().parent


class VersionTest(unittest.TestCase):
    def test_readme_version_matches_helper(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        versions = re.findall(r"^\*\*Version (\d+\.\d+\.\d+)\b", text, re.MULTILINE)
        self.assertEqual(versions, [mettle.VERSION])

    def test_protocol_version_matches_helper(self):
        text = (ROOT / "PERSONALITY.md").read_text(encoding="utf-8")
        versions = re.findall(r"^Protocol version: \*\*(\d+\.\d+\.\d+)\*\*", text, re.MULTILINE)
        self.assertEqual(versions, [mettle.VERSION])

    def test_cli_reports_current_version(self):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "mettle.py"), "--version"],
            stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), mettle.VERSION)
        self.assertEqual(result.stderr, "")

    def test_installed_package_and_workspace_reference_match_version(self):
        with tempfile.TemporaryDirectory(prefix="mettle-version-") as temporary:
            root = Path(temporary)
            mettle.install(root, [])
            package = root / mettle.PACKAGE
            for filename in ("mettle.py", "mettle_installer.py", "mettle_work.py", "mettle_migrate.py", "mettle_catalogue.py"):
                self.assertEqual((package / "tools" / filename).read_bytes(), (ROOT / filename).read_text(encoding="utf-8").encode("utf-8"))
            for installed, source in (("PERSONALITY.md", "PERSONALITY.md"),
                                      ("REFERENCE.md", "docs/records.md"),
                                      ("WORK_REFERENCE.md", "docs/workspaces.md")):
                self.assertEqual((package / installed).read_bytes(), (ROOT / source).read_text(encoding="utf-8").encode("utf-8"))
            self.assertIn(f"Version **{mettle.VERSION}**", (package / "WORK_REFERENCE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
