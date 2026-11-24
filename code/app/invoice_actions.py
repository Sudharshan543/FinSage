"""Compatibility alias for invoice actions."""

import sys

import app.tools.invoice as _implementation

sys.modules[__name__] = _implementation
