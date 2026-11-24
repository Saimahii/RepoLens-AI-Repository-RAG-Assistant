"""Debugging agent: analyzes errors, stack traces, and proposes fixes."""

from app.agents.base_agent import BaseAgent
from app.prompts.templates import DEBUGGER_INSTRUCTIONS


class DebuggerAgent(BaseAgent):
    """Triggered by debugging keywords: debug, error, fix."""

    name: str = "debugger"
    display_name: str = "Debugger"
    instructions: str = DEBUGGER_INSTRUCTIONS
