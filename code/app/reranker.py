"""Compatibility alias for evidence reranking."""

import sys

import app.tools.reranker as _implementation

sys.modules[__name__] = _implementation
