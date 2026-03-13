from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List


class QuestionType(str, Enum):
    YES_NO = "YES_NO"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    FREEFORM = "FREEFORM"
    CONFIRMATION = "CONFIRMATION"

    # Legacy aliases retained for compatibility with existing callers/tests.
    SINGLE_SELECT = MULTIPLE_CHOICE
    MULTI_SELECT = MULTIPLE_CHOICE
    FREE_TEXT = FREEFORM
    CONFIRM = CONFIRMATION


class AnswerValue(str, Enum):
    YES = "YES"
    NO = "NO"
    SKIPPED = "SKIPPED"
    TIMEOUT = "TIMEOUT"


@dataclass
class QuestionOption:
    label: str
    value: str = ""
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
        resolved_type = _coerce_question_type(type if type is not None else question_type)
        if resolved_type is None:
            raise TypeError("Question requires `type` (or legacy `question_type`).")

        resolved_options = list(options) if options else []
        _validate_option_schema(resolved_type, resolved_options)

        self.text = text if text is not None else (prompt or "")
        self.type = resolved_type
        self.options = resolved_options
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


@dataclass(init=False)
class Answer:
    value: str
    selected_option: QuestionOption | None
    text: str
    _selected_values: List[str]

    def __init__(
        self,
        value: str | AnswerValue = "",
        selected_option: QuestionOption | None = None,
        text: str = "",
        *,
        selected_values: List[str] | None = None,
    ) -> None:
        if isinstance(value, AnswerValue):
            value = value.value
        self.selected_option = selected_option
        self.text = text
        normalized = [str(item).strip() for item in (selected_values or []) if str(item).strip()]
        if not value and normalized:
            value = normalized[0]
        self.value = value
        self._selected_values = normalized

    @property
    def selected_values(self) -> List[str]:
        if self._selected_values:
            return list(self._selected_values)
        if self.value and self.value.strip():
            return [self.value.strip()]
        return []

    @selected_values.setter
    def selected_values(self, values: List[str]) -> None:
        normalized = [str(item).strip() for item in (values or []) if str(item).strip()]
        self._selected_values = normalized
        if normalized:
            self.value = normalized[0]


_SELECT_TYPES = {QuestionType.MULTIPLE_CHOICE}
_LEGACY_QUESTION_TYPE_NAMES = {
    "SINGLE_SELECT": QuestionType.MULTIPLE_CHOICE,
    "MULTI_SELECT": QuestionType.MULTIPLE_CHOICE,
    "FREE_TEXT": QuestionType.FREEFORM,
    "CONFIRM": QuestionType.CONFIRMATION,
}


def _coerce_question_type(value: QuestionType | str | None) -> QuestionType | None:
    if value is None:
        return None
    if isinstance(value, QuestionType):
        return value
    if isinstance(value, str):
        legacy = _LEGACY_QUESTION_TYPE_NAMES.get(value)
        if legacy is not None:
            return legacy
        try:
            return QuestionType(value)
        except ValueError as exc:
            raise ValueError(f"Unknown question type: {value}") from exc
    raise TypeError(f"Unsupported question type value: {value!r}")


def _validate_option_schema(question_type: QuestionType, options: list[QuestionOption]) -> None:
    if question_type not in _SELECT_TYPES and options:
        raise ValueError("Question options are only valid for multiple-choice questions.")

    for option in options:
        if not isinstance(option, QuestionOption):
            raise TypeError("Question options must be QuestionOption instances.")
        if not option.label or not option.label.strip():
            raise ValueError("Question options must include a non-empty label.")
        if question_type in _SELECT_TYPES and (not option.key or not option.key.strip()):
            raise ValueError("Multiple-choice question options must include a non-empty key.")
        if question_type in _SELECT_TYPES and (not option.value or not option.value.strip()):
            option.value = option.key.strip()
