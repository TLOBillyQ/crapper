"""Clojure cyclomatic complexity, ported from crap4clj.

Decision points are the same forms crap4clj counts: `if` / `when` and their
variants, `and`, `or`, `loop`, `catch`, and each clause of `cond`, `condp`,
`case`, `cond->`, `cond->>`, `some->`, and `some->>`.
"""

import re

from crapper.languages.language import Language, LanguageFactory
from crapper.model import Function

_DECISION = re.compile(
    r"\((if-not|if-let|if-some|when-not|when-let|when-some|when-first|if|when|and|or|loop|catch)[\s\)]"
)
_COND = re.compile(r"\((some->>|some->|cond->>|cond->|cond|condp|case)[\s\)]")
_DEFN = re.compile(r"(?s)^\(\s*defn-?\s+([^\s\(\)\[\]\{\}\"]+)")
_NS = re.compile(r"\(\s*ns\s+([A-Za-z0-9*+!_?.\-/]+)")
_IN_NS = re.compile(r"\(\s*in-ns\s+'([A-Za-z0-9*+!_?.\-/]+)\s*\)")
_IN_NS_QUOTE = re.compile(
    r"\(\s*in-ns\s+\(quote\s+([A-Za-z0-9*+!_?.\-/]+)\)\s*\)"
)

_FORM_SKIP = {
    "condp": 2,
    "case": 1,
    "cond->": 1,
    "cond->>": 1,
    "some->": 1,
    "some->>": 1,
}
_THREAD_FORMS = {"some->", "some->>"}
_CHAR_DELIMITERS = set("()[]{}\";,")


def _strip_strings(text: str) -> str:
    mode = "normal"
    escaped = False
    out: list[str] = []
    for ch in text:
        newline = ch == "\n"
        if mode == "string":
            if escaped:
                out.append(ch if newline else " ")
                escaped = False
            elif ch == "\\":
                out.append(" ")
                escaped = True
            elif ch == '"':
                out.append(ch)
                mode = "normal"
            else:
                out.append(ch if newline else " ")
        elif ch == '"':
            out.append(ch)
            mode = "string"
        else:
            out.append(ch)
    return "".join(out)


def _strip_comments(text: str) -> str:
    return "\n".join(re.sub(r";.*", "", line) for line in text.splitlines())


def without_strings_and_comments(source: str) -> str:
    return _strip_comments(_strip_strings(source))


def _open_bracket(ch: str) -> bool:
    return ch in "({["


def _close_bracket(ch: str) -> bool:
    return ch in ")}]"


def _count_top_level_forms(text: str, start: int) -> int:
    depth = 1
    forms = 0
    in_form = False
    i = start
    n = len(text)
    while i < n and depth != 0:
        ch = text[i]
        if _open_bracket(ch):
            if depth == 1 and not in_form:
                forms += 1
            depth += 1
            in_form = True
        elif _close_bracket(ch):
            if depth == 1:
                in_form = False
            depth -= 1
        elif ch.isspace():
            in_form = depth != 1
        else:
            if depth == 1 and not in_form:
                forms += 1
            in_form = True
        i += 1
    return forms


def _skip_to_body(text: str, match_start: int) -> int:
    i = match_start + 1
    while i < len(text) and not text[i].isspace() and text[i] != ")":
        i += 1
    return i


def _pairwise_clause_count(form_type: str, remaining: int) -> int:
    base = remaining // 2
    if form_type == "case" and remaining % 2 == 1:
        return base + 1
    return base


def _count_clauses(text: str, form_type: str, match_start: int) -> int:
    body_start = _skip_to_body(text, match_start)
    total_forms = _count_top_level_forms(text, body_start)
    remaining = total_forms - _FORM_SKIP.get(form_type, 0)
    if form_type in _THREAD_FORMS:
        return remaining
    return _pairwise_clause_count(form_type, remaining)


def _count_cond_decisions(clean: str) -> int:
    total = 0
    for match in _COND.finditer(clean):
        form_type = _COND.match(match.group(0)).group(1)
        total += _count_clauses(clean, form_type, match.start())
    return total


