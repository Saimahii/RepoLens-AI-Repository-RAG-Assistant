"""System instructions, per-agent instructions, and RAG prompt builder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from app.rag.retriever import RetrievedChunk

SYSTEM_PROMPT: str = """You are RepoLens, an AI assistant that helps developers understand, debug, and review code repositories.

Follow these strict rules in every answer:
1. Respond in clear, well-structured Markdown.
2. Ground every explanation in the retrieved code chunks provided below.
3. Always cite exact file paths and line numbers from the retrieved chunks (for example: `src/auth/jwt.py` lines 15-32).
4. Include short, relevant code snippets from the retrieved chunks when helpful.
5. NEVER invent file paths, symbol names, or line numbers that do not appear in the retrieved chunks.
6. If the retrieved chunks do not contain enough information to answer the question, state that honestly and explain what is missing.
"""

EXPLAINER_INSTRUCTIONS: str = """Role: Code Explainer Agent.
Focus on explaining how functions, classes, methods, logic flows, and APIs work in clear, developer-friendly steps. Walk through inputs, core behavior, and return values while referencing the exact files and line ranges."""

DEBUGGER_INSTRUCTIONS: str = """Role: Debugging Agent.
Focus on diagnosing errors, exceptions, stack traces, and failing logic. Identify the likely root cause in the retrieved code, explain why it happens, and propose concrete, minimal fixes with exact file paths and line numbers."""

BUG_FINDER_INSTRUCTIONS: str = """Role: Bug Finder Agent.
Focus on spotting potential bugs, risky patterns, unhandled edge cases, security issues, and anti-patterns in the retrieved code. For each issue found, cite the file and line range, explain the risk, and suggest how to harden it."""

ARCHITECT_INSTRUCTIONS: str = """Role: Architecture Explainer Agent.
Focus on explaining the repository's high-level structure, module responsibilities, key components, dependencies, and end-to-end request or data flow. Connect the big picture to concrete files and symbols."""

MAX_HISTORY_MSG_CHARS: int = 1200


def build_system_instruction(agent_display_name: str, agent_instructions: str) -> str:
    """Combine the global RepoLens rules with the selected agent's behavior."""
    return f"{SYSTEM_PROMPT}\n## Selected Agent: {agent_display_name}\n{agent_instructions}\n"


def _format_chunk(index: int, chunk: RetrievedChunk) -> str:
    """Format one retrieved code chunk with metadata and fenced code block."""
    header = f"[{index}] `{chunk.file_path}` (lines {chunk.start_line}-{chunk.end_line}) | language: {chunk.language} | {chunk.symbol_type}"
    if chunk.symbol_name:
        header += f" `{chunk.symbol_name}`"
    if chunk.parent:
        header += f" (in `{chunk.parent}`)"

    parts = [header]
    if chunk.imports:
        first_imports = "\n".join(chunk.imports.splitlines()[:10])
        parts.append(f"Imports:\n{first_imports}")
    parts.append(f"```{chunk.language}\n{chunk.content}\n```")
    return "\n".join(parts)


def _format_history(history: Sequence[dict[str, str]]) -> str:
    """Format the recent conversation turns (last 6 messages) for conversational memory."""
    if not history:
        return "No previous messages in this session."

    lines: list[str] = []
    for item in history:
        role_label = "User" if item.get("role") == "user" else "Assistant"
        text = (item.get("content") or "").strip()
        if len(text) > MAX_HISTORY_MSG_CHARS:
            text = text[: MAX_HISTORY_MSG_CHARS - 3] + "..."
        lines.append(f"{role_label}: {text}")
    return "\n\n".join(lines)


def build_rag_prompt(
    repo_context: str,
    code_chunks: Sequence[RetrievedChunk],
    summary_chunks: Sequence[RetrievedChunk],
    history: Sequence[dict[str, str]],
    question: str,
) -> str:
    """Assemble the complete RAG prompt sent to Gemini."""
    sections: list[str] = [f"## Repository Context\n{repo_context.strip()}"]

    if summary_chunks:
        summary_text = "\n\n".join(chunk.content.strip() for chunk in summary_chunks if chunk.content.strip())
        if summary_text:
            sections.append(f"## Repository & Architecture Summaries\n{summary_text}")

    if code_chunks:
        formatted_chunks = "\n\n".join(_format_chunk(i, chunk) for i, chunk in enumerate(code_chunks, start=1))
        sections.append(f"## Retrieved Code Chunks\n{formatted_chunks}")
    else:
        sections.append("## Retrieved Code Chunks\nNone found.")

    sections.append(f"## Recent Conversation History\n{_format_history(history)}")
    sections.append(f"## Current User Question\n{question.strip()}")

    return "\n\n".join(sections)
