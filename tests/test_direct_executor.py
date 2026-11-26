import json
import os
from pathlib import Path
import tempfile
import unittest

from benchmark import prepare, evaluate, KPIS, HTML_AFTER
from direct_executor import execute, dispatch, parse_call, ToolError


def reply(tool, args):
    return {"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": [
        {"type": "function", "function": {"name": tool, "arguments": json.dumps(args)}}]}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20,
                  "completion_tokens_details": {"reasoning_tokens": 0}}}


class DirectTests(unittest.TestCase):
    def test_kpi_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "fixture"
            prompt = prepare("kpi-v1", workspace)
            insertion = '<section id="demo" class="grid">' + "".join(
                f'<article class="card kpi"><h3>{label}</h3><p>{value}</p></article>'
                for label, value in KPIS) + '</section>\n'
            replies = iter([reply("read_file", {"path": "index.html"}),
                            reply("replace_text", {"path": "index.html", "old_text": HTML_AFTER,
                                                  "new_text": insertion + HTML_AFTER})])
            elapsed, outcome, details = execute("kpi-v1", workspace, prompt, "local", 1235,
                                                 request=lambda *a: next(replies))
            self.assertEqual(outcome, "completed")
            self.assertTrue(all(evaluate("kpi-v1", workspace).values()))
            self.assertEqual(details["recorded_tokens"]["reasoning"], 0)
            self.assertEqual(details["successful_tool_calls"], {"read_file": 1, "replace_text": 1})

    def test_no_tool_never_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "fixture"
            prompt = prepare("write-v1", workspace)
            response = {"choices": [{"finish_reason": "stop", "message": {"content": "Done"}}]}
            _, outcome, details = execute("write-v1", workspace, prompt, "local", 1235,
                                           request=lambda *a: response)
            self.assertEqual(outcome, "aborted")
            self.assertEqual(len(details["turns"]), 2)
            self.assertFalse((workspace / "hello.txt").exists())

    def test_path_restriction_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "fixture"
            prepare("write-v1", workspace)
            outside = Path(tmp) / "outside"
            outside.write_text("untouched")
            root = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with self.assertRaises(ToolError):
                    dispatch(root, "write-v1", "write_file", {"path": "../outside", "content": "bad"})
                with self.assertRaises(ToolError):
                    dispatch(root, "write-v1", "write_file", {"path": "README.txt", "content": "bad"})
                (workspace / "hello.txt").symlink_to(outside)
                with self.assertRaises(ToolError):
                    dispatch(root, "write-v1", "write_file", {"path": "hello.txt", "content": "bad"})
            finally:
                os.close(root)
            self.assertEqual(outside.read_text(), "untouched")

    def test_repair_after_failed_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "fixture"
            prompt = prepare("write-v1", workspace)
            replies = iter([reply("read_file", {"path": "README.txt"}),
                            reply("write_file", {"path": "hello.txt", "content": "wrong"}),
                            reply("write_file", {"path": "hello.txt", "content": "Hello Atlas\n"})])
            _, outcome, details = execute("write-v1", workspace, prompt, "local", 1235,
                                           request=lambda *a: next(replies))
            self.assertEqual(outcome, "completed")
            self.assertEqual(details["successful_tool_calls"]["write_file"], 2)

    def test_wrong_tool(self):
        with self.assertRaises(ToolError):
            parse_call(reply("read_file", {"path": "index.html"}), "replace_text")


if __name__ == "__main__":
    unittest.main()
