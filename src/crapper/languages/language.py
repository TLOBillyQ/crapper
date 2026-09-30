"""The operation every language implements."""

from abc import ABC, abstractmethod

from crapper.model import Function


class Language(ABC):
    @abstractmethod
    def functions(self, source: str, path: str, project_root: str) -> list[Function]:
        """Functions and methods defined in one source file."""


class Unknown(Language):
    def functions(self, source: str, path: str, project_root: str) -> list[Function]:
        return []
