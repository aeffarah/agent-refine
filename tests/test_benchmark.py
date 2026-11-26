import tempfile
import unittest
from pathlib import Path

from benchmark import HTML_AFTER, HTML_BEFORE, KPIS, compare, evaluate, prepare, score


def valid_demo():
    cards = "".join(f'<article class="card kpi"><h3>{label}</h3><p>{value}</p></article>'
                    for label, value in KPIS)
    return '<section id="demo" class="grid">' + cards + '</section>\n'


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "work"

    def write_task(self):
        prepare("write-v1", self.workspace)
        (self.workspace / "hello.txt").write_bytes(b"Hello Atlas\n")

    def kpi_task(self, insertion=None):
        prepare("kpi-v1", self.workspace)
        (self.workspace / "index.html").write_bytes(
            (HTML_BEFORE + (valid_demo() if insertion is None else insertion) + HTML_AFTER).encode())

    def report(self, **overrides):
        args = dict(task="write-v1", workspace=self.workspace, condition="baseline",
                    trial=1, profile="synthetic", elapsed=10, outcome="completed")
        return score(**(args | overrides))

    def test_prepare_refuses_existing_directory(self):
        prepare("write-v1", self.workspace)
        with self.assertRaises(FileExistsError):
            prepare("write-v1", self.workspace)

    def test_write_success(self):
        self.write_task()
        self.assertTrue(self.report()["success"])

    def test_wrong_content_and_extra_file_fail(self):
        self.write_task()
        (self.workspace / "hello.txt").write_bytes(b"Hello Atlas")
        (self.workspace / "extra.txt").touch()
        checks = evaluate("write-v1", self.workspace)
        self.assertFalse(checks["exact_output"])
        self.assertFalse(checks["workspace_scope"])

    def test_symlink_rejected(self):
        self.write_task()
        target = self.workspace / "hello.txt"
        target.unlink()
        target.symlink_to(self.workspace / "README.txt")
        self.assertFalse(self.report()["success"])

    def test_timeout_and_aborted_cannot_pass(self):
        self.write_task()
        self.assertFalse(self.report(elapsed=121)["success"])
        self.assertFalse(self.report(outcome="timeout")["success"])
        self.assertFalse(self.report(outcome="aborted")["success"])

    def test_kpi_success(self):
        self.kpi_task()
        self.assertTrue(all(evaluate("kpi-v1", self.workspace).values()))

    def test_kpi_wrong_value(self):
        self.kpi_task(valid_demo().replace("$84,205", "$0"))
        self.assertFalse(evaluate("kpi-v1", self.workspace)["exact_kpi_values"])

    def test_kpi_script_and_extra_section_rejected(self):
        self.kpi_task(valid_demo() + "<script>alert(1)</script><section></section>")
        self.assertFalse(evaluate("kpi-v1", self.workspace)["valid_demo_structure"])

    def test_kpi_existing_content_preserved(self):
        self.kpi_task()
        path = self.workspace / "index.html"
        path.write_bytes(path.read_bytes().replace(b"$19/mo", b"$99/mo"))
        self.assertFalse(evaluate("kpi-v1", self.workspace)["fixture_preserved"])

    def test_compare_includes_failures_and_rejects_duplicates(self):
        self.write_task()
        first = self.report()
        second = self.report(trial=2, elapsed=120, outcome="timeout")
        row = compare([first, second])[0]
        self.assertEqual(row["success_rate"], 0.5)
        self.assertEqual(row["median_elapsed_all_seconds"], 65)
        self.assertEqual(row["median_elapsed_success_seconds"], 10)
        with self.assertRaises(ValueError):
            compare([first, first])

    def test_telemetry_optional(self):
        self.write_task()
        self.assertIsNone(self.report()["telemetry"])
        self.assertEqual(self.report(session={"messages": []})["telemetry"]["messages"], 0)

    def test_bad_measurement_rejected(self):
        self.write_task()
        with self.assertRaises(ValueError):
            self.report(elapsed=float("nan"))
        with self.assertRaises(ValueError):
            self.report(profile="/private/path")


if __name__ == "__main__":
    unittest.main()
