"""Per-language function extraction."""

from crapper.languages.clojure import Clojure
from crapper.languages.golang import Go
from crapper.languages.java import Java
from crapper.languages.language import Unknown
from crapper.languages.python import Python
from crapper.languages.rust import Rust
from crapper.languages.typescript import TypeScript
from crapper.model import Function

_LANGUAGES = {
    "clojure": Clojure(),
    "java": Java(),
    "go": Go(),
    "typescript": TypeScript(),
    "python": Python(),
    "rust": Rust(),
}
_UNKNOWN = Unknown()


def functions_in_file(
    language: str, source: str, path: str, project_root: str
) -> list[Function]:
    chosen = _LANGUAGES.get(language, _UNKNOWN)
    return chosen.functions(source, path, project_root)
