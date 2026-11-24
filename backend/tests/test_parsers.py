"""Unit tests for file scanner, Python AST parser, JS/TS/TSX Tree-sitter parser, and fallback parser."""

from pathlib import Path

import pytest

from app.parsers.fallback_parser import parse_fallback
from app.parsers.js_parser import parse_js
from app.parsers.models import ParseError
from app.parsers.python_parser import parse_python
from app.utils.file_utils import MAX_FILE_SIZE_BYTES, scan_repository_files


# ── File scanner tests ──────────────────────────────────────────────────

def test_scanner_respects_ignore_dirs_extensions_size_and_binary(tmp_path: Path) -> None:
    # Supported files that SHOULD be scanned
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("def hi():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app" / "ui.tsx").write_text("export const App = () => <div />;\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\nHello\n", encoding="utf-8")

    # Ignored directories that MUST be skipped
    for ignored in ("node_modules", "dist", "build", ".git", "venv", ".venv", "__pycache__"):
        folder = tmp_path / ignored
        folder.mkdir()
        (folder / "skip.py").write_text("x = 1\n", encoding="utf-8")

    # Unsupported extension -> skipped
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

    # File above 1 MB -> skipped
    (tmp_path / "huge.py").write_text("a = 1\n" * ((MAX_FILE_SIZE_BYTES // 6) + 100), encoding="utf-8")

    # Binary file (null bytes) -> skipped
    (tmp_path / "binary.py").write_bytes(b"def f():\x00\x01\x02")

    # Invalid UTF-8 bytes -> skipped
    (tmp_path / "bad_encoding.py").write_bytes(b"\xff\xfe\xfd")

    scanned = scan_repository_files(tmp_path)
    rel_paths = [f.rel_path for f in scanned]

    assert rel_paths == ["README.md", "app/main.py", "app/ui.tsx"]
    assert [f.language for f in scanned] == ["markdown", "python", "tsx"]


# ── Python AST parser tests ─────────────────────────────────────────────

def test_python_parser_extracts_imports_classes_methods_decorators_and_routes() -> None:
    code = '''import os
from fastapi import APIRouter

router = APIRouter()


class AuthService:
    """Handles user authentication."""

    def validate_user(self, email: str) -> bool:
        """Return True if valid."""
        return bool(email)


@router.post("/auth/login")
async def login(email: str) -> dict:
    """Authenticate a user."""
    return {"email": email}
'''
    parsed = parse_python("app/api/auth.py", code)

    assert parsed.language == "python"
    assert not parsed.used_fallback
    assert "import os" in parsed.imports
    assert "from fastapi import APIRouter" in parsed.imports

    by_name = {s.symbol_name: s for s in parsed.symbols}
    assert set(by_name.keys()) == {"AuthService", "validate_user", "login"}

    assert by_name["AuthService"].symbol_type == "class"
    assert by_name["AuthService"].docstring == "Handles user authentication."
    assert by_name["AuthService"].start_line == 7
    assert by_name["AuthService"].end_line == 12

    assert by_name["validate_user"].symbol_type == "method"
    assert by_name["validate_user"].parent == "AuthService"
    assert by_name["validate_user"].docstring == "Return True if valid."
    assert by_name["validate_user"].start_line == 10
    assert by_name["validate_user"].end_line == 12

    # Decorator line (15) must be included in start_line
    assert by_name["login"].symbol_type == "function"
    assert by_name["login"].start_line == 15
    assert by_name["login"].end_line == 18
    assert by_name["login"].decorators == ["@router.post('/auth/login')"]
    assert by_name["login"].routes == ["POST /auth/login"]


def test_python_parser_raises_parse_error_on_syntax_error() -> None:
    broken = "def broken(:\n    pass\n"
    with pytest.raises(ParseError):
        parse_python("broken.py", broken)


# ── JS / TS / TSX Tree-sitter parser tests ──────────────────────────────

def test_js_parser_extracts_imports_functions_classes_and_routes() -> None:
    code = '''import express from 'express';
const helper = require('./helper');

export function greet(name) {
  return `Hello ${name}`;
}

export const add = (a, b) => {
  return a + b;
};

class UserRepo {
  findById(id) {
    return id;
  }
}

app.get('/users', (req, res) => {
  res.json([]);
});
'''
    parsed = parse_js("src/server.js", code, "javascript")

    assert len(parsed.imports) == 2
    by_name = {s.symbol_name: s for s in parsed.symbols}

    assert "greet" in by_name
    assert by_name["greet"].symbol_type == "function"
    assert by_name["greet"].start_line == 4
    assert by_name["greet"].end_line == 6

    assert "add" in by_name
    assert by_name["add"].symbol_type == "function"

    assert "UserRepo" in by_name
    assert by_name["UserRepo"].symbol_type == "class"

    assert "findById" in by_name
    assert by_name["findById"].symbol_type == "method"
    assert by_name["findById"].parent == "UserRepo"

    assert "GET /users" in by_name
    assert by_name["GET /users"].routes == ["GET /users"]


def test_tsx_parser_detects_react_components_and_typescript_functions() -> None:
    code = '''import React from 'react';

interface Props {
  title: string;
}

export const RepoCard = ({ title }: Props) => {
  return <div className="card">{title}</div>;
};

export function formatTitle(raw: string): string {
  return raw.trim();
}
'''
    parsed = parse_js("src/components/RepoCard.tsx", code, "tsx")
    by_name = {s.symbol_name: s for s in parsed.symbols}

    assert "RepoCard" in by_name
    assert by_name["RepoCard"].is_react_component is True
    assert by_name["RepoCard"].start_line == 7
    assert by_name["RepoCard"].end_line == 9

    assert "formatTitle" in by_name
    assert by_name["formatTitle"].is_react_component is False


def test_js_parser_raises_parse_error_on_severely_broken_syntax() -> None:
    broken = "function ((( { {{{ >>>"
    with pytest.raises(ParseError):
        parse_js("broken.js", broken, "javascript")


# ── Fallback parser tests ───────────────────────────────────────────────

def test_fallback_parser_windows_with_overlap_and_extracts_go_imports() -> None:
    header = ['package main', 'import "fmt"', 'import "net/http"']
    body = [f"// line {i}" for i in range(4, 151)]
    content = "\n".join(header + body)

    parsed = parse_fallback("cmd/server.go", "go", content, window_lines=60, overlap_lines=10)

    assert parsed.used_fallback is True
    assert 'import "fmt"' in parsed.imports
    assert 'import "net/http"' in parsed.imports
    assert len(parsed.symbols) == 3

    # Window 1: 1..60, Window 2: 51..110 (10 lines overlap), Window 3: 101..150
    assert (parsed.symbols[0].start_line, parsed.symbols[0].end_line) == (1, 60)
    assert (parsed.symbols[1].start_line, parsed.symbols[1].end_line) == (51, 110)
    assert (parsed.symbols[2].start_line, parsed.symbols[2].end_line) == (101, 150)
    assert all(s.symbol_type == "module" for s in parsed.symbols)


def test_python_parser_handles_flask_route_and_nested_class() -> None:
    code = '''from flask import Flask
app = Flask(__name__)

class Outer:
    class Inner:
        def ping(self) -> str:
            return "pong"

@app.route("/health", methods=["GET"])
def health():
    return "ok"
'''
    parsed = parse_python("app.py", code)
    by_name = {s.symbol_name: s for s in parsed.symbols}
    assert by_name["Inner"].parent == "Outer"
    assert by_name["ping"].parent == "Inner"
    assert by_name["health"].routes == ["ROUTE /health"]


def test_ts_parser_handles_class_field_arrow_methods() -> None:
    code = '''export class ApiClient {
  fetchUser = async (id: string) => {
    return id;
  };
}
'''
    parsed = parse_js("src/client.ts", code, "typescript")
    by_name = {s.symbol_name: s for s in parsed.symbols}
    assert "ApiClient" in by_name
    assert by_name["fetchUser"].symbol_type == "method"
    assert by_name["fetchUser"].parent == "ApiClient"


def test_fallback_parser_extracts_java_imports() -> None:
    java_code = "package com.demo;\nimport java.util.List;\nimport java.io.File;\npublic class Main {}\n"
    parsed = parse_fallback("src/Main.java", "java", java_code)
    assert parsed.imports == ["import java.util.List;", "import java.io.File;"]
    assert len(parsed.symbols) == 1
