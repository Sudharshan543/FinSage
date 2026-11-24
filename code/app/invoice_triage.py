"""Compatibility alias for invoice triage tools."""

import sys

import app.tools.invoice_triage as _implementation

sys.modules[__name__] = _implementation
