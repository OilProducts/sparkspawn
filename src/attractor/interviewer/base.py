from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from .models import Answer, Question


class Interviewer(ABC):
    @abstractmethod
    def ask(self, question: Question) -> Answer:
        raise NotImplementedError

    def ask_multiple(self, questions: Iterable[Question]) -> list[Answer]:
        return [self.ask(question) for question in questions]

    def inform(self, message: str, stage: str) -> None:
        return None
