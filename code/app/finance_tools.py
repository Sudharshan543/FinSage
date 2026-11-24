"""Compatibility alias for finance data tools."""

import sys

import app.tools.finance as _implementation

sys.modules[__name__] = _implementation
