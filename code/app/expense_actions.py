"""Compatibility alias for expense exception actions."""

import sys

import app.tools.exception as _implementation

sys.modules[__name__] = _implementation
