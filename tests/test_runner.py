import json
from pathlib import Path
import sys
import tempfile
import unittest

from runner import command, environment, event_summary, run_process


class RunnerTests(unittest.TestCase):
    def test_explicit_workspace(self):
        workspace = Path("/tmp/synthetic-workspace")
        config = Path("/tmp/config.json")
        self.assertEqual(environment(workspace, config)["PWD"], str(workspace))
        self.assertEqual(environment(workspace, config)["OPENCODE_CONFIG"], str(config))
        args = command(workspace, "local/model", "task")
        self.assertEqual(args[args.index("--dir") + 1], str(workspace))
        self.assertNotIn("--auto", args)
        self.assertEqual(args[-1], "task")

    def test_events_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            events = [
                {"type": "reasoning", "sessionID": "ses_test123", "part": {"text": "private"}},
                {"type": "step_finish", "sessionID": "ses_test123", "part": {"reason": "stop"}},
                {"type": "custom_private_event", "sessionID": "ses_test123"},
            ]
            path.write_text("\n".join(map(json.dumps, events)) + "\ninvalid\n")
            summary, sid = event_summary(path)
            self.assertEqual(sid, "ses_test123")
            self.assertEqual(summary["last_finish"], "stop")
            self.assertEqual(summary["event_counts"], {"reasoning": 1, "step_finish": 1, "other": 1})
            self.assertEqual(summary["invalid_lines"], 1)
            self.assertNotIn("private", json.dumps(summary))
            self.assertNotIn(sid, json.dumps(summary))

    def test_ambiguous_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"sessionID":"ses_a"}\n{"sessionID":"ses_b"}\n')
            summary, sid = event_summary(path)
            self.assertIsNone(sid)
            self.assertEqual(summary["session_count"], 2)

    def test_process_exit_and_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = environment(root, root / "config")
            for i, code, budget, expected in [
                (1, "print('ok')", 5, "completed"),
                (2, "raise SystemExit(3)", 5, "aborted"),
                (3, "import time; time.sleep(30)", 0.2, "timeout"),
            ]:
                elapsed, outcome, rc = run_process(
                    [sys.executable, "-c", code], root, env,
                    root / f"{i}.out", root / f"{i}.err", budget)
                self.assertEqual(outcome, expected)
                self.assertGreaterEqual(elapsed, 0)
                if expected == "timeout":
                    self.assertLess(elapsed, 5)


if __name__ == "__main__":
    unittest.main()
