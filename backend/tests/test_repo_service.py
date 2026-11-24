"""Tests for GitHub URL validation and git error classification (no network, no MySQL)."""

import pytest

from app.services.repo_service import (
    CloneFailedError,
    InvalidRepoUrlError,
    RepoNotFoundError,
    classify_git_error,
    parse_github_url,
)
from app.utils.helpers import safe_folder_name


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/octocat/Hello-World",
        "https://github.com/octocat/Hello-World/",
        "https://github.com/octocat/Hello-World.git",
        "https://www.github.com/octocat/Hello-World",
        "  https://github.com/octocat/Hello-World  ",
    ],
)
def test_valid_urls_are_normalized(url: str) -> None:
    owner, repo, normalized = parse_github_url(url)
    assert (owner, repo) == ("octocat", "Hello-World")
    assert normalized == "https://github.com/octocat/Hello-World"


def test_repo_names_with_dots_and_underscores() -> None:
    _, repo, normalized = parse_github_url("https://github.com/vercel/next.js")
    assert repo == "next.js"
    assert normalized == "https://github.com/vercel/next.js"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "http://github.com/octocat/Hello-World",          # must be https
        "https://gitlab.com/octocat/Hello-World",         # not GitHub
        "https://github.com/octocat",                      # missing repo
        "https://github.com/octocat/Hello-World/tree/main",  # extra path
        "https://github.com/-bad/repo",                    # invalid owner
        "https://github.com/octocat/..",                   # path trick
        "https://github.com/octocat/repo;rm -rf",          # shell characters
        "https://github.com/octocat/Hello-World?x=1",      # query string
    ],
)
def test_invalid_urls_are_rejected(url: str) -> None:
    with pytest.raises(InvalidRepoUrlError):
        parse_github_url(url)


def test_private_or_missing_repo_maps_to_404() -> None:
    stderr = "fatal: could not read Username for 'https://github.com': terminal prompts disabled"
    error = classify_git_error(stderr)
    assert isinstance(error, RepoNotFoundError)
    assert error.status_code == 404


def test_unknown_git_error_maps_to_502() -> None:
    error = classify_git_error("warning: something\nfatal: disk full\n")
    assert isinstance(error, CloneFailedError)
    assert error.status_code == 502
    assert "disk full" in error.message


def test_safe_folder_name() -> None:
    assert safe_folder_name(3, "octocat", "Hello-World") == "3_octocat_Hello-World"
    assert safe_folder_name(1, "a", "b c") == "1_a_b-c"
