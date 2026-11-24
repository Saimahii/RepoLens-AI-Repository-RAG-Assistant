"""Base class for all prompt-based RepoLens agents."""

from typing import Sequence

from app.prompts.templates import build_rag_prompt, build_system_instruction
from app.rag.retriever import RetrievedChunk
from app.services.gemini_service import generate_text


class BaseAgent:
    """Simple prompt-based agent that delegates generation to Gemini."""

    name: str = "explainer"
    display_name: str = "Code Explainer"
    instructions: str = ""
    temperature: float = 0.2

    def build_messages(
        self,
        repo_context: str,
        code_chunks: Sequence[RetrievedChunk],
        summary_chunks: Sequence[RetrievedChunk],
        history: Sequence[dict[str, str]],
        question: str,
    ) -> tuple[str, str]:
        """Return (system_instruction, user_prompt) for this agent."""
        system_instruction = build_system_instruction(self.display_name, self.instructions)
        user_prompt = build_rag_prompt(
            repo_context=repo_context,
            code_chunks=code_chunks,
            summary_chunks=summary_chunks,
            history=history,
            question=question,
        )
        return system_instruction, user_prompt

    def run(
        self,
        repo_context: str,
        code_chunks: Sequence[RetrievedChunk],
        summary_chunks: Sequence[RetrievedChunk],
        history: Sequence[dict[str, str]],
        question: str,
    ) -> str:
        """Build the agent prompt and call Gemini."""
        system_instruction, prompt = self.build_messages(
            repo_context=repo_context,
            code_chunks=code_chunks,
            summary_chunks=summary_chunks,
            history=history,
            question=question,
        )
        return generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=self.temperature,
        )
