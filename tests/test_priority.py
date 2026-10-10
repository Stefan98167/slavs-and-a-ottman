import io
from contextlib import redirect_stderr
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from arena_kit.priority import PRIORITY_COLUMN, prioritize
from arena_kit.quote_extract import extract


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.records = extract(io.StringIO("description\nPrice fixed until December\nRepeated delivery failures\n"))
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.supplier_csv = Path(temporary.name) / "supplier_quote.csv"
        self.supplier_csv.write_text("unit_price\n" + "17.47\n" * 108)

    def test_extractor_integration_preserves_records_and_reorders_response(self):
        complete = Mock(return_value=json.dumps({"priorities": [
            {"row_id": 1, "priority": 2}, {"row_id": 0, "priority": 1},
        ]}))
        rows = extract(io.StringIO("description\nPrice fixed until December\nRepeated delivery failures\n"),
                       priority="llm", complete=complete, priority_context="Renewal of contract")
        self.assertEqual([r[PRIORITY_COLUMN] for r in rows], [1, 2])
        self.assertEqual([r["Information"] for r in rows], [r["Information"] for r in self.records])
        self.assertEqual([r["Source"] for r in rows], [r["Source"] for r in self.records])
        payload = json.loads(complete.call_args.args[1])
        self.assertEqual(payload["negotiation_context"], "Renewal of contract")
        self.assertNotIn(PRIORITY_COLUMN, payload["records"][0])
        self.assertEqual(self.records[0][PRIORITY_COLUMN], 3)

    def test_batches(self):
        def complete(system, user):
            data = json.loads(user)
            return json.dumps({"priorities": [{"row_id": r["row_id"], "priority": 1}
                                               for r in data["records"]]})
        mock = Mock(side_effect=complete)
        messages = []
        rows = prioritize(self.records, complete=mock, batch_size=1, progress=messages.append)
        self.assertEqual(mock.call_count, 2)
        self.assertEqual([r[PRIORITY_COLUMN] for r in rows], [1, 1])
        self.assertEqual(messages, ["Ranking batch 1/2 (1 records)...", "Batch 1/2 complete.",
                                    "Ranking batch 2/2 (1 records)...", "Batch 2/2 complete."])

    def test_cli_keeps_progress_out_of_json(self):
        from contextlib import redirect_stdout

        from arena_kit.quote_extract import main

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["quote_extract", str(self.supplier_csv), "--priority", "llm"]), patch(
            "arena_kit.cli.load_env"
        ), patch("arena_kit.agents.llm.llm_from_env") as factory, redirect_stdout(stdout), redirect_stderr(stderr):
            def complete(system, user):
                return json.dumps({"priorities": [{"row_id": r["row_id"], "priority": 1}
                                                   for r in json.loads(user)["records"]]})
            factory.return_value = complete
            main()
        self.assertEqual(len(json.loads(stdout.getvalue())), 108)
        self.assertIn("Ranking batch 1/5", stderr.getvalue())
        self.assertIn("Done: 108 records", stderr.getvalue())

    def test_invalid_responses_fail_without_fallback(self):
        replies = ["not json", "[]", '{"priorities": []}',
                   json.dumps({"priorities": [{"row_id": 0, "priority": 1}] * 2}),
                   json.dumps({"priorities": [{"row_id": 9, "priority": 1}]}),
                   json.dumps({"priorities": [{"row_id": 0, "priority": True}]}),
                   json.dumps({"priorities": [{"row_id": 0, "priority": 4}]}),
                   json.dumps({"priorities": [{"row_id": 0, "priority": "1"}]})]
        for reply in replies:
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                prioritize(self.records, complete=lambda system, user: reply)

    def test_provider_failures_propagate(self):
        with self.assertRaises(TimeoutError):
            prioritize(self.records, complete=Mock(side_effect=TimeoutError("provider timed out")))

    def test_configured_provider_and_empty_input(self):
        with patch("arena_kit.agents.llm.llm_from_env") as factory:
            self.assertEqual(prioritize([]), [])
            factory.assert_not_called()
            factory.return_value = Mock(return_value=json.dumps({"priorities": [
                {"row_id": 0, "priority": 1}, {"row_id": 1, "priority": 2},
            ]}))
            self.assertEqual(prioritize(self.records)[0][PRIORITY_COLUMN], 1)
            factory.assert_called_once_with()

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            extract([], priority="unknown")
        with self.assertRaises(ValueError):
            prioritize(self.records, batch_size=0)

    def test_llm_request_uses_configured_endpoint(self):
        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": json.dumps({"priorities": [
            {"row_id": 0, "priority": 1}, {"row_id": 1, "priority": 2},
        ]})}}]}
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "openai", "LLM_MODEL": "test-model",
            "LLM_BASE_URL": "http://localhost:11434/v1", "LLM_API_KEY": "test-key",
        }), patch("httpx.post", return_value=response) as post:
            rows = prioritize(self.records)
        self.assertEqual([r[PRIORITY_COLUMN] for r in rows], [1, 2])
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "test-model")
        response.raise_for_status.assert_called_once()

    def test_missing_model_has_setup_error(self):
        from arena_kit.agents.llm import llm_from_env

        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "LLM_MODEL is missing"):
            llm_from_env()

    def test_cli_reports_configuration_error_without_traceback(self):
        from arena_kit.quote_extract import main

        stderr = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch("arena_kit.cli.load_env"), patch(
            "sys.argv", ["quote_extract", str(self.supplier_csv), "--priority", "llm"]
        ), redirect_stderr(stderr), self.assertRaises(SystemExit) as exc:
            main()
        self.assertEqual(exc.exception.code, 2)
        self.assertIn("LLM_MODEL is missing", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
