"""LMetrics - Prometheus exporter for metrics collected from log files."""

from distutils.version import LooseVersion

import pkg_resources

__all__ = ["__version__"]

__version__ = LooseVersion(pkg_resources.require("lmetrics")[0].version)
