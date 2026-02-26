from __future__ import annotations

from collections import deque
from typing import Callable, Deque, Iterable

from .base import Interviewer
from .models import Answer, AnswerValue, Question, QuestionType


class AutoApproveInterviewer(Interviewer):
    def ask(self, question: Question) -> Answer:
        if question.type in {QuestionType.YES_NO, QuestionType.CONFIRMATION}:
            return Answer(value=AnswerValue.YES)
        if question.options:
            first = question.options[0]
            return Answer(value=first.key, selected_option=first)
        return Answer(value="auto-approved", text="auto-approved")


class ConsoleInterviewer(Interviewer):
    def ask(self, question: Question) -> Answer:
        print(f"[?] {question.text}")

        if question.type == QuestionType.MULTIPLE_CHOICE:
            for option in question.options:
                print(f"  [{option.key}] {option.label}")
            response = input("Select: ").strip()
            return _match_option(response, question.options)

        if question.type in {QuestionType.YES_NO, QuestionType.CONFIRMATION}:
            response = input("[Y/N]: ").strip().lower()
            return Answer(value=AnswerValue.YES if response == "y" else AnswerValue.NO)

        if question.type == QuestionType.FREEFORM:
            return Answer(text=input("> ").strip())

        return Answer(text=input("> ").strip())


def _match_option(response: str, options) -> Answer:
    token = response.strip()
    if not token:
        return Answer()

    if token.isdigit():
        idx = int(token)
        if 1 <= idx <= len(options):
            selected = options[idx - 1]
            return Answer(value=selected.key, selected_option=selected)

    normalized = token.lower()
    for option in options:
        if option.key and option.key.lower() == normalized:
            return Answer(value=option.key, selected_option=option)
        if option.value and option.value.lower() == normalized:
            return Answer(value=option.key, selected_option=option)
        if option.label and option.label.lower() == normalized:
            return Answer(value=option.key, selected_option=option)

    return Answer(text=token)


class CallbackInterviewer(Interviewer):
    def __init__(self, callback: Callable[[Question], Answer]):
        self.callback = callback

    def ask(self, question: Question) -> Answer:
        return self.callback(question)


class QueueInterviewer(Interviewer):
    def __init__(self, answers: Iterable[Answer]):
        self._answers: Deque[Answer] = deque(answers)

    def ask(self, question: Question) -> Answer:
        if not self._answers:
            return Answer()
        return self._answers.popleft()


class RecordingInterviewer(Interviewer):
    def __init__(self, inner: Interviewer):
        self.inner = inner
        self.recordings: list[tuple[Question, Answer]] = []

    def ask(self, question: Question) -> Answer:
        answer = self.inner.ask(question)
        self.recordings.append((question, answer))
        return answer
