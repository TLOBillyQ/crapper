"""Per-language function extraction."""

from crapper.languages import clojure, golang, java, python, rust, typescript
from crapper.model import Function


def functions_in_file(
    language: str, source: str, path: str, project_root: str
) -> list[Function]:
    if language == "clojure":
        return clojure.functions_in_source(source, path, project_root)
    if language == "java":
        return java.functions_in_source(source, path)
    if language == "go":
        return golang.functions_in_source(source, path, project_root)
    if language == "typescript":
        return typescript.functions_in_source(source, path, project_root)
    if language == "python":
        return python.functions_in_source(source, path, project_root)
    if language == "rust":
        return rust.functions_in_source(source, path, project_root)
    return []
