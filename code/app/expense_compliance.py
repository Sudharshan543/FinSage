"""Compatibility alias for expense compliance tools."""

import sys

import app.tools.expense_compliance as _implementation

sys.modules[__name__] = _implementation
