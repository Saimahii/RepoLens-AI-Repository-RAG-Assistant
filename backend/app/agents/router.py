"""Simple keyword-based agent router matching AGENTS.md rules exactly.

Routing order:
1. "bug", "issue", "problem"       -> Bug Finder Agent ("bugfinder")
2. "debug", "error", "fix"         -> Debugging Agent ("debugger")
3. "architecture", "flow", "structure" -> Architecture Explainer Agent ("architect")
4. Everything else                 -> Code Explainer Agent ("explainer")
"""

import re

from app.agents.architect import ArchitectAgent
from app.agents.base_agent import BaseAgent
from app.agents.bug_finder import BugFinderAgent
from app.agents.debugger import DebuggerAgent
from app.agents.explainer import ExplainerAgent

# Word-boundary regexes prevent "debug" from accidentally matching "bug"
_BUG_FINDER_RE = re.compile(r"\b(bugs?|issues?|problems?)\b", re.IGNORECASE)
_DEBUGGER_RE = re.compile(r"\b(debug\w*|errors?|fix\w*)\b", re.IGNORECASE)
_ARCHITECT_RE = re.compile(r"\b(architecture|flows?|structures?)\b", re.IGNORECASE)

_BUG_FINDER = BugFinderAgent()
_DEBUGGER = DebuggerAgent()
_ARCHITECT = ArchitectAgent()
_EXPLAINER = ExplainerAgent()


def route_agent(question: str) -> BaseAgent:
    """Select one of the 4 RepoLens agents based on keywords in the question."""
    text = question.strip()
    if _BUG_FINDER_RE.search(text):
        return _BUG_FINDER
    if _DEBUGGER_RE.search(text):
        return _DEBUGGER
    if _ARCHITECT_RE.search(text):
        return _ARCHITECT
    return _EXPLAINER
