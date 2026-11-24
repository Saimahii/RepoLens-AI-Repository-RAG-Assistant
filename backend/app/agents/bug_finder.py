"""Bug Finder agent: detects risky patterns, edge cases, and potential bugs."""

from app.agents.base_agent import BaseAgent
from app.prompts.templates import BUG_FINDER_INSTRUCTIONS


class BugFinderAgent(BaseAgent):
    """Triggered by bug-finding keywords: bug, issue, problem."""

    name: str = "bugfinder"
    display_name: str = "Bug Finder"
    instructions: str = BUG_FINDER_INSTRUCTIONS
