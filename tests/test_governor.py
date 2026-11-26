import unittest
from governor import Observer, can_recover, recovery_prompt, run_recovery
from unittest.mock import patch, Mock
from pathlib import Path
import tempfile
import threading
from benchmark import prepare


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.obs = Observer("ses_a")

    def event(self, kind, **props):
        self.obs.feed({"type": kind, "properties": props})

    def test_delayed_part_type_and_limit(self):
        self.event("message.part.delta", sessionID="ses_a", partID="p", delta="abc")
        self.assertEqual(self.obs.totals(), {"unknown": 3})
        self.event("message.part.updated", part={"sessionID": "ses_a", "id": "p", "type": "reasoning"})
        self.assertEqual(self.obs.totals(), {"reasoning": 3})
        self.assertIsNone(self.obs.reason(4))
        self.event("message.part.delta", sessionID="ses_a", partID="p", delta="de")
        self.assertEqual(self.obs.reason(4), "reasoning_limit")
        self.assertIsNone(self.obs.reason(None))

    def test_session_filter_and_text(self):
        self.event("message.part.updated", part={"sessionID": "ses_a", "id": "p", "type": "text"})
        self.event("message.part.delta", sessionID="ses_b", partID="p", delta="wrong")
        self.event("message.part.delta", sessionID="ses_a", partID="p", delta="hello")
        self.event("message.part.delta", sessionID="ses_a", partID="p", field="other", delta="ignored")
        self.assertEqual(self.obs.totals(), {"text": 5})
        self.assertIsNone(self.obs.reason(1))

    def test_idle_requires_activity(self):
        self.event("session.idle", sessionID="ses_a")
        self.assertIsNone(self.obs.reason(None))
        self.event("session.status", sessionID="ses_a", status={"type": "busy"})
        self.event("session.idle", sessionID="ses_a")
        self.assertEqual(self.obs.reason(None), "completed")

    def test_error(self):
        self.event("session.error", sessionID="ses_a")
        self.assertEqual(self.obs.reason(None), "session_error")


class RecoveryTests(unittest.TestCase):
    def test_gates(self):
        result = {"stop_reason": "reasoning_limit", "abort_acknowledged": True,
                  "final_status": "not-listed"}
        checks = {"fixture_preserved": True, "exact_output": False}
        self.assertTrue(can_recover(result, checks, 60))
        self.assertFalse(can_recover(result, checks, 15))
        self.assertFalse(can_recover(dict(result, abort_acknowledged=False), checks, 60))
        self.assertFalse(can_recover(dict(result, final_status="busy"), checks, 60))
        self.assertFalse(can_recover(result, {"fixture_preserved": False}, 60))
        self.assertFalse(can_recover(result, {"fixture_preserved": True}, 60))
        self.assertTrue(recovery_prompt("task").endswith("Original task:\ntask"))

    @patch("governor.time.sleep")
    @patch("governor.connect_events")
    @patch("governor.supervise")
    def test_one_retry_shared_budget(self, supervise, connect, sleep):
        first = {"stop_reason": "reasoning_limit", "abort_acknowledged": True,
                 "final_status": "not-listed", "streamed_characters": {"reasoning": 3001}}
        second = dict(first, stop_reason="completed", abort_acknowledged=None,
                      streamed_characters={"reasoning": 10, "text": 20})
        supervise.side_effect = [first, second]
        connect.return_value = (Mock(), threading.Event())
        client = Mock()
        client.api.return_value = {}
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "fresh"
            prompt = prepare("write-v1", workspace)
            result = run_recovery(client, "ses_a", prompt, "local/model", 120, 3000,
                                  Mock(), threading.Event(), "write-v1", workspace)
        self.assertEqual(supervise.call_count, 2)
        self.assertEqual(supervise.call_args.args[1], "ses_a")
        self.assertLessEqual(supervise.call_args.args[4], 120)
        self.assertEqual(result["recovery_attempts"], 1)
        self.assertEqual(result["streamed_characters"], {"reasoning": 3011, "text": 20})
        self.assertEqual(result["stop_reason"], "completed")


if __name__ == "__main__":
    unittest.main()
