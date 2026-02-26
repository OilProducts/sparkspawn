from __future__ import annotations

from attractor.engine.outcome import Outcome, OutcomeStatus
from attractor.interviewer import Answer, Interviewer, Question, QuestionOption, QuestionType

from ..base import HandlerRuntime


class WaitHumanHandler:
    def __init__(self, interviewer: Interviewer):
        self.interviewer = interviewer

    def execute(self, runtime: HandlerRuntime) -> Outcome:
        if not runtime.outgoing_edges:
            return Outcome(status=OutcomeStatus.FAIL, failure_reason="No outgoing edges for human gate")

        options = []
        for edge in runtime.outgoing_edges:
            label_attr = edge.attrs.get("label")
            label = edge.target
            if label_attr is not None:
                raw_label = str(label_attr.value)
                if raw_label.strip():
                    label = raw_label
            options.append(QuestionOption(label=label, value=label, key=_parse_accelerator_key(label)))

        question = Question(
            title=f"Human Gate: {runtime.node_id}",
            prompt=runtime.prompt or "Choose next route",
            question_type=QuestionType.SINGLE_SELECT,
            options=options,
            metadata={"node_id": runtime.node_id},
        )

        answer = self.interviewer.ask(question)
        selected = _pick_single(answer)
        if not selected:
            return Outcome(status=OutcomeStatus.FAIL, failure_reason="human skipped interaction")

        return Outcome(status=OutcomeStatus.SUCCESS, preferred_label=selected, notes="human selection applied")


def _pick_single(answer: Answer) -> str:
    if answer.selected_values:
        return answer.selected_values[0]
    return ""


def _parse_accelerator_key(label: str) -> str:
    text = (label or "").strip()
    if not text:
        return ""

    if text.startswith("[") and "]" in text:
        inside = text[1 : text.find("]")].strip()
        if inside:
            return inside[0].upper()

    if len(text) >= 2 and text[0].isalnum() and text[1] == ")":
        return text[0].upper()

    if len(text) >= 3 and text[0].isalnum():
        idx = 1
        while idx < len(text) and text[idx] == " ":
            idx += 1
        if idx < len(text) and text[idx] == "-":
            return text[0].upper()

    return text[0].upper()
