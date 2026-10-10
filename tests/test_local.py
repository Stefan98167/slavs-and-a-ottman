import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arena_kit.local import main, run_local


class LocalTests(unittest.TestCase):
    def test_pipeline_and_json_without_network(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "socket.socket", side_effect=AssertionError("Offline mode attempted network access")
        ), patch.dict(os.environ, {"ARENA_URL": "https://must-not-be-called.invalid", "ARENA_API_KEY": "unused"}):
            csv = Path(directory) / "quote.csv"
            csv.write_text("unit_price,currency\n17.47,EUR\n")
            result = run_local([csv])
            self.assertEqual(result["mode"], "local")
            self.assertEqual(result["decisions"][0]["proposed_unit_price"], 16.60)
            extracted = Path(directory) / "extracted.json"
            extracted.write_text(json.dumps([{k: v for k, v in result["decisions"][0].items()
                                             if k in ("Information", "Source", "Priority (Argument wise)")}]))
            output = Path(directory) / "decisions.json"
            main(["--json", str(extracted), "--out", str(output)])
            self.assertEqual(json.loads(output.read_text())["decisions"][0]["action"], "counter_offer")
            with self.assertRaises(ValueError):
                run_local([csv], json_file=extracted)

    def test_cli_needs_no_third_party_packages_or_network(self):
        # -S disables site-packages. Patch sockets before importing the runner.
        script = (
            "import socket,sys; "
            "socket.socket=lambda *a,**k: (_ for _ in ()).throw(AssertionError('Network attempted')); "
            "import io; from arena_kit.local import run_local; "
            "import json; print(json.dumps(run_local([io.StringIO('unit_price\\n17.47\\n')]))); "
            "assert 'arena_kit.client' not in sys.modules; "
            "assert 'httpx' not in sys.modules"
        )
        process = subprocess.run([sys.executable, "-S", "-c", script],
                                 cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertTrue(result["decisions"])
        self.assertEqual(result["mode"], "local")

    def test_no_default_data_or_bundled_evidence(self):
        with self.assertRaisesRegex(ValueError, "no bundled data"):
            run_local()
        with self.assertRaisesRegex(ValueError, "Bundled"):
            run_local(["data/data/quotes.csv"])
