import json
import unittest
from agent_refine import analyze


def message(parts, finish='tool-calls', tokens=None, **extra):
    return {'info': {'role': 'assistant', 'finish': finish, 'tokens': tokens or {}, **extra}, 'parts': parts}


def read(output='secret content'):
    return {'type': 'tool', 'tool': 'read', 'state': {'status': 'completed', 'input': {'filePath': '/private/path'}, 'output': output}}


class AnalyzerTests(unittest.TestCase):
    def test_repeat_reads(self):
        report = analyze({'messages': [message([read(), read(), read('different')])]})
        self.assertEqual(report['repeated_read_targets'], 2)
        self.assertEqual(report['identical_read_outputs'], 1)

    def test_edit_resets_read_tracking(self):
        edit = {'type': 'tool', 'tool': 'edit', 'state': {'status': 'completed'}}
        report = analyze({'messages': [message([read(), edit, read()])]})
        self.assertEqual(report['repeated_read_targets'], 0)
        self.assertEqual(report['recognized_completed_edit_calls'], 1)

    def test_limit_and_abort(self):
        report = analyze({'messages': [message([], 'length', {'reasoning': 100, 'output': 0}), message([{'type': 'reasoning', 'text': 'private reasoning'}], None, error={'name': 'MessageAbortedError'})]})
        self.assertEqual(report['finishes'], {'length': 1, 'aborted': 1})
        self.assertEqual(report['uncounted_reasoning_chars'], 17)
        self.assertEqual(report['reasoning_share_of_recorded_generation'], 1)

    def test_aggregate_privacy(self):
        report = analyze({'info': {'directory': '/private/path'}, 'messages': [message([read(), {'type': 'reasoning', 'text': 'secret content'}])]})
        serialized = json.dumps(report)
        self.assertNotIn('/private/path', serialized)
        self.assertNotIn('secret content', serialized)

    def test_empty(self):
        report = analyze({'messages': []})
        self.assertIsNone(report['elapsed_seconds'])
        self.assertIsNone(report['reasoning_share_of_recorded_generation'])

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            analyze({'not_messages': []})

    def test_elapsed_and_compaction(self):
        report = analyze({'info': {'time': {'created': 1000}}, 'messages': [{'info': {'role': 'user'}, 'parts': [{'type': 'compaction'}]}, message([], time={'created': 2000, 'completed': 4500})]})
        self.assertEqual(report['elapsed_seconds'], 3.5)
        self.assertEqual(report['compactions'], 1)

    def test_failed_edit_not_counted(self):
        edit = {'type': 'tool', 'tool': 'edit', 'state': {'status': 'error'}}
        report = analyze({'messages': [message([read(), edit, read()])]})
        self.assertEqual(report['recognized_completed_edit_calls'], 0)
        self.assertEqual(report['identical_read_outputs'], 1)


if __name__ == '__main__':
    unittest.main()
