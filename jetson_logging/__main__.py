"""Entry point for `python -m jetson_logging`.

Runs the privacy-filter self-test described in README.md. The supervisor
treats a non-zero exit as a refusal to start the inference pipeline.
"""

from __future__ import annotations

import sys
import unittest


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName("jetson_logging.tests.test_privacy")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
