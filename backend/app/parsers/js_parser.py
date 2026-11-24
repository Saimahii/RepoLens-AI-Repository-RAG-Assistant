"""JavaScript, TypeScript, and TSX parser built on Tree-sitter."""

from functools import lru_cache
import re

from tree_sitter import Language, Node, Parser
import tree_sitter_javascript
import tree_sitter_typescript

from app.parsers.models import ParsedFile, ParsedSymbol, ParseError

# HTTP route methods commonly used with Express / Fastify / Hono routers
_ROUTE_METHODS: frozenset[str] = frozenset({"get", "post", "put", "delete", "patch", "options", "head", "all", "use"})
_JSX_NODE_TYPES: frozenset[str] = frozenset({"jsx_element", "jsx_self_closing_element", "jsx_fragment"})
_PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")


@lru_cache(maxsize=4)
def _get_language(language: str) -> Language:
    """Load and cache the Tree-sitter grammar for js, ts, or tsx."""
    if language == "javascript":
        return Language(tree_sitter_javascript.language())
    if language == "typescript":
        return Language(tree_sitter_typescript.language_typescript())
    if language == "tsx":
        return Language(tree_sitter_typescript.language_tsx())
    raise ParseError(f"Unsupported JS/TS language: {language}")


def _node_text(node: Node, source_bytes: bytes) -> str:
    """Slice a Tree-sitter node's raw text out of the UTF-8 source bytes."""
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _contains_jsx(node: Node) -> bool:
    """Return True if a function/arrow body contains JSX (indicates a React component)."""
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in _JSX_NODE_TYPES:
            return True
        stack.extend(current.children)
    return False


def _is_react_component(name: str, node: Node) -> bool:
    """Heuristic: PascalCase name + JSX inside the body."""
    return bool(_PASCAL_CASE_RE.match(name)) and _contains_jsx(node)


def _extract_leading_comment(node: Node, source_bytes: bytes) -> str | None:
    """Return the comment immediately above a symbol, if present."""
    prev = node.prev_sibling
    if prev is not None and prev.type == "comment":
        # Only attach if the comment sits right above the symbol (no blank gap)
        if node.start_point[0] - prev.end_point[0] <= 1:
            return _node_text(prev, source_bytes).strip()
    return None


def _extract_class_symbols(
    class_node: Node,
    outer_node: Node,
    source_bytes: bytes,
    fallback_name: str | None = None,
) -> list[ParsedSymbol]:
    """Extract a JS/TS class and all its methods (including class-field arrow functions)."""
    name_node = class_node.child_by_field_name("name")
    class_name = _node_text(name_node, source_bytes) if name_node else (fallback_name or "AnonymousClass")

    symbols: list[ParsedSymbol] = [
        ParsedSymbol(
            symbol_name=class_name,
            symbol_type="class",
            start_line=outer_node.start_point[0] + 1,
            end_line=outer_node.end_point[0] + 1,
            parent=None,
            docstring=_extract_leading_comment(outer_node, source_bytes),
        )
    ]

    body = class_node.child_by_field_name("body")
    if body is None:
        return symbols

    for member in body.children:
        if member.type == "method_definition":
            m_name_node = member.child_by_field_name("name")
            m_name = _node_text(m_name_node, source_bytes) if m_name_node else "anonymous"
            symbols.append(
                ParsedSymbol(
                    symbol_name=m_name,
                    symbol_type="method",
                    start_line=member.start_point[0] + 1,
                    end_line=member.end_point[0] + 1,
                    parent=class_name,
                    docstring=_extract_leading_comment(member, source_bytes),
                )
            )
        elif member.type in {"public_field_definition", "field_definition"}:
            value_node = member.child_by_field_name("value")
            if value_node is not None and value_node.type in {"arrow_function", "function_expression"}:
                m_name_node = member.child_by_field_name("name")
                m_name = _node_text(m_name_node, source_bytes) if m_name_node else "anonymous"
                symbols.append(
                    ParsedSymbol(
                        symbol_name=m_name,
                        symbol_type="method",
                        start_line=member.start_point[0] + 1,
                        end_line=member.end_point[0] + 1,
                        parent=class_name,
                        docstring=_extract_leading_comment(member, source_bytes),
                    )
                )

    return symbols


def _try_extract_route(expr_stmt: Node, source_bytes: bytes) -> ParsedSymbol | None:
    """Detect Express/Router calls such as `app.get('/users', handler)`."""
    if not expr_stmt.named_children:
        return None
    call = expr_stmt.named_children[0]
    if call.type != "call_expression":
        return None

    callee = call.child_by_field_name("function")
    if callee is None or callee.type != "member_expression":
        return None

    prop = callee.child_by_field_name("property")
    obj = callee.child_by_field_name("object")
    if prop is None or obj is None:
        return None

    method_name = _node_text(prop, source_bytes).lower()
    obj_name = _node_text(obj, source_bytes).lower()
    if method_name not in _ROUTE_METHODS:
        return None

    # Require a router-like object name or a string path first argument to avoid false positives
    args = call.child_by_field_name("arguments")
    route_path = ""
    if args is not None and args.named_children:
        first_arg = args.named_children[0]
        if first_arg.type in {"string", "template_string"}:
            route_path = _node_text(first_arg, source_bytes).strip("'\"`")

    is_router_obj = any(tok in obj_name for tok in ("app", "router", "route", "server", "fastify"))
    if not route_path.startswith("/") and not (is_router_obj and route_path):
        return None

    route_label = f"{method_name.upper()} {route_path}".strip()
    return ParsedSymbol(
        symbol_name=route_label,
        symbol_type="function",
        start_line=expr_stmt.start_point[0] + 1,
        end_line=expr_stmt.end_point[0] + 1,
        parent=None,
        docstring=_extract_leading_comment(expr_stmt, source_bytes),
        routes=[route_label],
    )


