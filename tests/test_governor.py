import unittest
from governor import Observer


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


if __name__ == "__main__":
    unittest.main()
