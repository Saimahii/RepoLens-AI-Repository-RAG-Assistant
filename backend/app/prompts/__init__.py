"""Prompt templates and RAG prompt assembly."""

from app.prompts.templates import (
    ARCHITECT_INSTRUCTIONS,
    BUG_FINDER_INSTRUCTIONS,
    DEBUGGER_INSTRUCTIONS,
    EXPLAINER_INSTRUCTIONS,
    SYSTEM_PROMPT,
    build_rag_prompt,
    build_system_instruction,
)

__all__ = [
    "ARCHITECT_INSTRUCTIONS",
    "BUG_FINDER_INSTRUCTIONS",
    "DEBUGGER_INSTRUCTIONS",
    "EXPLAINER_INSTRUCTIONS",
    "SYSTEM_PROMPT",
    "build_rag_prompt",
    "build_system_instruction",
]