def _handle_variable_declaration(
    decl_node: Node,
    outer_node: Node,
    source_bytes: bytes,
    imports: list[str],
    symbols: list[ParsedSymbol],
) -> None:
    """Inspect `const/let/var` declarations for require(), arrow functions, function or class expressions."""
    for child in decl_node.named_children:
        if child.type != "variable_declarator":
            continue
        name_node = child.child_by_field_name("name")
        value_node = child.child_by_field_name("value")
        if name_node is None or value_node is None:
            continue

        var_name = _node_text(name_node, source_bytes)

        # CommonJS require: const express = require('express')
        if value_node.type == "call_expression":
            fn = value_node.child_by_field_name("function")
            if fn is not None and _node_text(fn, source_bytes) == "require":
                imports.append(_node_text(outer_node, source_bytes).strip())
                continue

        if value_node.type in {"arrow_function", "function_expression", "generator_function"}:
            symbols.append(
                ParsedSymbol(
                    symbol_name=var_name,
                    symbol_type="function",
                    start_line=outer_node.start_point[0] + 1,
                    end_line=outer_node.end_point[0] + 1,
                    parent=None,
                    docstring=_extract_leading_comment(outer_node, source_bytes),
                    is_react_component=_is_react_component(var_name, value_node),
                )
            )
        elif value_node.type == "class":
            symbols.extend(_extract_class_symbols(value_node, outer_node, source_bytes, fallback_name=var_name))


def _process_statement(
    stmt: Node,
    outer_node: Node,
    source_bytes: bytes,
    imports: list[str],
    symbols: list[ParsedSymbol],
) -> None:
    """Extract imports and top-level symbols from a single top-level AST statement."""
    node_type = stmt.type

    if node_type == "import_statement":
        imports.append(_node_text(stmt, source_bytes).strip())
        return

    if node_type == "export_statement":
        decl = stmt.child_by_field_name("declaration")
        if decl is not None:
            _process_statement(decl, outer_node=stmt, source_bytes=source_bytes, imports=imports, symbols=symbols)
            return
        # Handle `export default function() {}` or `export default () => {}`
        value = stmt.child_by_field_name("value")
        if value is not None and value.type in {"arrow_function", "function_expression"}:
            symbols.append(
                ParsedSymbol(
                    symbol_name="default",
                    symbol_type="function",
                    start_line=stmt.start_point[0] + 1,
                    end_line=stmt.end_point[0] + 1,
                    parent=None,
                    docstring=_extract_leading_comment(stmt, source_bytes),
                    is_react_component=_contains_jsx(value),
                )
            )
        return

    if node_type in {"function_declaration", "generator_function_declaration"}:
        name_node = stmt.child_by_field_name("name")
        fn_name = _node_text(name_node, source_bytes) if name_node else "default"
        symbols.append(
            ParsedSymbol(
                symbol_name=fn_name,
                symbol_type="function",
                start_line=outer_node.start_point[0] + 1,
                end_line=outer_node.end_point[0] + 1,
                parent=None,
                docstring=_extract_leading_comment(outer_node, source_bytes),
                is_react_component=_is_react_component(fn_name, stmt),
            )
        )
        return

    if node_type in {"class_declaration", "abstract_class_declaration"}:
        symbols.extend(_extract_class_symbols(stmt, outer_node, source_bytes))
        return

    if node_type in {"lexical_declaration", "variable_declaration"}:
        _handle_variable_declaration(stmt, outer_node, source_bytes, imports, symbols)
        return

    if node_type == "expression_statement":
        route_sym = _try_extract_route(stmt, source_bytes)
        if route_sym is not None:
            symbols.append(route_sym)


def parse_js(file_path: str, content: str, language: str) -> ParsedFile:
    """Parse a .js, .ts, or .tsx file with Tree-sitter.

    Raises ParseError if Tree-sitter fails or produces an unusable syntax tree,
    allowing the chunker to fall back to line-window chunking.
    """
    ts_language = _get_language(language)
    source_bytes = content.encode("utf-8")

    try:
        parser = Parser(ts_language)
        tree = parser.parse(source_bytes)
    except Exception as error:  # tree-sitter raises RuntimeError/ValueError on internal failures
        raise ParseError(f"Tree-sitter failed for {file_path}: {error}") from error

    root = tree.root_node
    imports: list[str] = []
    symbols: list[ParsedSymbol] = []

    for child in root.children:
        _process_statement(child, outer_node=child, source_bytes=source_bytes, imports=imports, symbols=symbols)

    # If the file has syntax errors and we couldn't extract any symbols, fall back cleanly
    if root.has_error and not symbols:
        raise ParseError(f"Tree-sitter reported syntax errors with no symbols in {file_path}")

    return ParsedFile(
        file_path=file_path,
        language=language,
        imports=imports,
        symbols=symbols,
        used_fallback=False,
    )
