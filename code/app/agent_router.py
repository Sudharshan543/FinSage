"""Compatibility alias for the agent orchestration module."""

import sys

import app.agent as _implementation

sys.modules[__name__] = _implementation
