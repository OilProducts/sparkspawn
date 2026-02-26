from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List


class QuestionType(str, Enum):
    SINGLE_SELECT = "SINGLE_SELECT"
    MULTI_SELECT = "MULTI_SELECT"
    FREE_TEXT = "FREE_TEXT"
    CONFIRM = "CONFIRM"


@dataclass
class QuestionOption:
    label: str
    value: str
    key: str = ""


@dataclass(init=False)
class Question:
    text: str
    type: QuestionType
    options: List[QuestionOption]
    default: Answer | None
    timeout_seconds: float | None
    stage: str
    metadata: dict[str, Any]

    def __init__(
        self,
        text: str | None = None,
        type: QuestionType | None = None,
        options: List[QuestionOption] | None = None,
        default: Answer | None = None,
        timeout_seconds: float | None = None,
        stage: str = "",
        metadata: dict[str, Any] | None = None,
        *,
        title: str | None = None,
        prompt: str | None = None,
        question_type: QuestionType | None = None,
    ):
        resolved_type = type if type is not None else question_type
        if resolved_type is None:
            raise TypeError("Question requires `type` (or legacy `question_type`).")

        self.text = text if text is not None else (prompt or "")
        self.type = resolved_type
        self.options = list(options) if options else []
        self.default = default
        self.timeout_seconds = timeout_seconds
        self.stage = stage or (title or "")
        self.metadata = dict(metadata) if metadata else {}

    @property
    def title(self) -> str:
        return self.stage

    @title.setter
    def title(self, value: str) -> None:
        self.stage = value

    @property
    def prompt(self) -> str:
        return self.text

    @prompt.setter
    def prompt(self, value: str) -> None:
        self.text = value

    @property
    def question_type(self) -> QuestionType:
        return self.type

    @question_type.setter
    def question_type(self, value: QuestionType) -> None:
        self.type = value


@dataclass
class Answer:
    selected_values: List[str] = field(default_factory=list)
    text: str = ""
