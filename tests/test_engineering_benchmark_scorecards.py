import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCORECARD_DOC = ROOT / "docs" / "engineering-benchmark-scorecards.md"
METRICS_DOC = ROOT / "docs" / "engineering-run-metrics.md"


class EngineeringBenchmarkScorecardDocsTest(unittest.TestCase):
    def test_scorecard_preserves_core_measurement_invariants(self):
        scorecard = SCORECARD_DOC.read_text(encoding="utf-8")
        metrics = METRICS_DOC.read_text(encoding="utf-8")

        self.assertIn("Safe", scorecard)
        self.assertIn("Reliable", scorecard)
        self.assertIn("Fast", scorecard)
        self.assertIn("Efficient", scorecard)
        self.assertIn("time to accepted change", scorecard.lower())
        self.assertIn("single-agent baseline", scorecard.lower())
        self.assertIn("never estimate", scorecard.lower())
        self.assertIn("engineering-run/v1", scorecard)

        self.assertIn("engineering-benchmark-scorecards.md", metrics)
        self.assertIn("time to accepted change", metrics.lower())
        self.assertIn("single-agent baseline", metrics.lower())


if __name__ == "__main__":
    unittest.main()
