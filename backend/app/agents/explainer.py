"""Code Explainer agent: explains functions, classes, logic flow, and APIs."""

from app.agents.base_agent import BaseAgent
from app.prompts.templates import EXPLAINER_INSTRUCTIONS


class ExplainerAgent(BaseAgent):
    """Default agent when no specialized debugging/bug/architecture keyword matches."""

    name: str = "explainer"
    display_name: str = "Code Explainer"
    instructions: str = EXPLAINER_INSTRUCTIONS
