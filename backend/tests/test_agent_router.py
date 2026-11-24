"""Unit tests for the keyword-based agent router."""

import pytest

from app.agents.router import route_agent


@pytest.mark.parametrize(
    ("question", "expected_agent"),
    [
        # Bug Finder: bug, issue, problem
        ("Find potential bugs in authentication", "bugfinder"),
        ("Is there a bug in jwt.py?", "bugfinder"),
        ("Check this module for any security issue", "bugfinder"),
        ("What is the problem with this loop?", "bugfinder"),
        # Debugger: debug, error, fix (notice "debug" must NOT trigger "bug"!)
        ("Debug this login crash", "debugger"),
        ("Help me debug the token validation", "debugger"),
        ("Why am I getting a TypeError error here?", "debugger"),
        ("How do I fix the 401 unauthorized response?", "debugger"),
        # Architecture Explainer: architecture, flow, structure
        ("Explain the main architecture of this repo", "architect"),
        ("Walk me through the authentication flow", "architect"),
        ("Describe the folder structure and module layout", "architect"),
        # Default: Code Explainer
        ("How does generate_token work?", "explainer"),
        ("Summarize what TimestampSigner does", "explainer"),
        ("Where is the secret key loaded?", "explainer"),
        # Precedence check: bug/issue/problem wins over debug/error/fix
        ("Debug this bug in the parser", "bugfinder"),
        # False-positive guardrails: "overflow" must NOT trigger "flow"
        ("How does stack overflow prevention work?", "explainer"),
        ("HOW DOES THE ARCHITECTURE WORK?!", "architect"),
    ],
)
def test_route_agent_keywords(question: str, expected_agent: str) -> None:
    agent = route_agent(question)
    assert agent.name == expected_agent
