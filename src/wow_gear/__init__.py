"""Classic Gear Calculator: explainable, profile-aware item comparisons for WoW Classic.

The package is layered; each subpackage's docstring says what it owns and what it may
import, and ``tests/unit/test_architecture.py`` enforces those rules.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("classic-wow-gear-calculator")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+source"

__all__ = ["__version__"]
