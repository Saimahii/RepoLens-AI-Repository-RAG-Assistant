"""Python AST parser: extracts classes, functions, methods, imports, docstrings, decorators & routes."""

import ast

from app.parsers.models import ParsedFile, ParsedSymbol, ParseError

# Common HTTP/routing decorator method names in FastAPI and Flask
_ROUTE_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "delete", "patch", "options", "head", "route", "api_route", "websocket"}
)


def _format_import(node: ast.Import | ast.ImportFrom) -> str:
    """Turn an AST import node into a readable one-line string."""
    try:
        return ast.unparse(node)
    except (ValueError, TypeError):
        return ""


def _extract_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> tuple[list[str], list[str]]:
    """Return (decorator_texts, detected_routes) for a function or class node."""
    decorators: list[str] = []
    routes: list[str] = []

    for dec in node.decorator_list:
        try:
            dec_text = f"@{ast.unparse(dec)}"
        except (ValueError, TypeError):
            dec_text = "@<decorator>"
        decorators.append(dec_text)

        # Detect FastAPI / Flask route decorators like @router.post("/upload") or @app.route("/login")
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            method_name = dec.func.attr.lower()
            if method_name in _ROUTE_METHODS:
                route_path = ""
                if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                    route_path = dec.args[0].value
                else:
                    for kw in dec.keywords:
                        if kw.arg in {"path", "rule"} and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            route_path = kw.value.value
                            break
                verb = method_name.upper()
                routes.append(f"{verb} {route_path}".strip())

    return decorators, routes


def _symbol_start_line(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> int:
    """Start line including any decorators directly attached to the symbol."""
    if node.decorator_list:
        return min(dec.lineno for dec in node.decorator_list)
    return node.lineno


def _extract_class_symbols(class_node: ast.ClassDef, parent_name: str | None = None) -> list[ParsedSymbol]:
    """Extract a class symbol plus all methods (and nested classes) inside it."""
    decorators, routes = _extract_decorators(class_node)
    symbols: list[ParsedSymbol] = [
        ParsedSymbol(
            symbol_name=class_node.name,
            symbol_type="class",
            start_line=_symbol_start_line(class_node),
            end_line=class_node.end_lineno or class_node.lineno,
            parent=parent_name,
            docstring=ast.get_docstring(class_node),
            decorators=decorators,
            routes=routes,
        )
    ]

    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m_decs, m_routes = _extract_decorators(child)
            symbols.append(
                ParsedSymbol(
                    symbol_name=child.name,
                    symbol_type="method",
                    start_line=_symbol_start_line(child),
                    end_line=child.end_lineno or child.lineno,
                    parent=class_node.name,
                    docstring=ast.get_docstring(child),
                    decorators=m_decs,
                    routes=m_routes,
                )
            )
        elif isinstance(child, ast.ClassDef):
            symbols.extend(_extract_class_symbols(child, parent_name=class_node.name))

    return symbols


def parse_python(file_path: str, content: str) -> ParsedFile:
    """Parse a Python source file using the standard library `ast` module.

    Raises ParseError if the file has syntax errors so the caller can fall back
    to line-window chunking.
    """
    try:
        tree = ast.parse(content, filename=file_path)
    except (SyntaxError, ValueError) as error:
        raise ParseError(f"Python AST parse failed for {file_path}: {error}") from error

    imports: list[str] = []
    symbols: list[ParsedSymbol] = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            formatted = _format_import(node)
            if formatted:
                imports.append(formatted)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators, routes = _extract_decorators(node)
            symbols.append(
                ParsedSymbol(
                    symbol_name=node.name,
                    symbol_type="function",
                    start_line=_symbol_start_line(node),
                    end_line=node.end_lineno or node.lineno,
                    parent=None,
                    docstring=ast.get_docstring(node),
                    decorators=decorators,
                    routes=routes,
                )
            )
        elif isinstance(node, ast.ClassDef):
            symbols.extend(_extract_class_symbols(node))

    return ParsedFile(
        file_path=file_path,
        language="python",
        imports=imports,
        symbols=symbols,
        used_fallback=False,
    )