def cyclomatic_complexity(fn_text: str) -> int:
    clean = without_strings_and_comments(fn_text)
    simple = len(_DECISION.findall(clean))
    return 1 + simple + _count_cond_decisions(clean)


def _char_literal_end(source: str, index: int) -> int:
    first = index + 1
    if first >= len(source):
        return len(source)
    i = first + 1
    while i < len(source):
        ch = source[i]
        if ch.isspace() or ch in _CHAR_DELIMITERS:
            return i
        i += 1
    return len(source)


def _consume_comment(source: str, index: int, line: int) -> tuple[int, int]:
    index += 1
    while index < len(source) and source[index] != "\n":
        index += 1
    if index < len(source):
        return index + 1, line + 1
    return index, line


def _consume_string(source: str, index: int, line: int) -> tuple[int, int]:
    index += 1
    escaped = False
    while index < len(source):
        ch = source[index]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            return index + 1, line
        if ch == "\n":
            line += 1
        index += 1
    return index, line


def _remember_form(
    forms: list[dict], source: str, start: int, start_line: int, end: int, line: int
) -> None:
    form_text = source[start : end + 1]
    matched = _DEFN.match(form_text)
    if matched is None:
        return
    forms.append(
        {
            "name": matched.group(1),
            "start_line": start_line,
            "end_line": line,
            "text": form_text,
        }
    )


def _close_form(forms, source, depth, form_start, form_line, index, line):
    if depth == 1 and form_start is not None and form_line is not None:
        _remember_form(forms, source, form_start, form_line, index, line)
        return 0, None, None
    return max(0, depth - 1), form_start, form_line


def _extract_top_level_defns(source: str) -> list[dict]:
    forms: list[dict] = []
    index = 0
    line = 1
    depth = 0
    form_start = None
    form_line = None
    while index < len(source):
        ch = source[index]
        if ch == ";":
            index, line = _consume_comment(source, index, line)
            continue
        if ch == '"':
            index, line = _consume_string(source, index, line)
            continue
        if ch == "\\":
            index = _char_literal_end(source, index)
            continue
        if ch == "(":
            if depth == 0:
                form_start = index
                form_line = line
            depth += 1
        elif ch == ")":
            depth, form_start, form_line = _close_form(
                forms, source, depth, form_start, form_line, index, line
            )
        if ch == "\n":
            line += 1
        index += 1
    return forms


def extract_functions(source: str) -> list[dict]:
    found = []
    for form in _extract_top_level_defns(source):
        found.append(
            {
                "name": form["name"],
                "start_line": form["start_line"],
                "end_line": form["end_line"],
                "complexity": cyclomatic_complexity(form["text"]),
            }
        )
    return found


def declared_namespace(source: str) -> str | None:
    for pattern in (_NS, _IN_NS, _IN_NS_QUOTE):
        match = pattern.search(source)
        if match:
            return match.group(1)
    return None


def namespace_from_path(path: str, source_root: str | None) -> str:
    relative = path.replace("\\", "/")
    root = (source_root or "").replace("\\", "/").rstrip("/")
    if root and root not in {".", ""} and relative.startswith(root + "/"):
        relative = relative[len(root) + 1 :]
    if relative.startswith("src/"):
        relative = relative[4:]
    elif "/src/" in relative:
        relative = relative.split("/src/", 1)[1]
    relative = re.sub(r"\.(?:clj[cs]?|bb)$", "", relative)
    return relative.replace("/", ".").replace("_", "-")


def functions_in_source(
    source: str, path: str, source_root: str | None = None
) -> list[Function]:
    namespace = declared_namespace(source) or namespace_from_path(path, source_root)
    return [
        Function(
            name=item["name"],
            namespace=namespace,
            complexity=item["complexity"],
            start_line=item["start_line"],
            end_line=item["end_line"],
            path=path,
            language="clojure",
        )
        for item in extract_functions(source)
    ]


class Clojure(Language):
    def functions(self, source: str, path: str, project_root: str) -> list[Function]:
        return functions_in_source(source, path, project_root)


class ClojureFactory(LanguageFactory):
    def create(self) -> Language:
        return Clojure()
