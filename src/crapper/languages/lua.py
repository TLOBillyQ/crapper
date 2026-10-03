"""Lua functions and cyclomatic complexity.

Decision points: `if`, `elseif`, `while`, `repeat`, both `for` forms, and each
`and` / `or`. Entries are `function` declarations and function expressions
assigned to a name (`local f = function`, `M.bar = function`). The name is
written as in the source: `helper`, `M.foo`, `Account:deposit`. A nested
function stays inside the enclosing function, and an anonymous closure that
is never assigned is not an entry. The namespace is the `require` path.
"""

from crapper.languages.treesitter import (
    complexity,
    descendants,
    end_line,
    node_text,
    parse,
    start_line,
)
from crapper.languages.language import Language, LanguageFactory
from crapper.model import Function

_DECISIONS = {
    "if_statement",
    "elseif_statement",
    "while_statement",
    "repeat_statement",
    "for_statement",
}

_FUNCTIONS = {"function_declaration", "function_definition"}

_ROOTS = ("src/lua/", "src/", "lua/")


def _is_decision(node) -> bool:
    if node.type in _DECISIONS:
        return True
    return node.type == "binary_expression" and any(
        child.type in {"and", "or"} for child in node.children
    )


def _skip(node) -> bool:
    return False


def _relative(path: str, project_root: str | None) -> str:
    relative = path.replace("\\", "/")
    root = (project_root or "").replace("\\", "/").rstrip("/")
    if root and root != "." and relative.startswith(root + "/"):
        relative = relative[len(root) + 1 :]
    while relative.startswith("./"):
        relative = relative[2:]
    return relative


def _strip_lua_root(relative: str) -> str:
    for root in _ROOTS:
        if relative.startswith(root):
            return relative[len(root) :]
    return relative


def _module_namespace(path: str, project_root: str | None) -> str:
    relative = _strip_lua_root(_relative(path, project_root))
    if relative.endswith(".lua"):
        relative = relative[: -len(".lua")]
    if relative.endswith("/init"):
        relative = relative[: -len("/init")]
    return relative.replace("/", ".")


def _is_nested(node) -> bool:
    current = node.parent
    while current is not None:
        if current.type in _FUNCTIONS:
            return True
        current = current.parent
    return False


def _assigned_name(data: bytes, node):
    """The target of `name = function ... end`, or None for an unbound closure."""

    values = node.parent
    if values is None or values.type != "expression_list":
        return None
    assignment = values.parent
    if assignment is None or assignment.type != "assignment_statement":
        return None
    targets = [child for child in assignment.children if child.type == "variable_list"]
    if not targets:
        return None
    index = values.named_children.index(node)
    names = targets[0].named_children
    if index >= len(names):
        return None
    return node_text(data, names[index])


def _declaration_start(node):
    """`local f = function` starts at `local`, so the header shows the visibility."""

    assignment = node.parent.parent
    declaration = assignment.parent
    if declaration is not None and declaration.type == "variable_declaration":
        return declaration
    return assignment


def _entry(data: bytes, node):
    if node.type == "function_declaration":
        name = node.child_by_field_name("name")
        if name is None:
            return None
        return node_text(data, name), node
    name = _assigned_name(data, node)
    if name is None:
        return None
    return name, _declaration_start(node)


def functions_in_source(
    source: str, path: str, project_root: str | None = None
) -> list[Function]:
    data, tree = parse(source, "lua")
    namespace = _module_namespace(path, project_root)
    found: list[Function] = []
    for node in descendants(tree.root_node):
        if node.type not in _FUNCTIONS or _is_nested(node):
            continue
        entry = _entry(data, node)
        if entry is None:
            continue
        name, header = entry
        found.append(
            Function(
                name=name,
                namespace=namespace,
                complexity=complexity(node, _is_decision, _skip),
                start_line=start_line(header),
                end_line=end_line(node),
                path=path,
                language="lua",
            )
        )
    return found


class Lua(Language):
    def functions(self, source: str, path: str, project_root: str) -> list[Function]:
        return functions_in_source(source, path, project_root)


class LuaFactory(LanguageFactory):
    def create(self) -> Language:
        return Lua()
