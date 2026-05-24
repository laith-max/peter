"""Entry point for `python -m jetson_logging`.

Acts as the boot gate the supervisor relies on. It (1) loads and validates
the *real* deployed `config/site.json`, then (2) runs the privacy-filter
self-tests. A non-zero exit is a refusal to start the inference pipeline:
an unconfigured or misconfigured device fails step (1), and a broken filter
fails step (2).
"""

from __future__ import annotations

import sys
import unittest

from jetson_logging import config
from jetson_logging.filters.privacy import PrivacyConfig, PrivacyFilterError


def main() -> int:
    try:
        cfg = config.load_validated()
        PrivacyConfig.from_site_config(cfg)
    except (config.ConfigError, PrivacyFilterError) as e:
        print(f"jetson_logging: refusing to start — {e}", file=sys.stderr)
        return 1

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName("jetson_logging.tests.test_privacy")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
