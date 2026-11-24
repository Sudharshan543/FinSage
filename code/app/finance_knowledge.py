"""Compatibility alias for policy retrieval."""

import sys

import app.tools.retriever as _implementation

sys.modules[__name__] = _implementation
