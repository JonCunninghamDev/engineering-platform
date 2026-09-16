import sys
import unittest


class ReusablePythonCapabilityTest(unittest.TestCase):
    def test_python_capability_is_available(self) -> None:
        self.assertGreaterEqual(sys.version_info, (3, 12))


if __name__ == "__main__":
    unittest.main()
