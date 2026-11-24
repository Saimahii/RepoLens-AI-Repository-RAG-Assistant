"""Unit tests for the nested file tree builder and path-traversal safety checks."""

from pathlib import Path

import pytest

from app.services.file_service import (
    FilePathTraversalError,
    build_file_tree,
    resolve_safe_repo_path,
)


def test_build_file_tree_nests_and_sorts_folders_before_files() -> None:
    entries = [
        ("README.md", "markdown"),
        ("app/api/chat.py", "python"),
        ("app/api/auth.py", "python"),
        ("app/main.py", "python"),
        ("src/index.js", "javascript"),
    ]

    tree = build_file_tree(entries)

    # Top-level: folders ("app", "src") sorted before root file ("README.md")
    assert [(n.name, n.type) for n in tree] == [
        ("app", "folder"),
        ("src", "folder"),
        ("README.md", "file"),
    ]
    assert tree[2].language == "markdown"
    assert tree[2].children == []

    app_node = tree[0]
    assert [(n.name, n.type) for n in app_node.children] == [
        ("api", "folder"),
        ("main.py", "file"),
    ]
    api_node = app_node.children[0]
    assert [(n.name, n.path, n.language) for n in api_node.children] == [
        ("auth.py", "app/api/auth.py", "python"),
        ("chat.py", "app/api/chat.py", "python"),
    ]


def test_resolve_safe_repo_path_accepts_valid_relative_files(tmp_path: Path) -> None:
    target = tmp_path / "app" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('ok')\n", encoding="utf-8")

    resolved, rel = resolve_safe_repo_path(tmp_path, "app/main.py")
    assert resolved == target.resolve()
    assert rel == "app/main.py"

    # Backslashes from Windows clients are normalized safely
    resolved_win, rel_win = resolve_safe_repo_path(tmp_path, r"app\main.py")
    assert resolved_win == target.resolve()
    assert rel_win == "app/main.py"


@pytest.mark.parametrize(
    "bad_path",
    [
        "",
        "   ",
        "../secret.txt",
        "app/../../.env",
        r"..\..\Windows\win.ini",
        "/etc/passwd",
        r"C:\Users\secret.txt",
        r"\\server\share\file.py",
        "app/main.py\x00.txt",
        ".git/config",
        "node_modules/pkg/index.js",
        "venv/pyvenv.cfg",
        "__pycache__/main.pyc",
        "frontend/node_modules/react/index.js",
        "sub/.git/HEAD",
    ],
)
def test_resolve_safe_repo_path_blocks_traversal_and_internal_dirs(
    tmp_path: Path, bad_path: str
) -> None:
    with pytest.raises(FilePathTraversalError):
        resolve_safe_repo_path(tmp_path, bad_path)
