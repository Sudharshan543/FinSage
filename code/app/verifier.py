"""Compatibility alias for evidence verification."""

import sys

import app.tools.verifier as _implementation

sys.modules[__name__] = _implementation
