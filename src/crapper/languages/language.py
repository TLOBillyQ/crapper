"""The language operation, and the factories that create language instances."""

from abc import ABC, abstractmethod

from crapper.model import Function


class Language(ABC):
    @abstractmethod
    def functions(self, source: str, path: str, project_root: str) -> list[Function]:
        """Functions and methods defined in one source file."""


class Unknown(Language):
    def functions(self, source: str, path: str, project_root: str) -> list[Function]:
        return []


class LanguageFactory(ABC):
    @abstractmethod
    def create(self) -> Language:
        """A language instance ready to read source files."""


class UnknownFactory(LanguageFactory):
    def create(self) -> Language:
        return Unknown()
