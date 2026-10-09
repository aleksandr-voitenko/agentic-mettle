"""Keep the advertised, protocol, and executable versions in sync."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
