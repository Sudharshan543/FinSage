"""Compatibility alias for keyword-based HANA retrieval."""

import sys

import app.tools.keyword_retriever as _implementation

sys.modules[__name__] = _implementation
