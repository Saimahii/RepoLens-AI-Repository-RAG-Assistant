"""Architecture Explainer agent: explains structure, modules, and data/request flow."""

from app.agents.base_agent import BaseAgent
from app.prompts.templates import ARCHITECT_INSTRUCTIONS


class ArchitectAgent(BaseAgent):
    """Triggered by architecture keywords: architecture, flow, structure."""

    name: str = "architect"
    display_name: str = "Architecture Explainer"
    instructions: str = ARCHITECT_INSTRUCTIONS
