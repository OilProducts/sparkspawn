import json
from unittest.mock import patch

from attractor.interviewer import (
    Answer,
    AnswerValue,
    AutoApproveInterviewer,
    CallbackInterviewer,
    ConsoleInterviewer,
    Interviewer,
    Question,
    QuestionOption,
    QuestionType,
    QueueInterviewer,
    RecordingInterviewer,
)


class TestInterviewerImplementations:
    def test_interviewer_ask_multiple_delegates_to_ask(self):
        class _StubInterviewer(Interviewer):
            def ask(self, question: Question) -> Answer:
                return Answer(selected_values=[question.stage])

        interviewer = _StubInterviewer()
        questions = [
            Question(stage="q1", text="p1", type=QuestionType.MULTIPLE_CHOICE),
            Question(stage="q2", text="p2", type=QuestionType.MULTIPLE_CHOICE),
        ]

        answers = interviewer.ask_multiple(questions)
        assert [answer.selected_values for answer in answers] == [["q1"], ["q2"]]

    def test_interviewer_inform_default_is_noop(self):
        class _StubInterviewer(Interviewer):
            def ask(self, question: Question) -> Answer:
                return Answer()

        interviewer = _StubInterviewer()
        assert interviewer.inform("Heads up", "review") is None

    def test_autoapprove_yes_no_returns_yes_value(self):
        q = Question(stage="Deploy", text="Ship it?", type=QuestionType.YES_NO)
        answer = AutoApproveInterviewer().ask(q)
        assert answer.value == AnswerValue.YES.value

    def test_autoapprove_multiple_choice_picks_first_option_key(self):
        first = QuestionOption(label="A", value="a", key="A")
        second = QuestionOption(label="B", value="b", key="B")
        q = Question(
            stage="Pick",
            text="choose",
            type=QuestionType.MULTIPLE_CHOICE,
            options=[first, second],
        )
        answer = AutoApproveInterviewer().ask(q)
        assert answer.value == "A"
        assert answer.selected_option == first

    def test_console_interviewer_multiple_choice_matches_option_key_case_insensitive(self):
        question = Question(
            text="Pick one",
            type=QuestionType.MULTIPLE_CHOICE,
            options=[QuestionOption(label="Alpha", value="alpha", key="A"), QuestionOption(label="Beta", value="beta", key="B")],
        )

        with patch("builtins.input", return_value="b"):
            answer = ConsoleInterviewer().ask(question)

        assert answer.value == "B"
        assert answer.selected_option == question.options[1]

    def test_console_interviewer_yes_no_maps_y_to_yes(self):
        question = Question(text="Proceed?", type=QuestionType.YES_NO)

        with patch("builtins.input", return_value="Y"):
            answer = ConsoleInterviewer().ask(question)

        assert answer.value == AnswerValue.YES.value

    def test_console_interviewer_yes_no_maps_non_yes_to_no(self):
        question = Question(text="Proceed?", type=QuestionType.YES_NO)

        with patch("builtins.input", return_value="n"):
            answer = ConsoleInterviewer().ask(question)

        assert answer.value == AnswerValue.NO.value

    def test_console_interviewer_freeform_returns_text(self):
        question = Question(text="Why?", type=QuestionType.FREEFORM)

        with patch("builtins.input", return_value="because"):
            answer = ConsoleInterviewer().ask(question)

        assert answer.text == "because"

    def test_callback_interviewer(self):
        interviewer = CallbackInterviewer(lambda q: Answer(selected_values=["x"]))
        answer = interviewer.ask(Question(stage="T", text="P", type=QuestionType.CONFIRMATION))
        assert answer.selected_values == ["x"]

    def test_queue_interviewer(self):
        interviewer = QueueInterviewer([Answer(selected_values=["first"]), Answer(text="second")])
        a1 = interviewer.ask(Question(stage="1", text="1", type=QuestionType.MULTIPLE_CHOICE))
        a2 = interviewer.ask(Question(stage="2", text="2", type=QuestionType.FREEFORM))
        a3 = interviewer.ask(Question(stage="3", text="3", type=QuestionType.FREEFORM))
        assert a1.selected_values == ["first"]
        assert a2.text == "second"
        assert a3.value == AnswerValue.SKIPPED.value

    def test_recording_interviewer_persists_jsonl_records(self, tmp_path):
        record_path = tmp_path / "recordings.jsonl"
        interviewer = RecordingInterviewer(
            QueueInterviewer([Answer(value=AnswerValue.YES), Answer(text="notes")]),
            record_path=record_path,
        )

        interviewer.ask(Question(text="Ship?", type=QuestionType.YES_NO, stage="gate"))
        interviewer.ask(Question(text="Why?", type=QuestionType.FREEFORM, stage="gate"))

        lines = record_path.read_text().strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["question"]["text"] == "Ship?"
        assert first["answer"]["value"] == AnswerValue.YES.value
        assert second["question"]["text"] == "Why?"
        assert second["answer"]["text"] == "notes"

    def test_builtin_interviewer_variants_satisfy_adapter_contracts(self):
        question = Question(
            stage="Pick",
            text="Choose one",
            type=QuestionType.MULTIPLE_CHOICE,
            options=[QuestionOption(label="A", value="a", key="A"), QuestionOption(label="B", value="b", key="B")],
        )
        with patch("builtins.input", side_effect=["1", "1"]):
            interviewer_variants = [
                AutoApproveInterviewer(),
                CallbackInterviewer(lambda _: Answer(selected_values=["cb"])),
                ConsoleInterviewer(),
                QueueInterviewer([Answer(selected_values=["queued"]), Answer(selected_values=["queued-2"])]),
                RecordingInterviewer(
                    QueueInterviewer([Answer(selected_values=["recorded"]), Answer(selected_values=["recorded-2"])])
                ),
            ]

            for interviewer in interviewer_variants:
                answer = interviewer.ask(question)
                assert isinstance(answer, Answer)
                answers = interviewer.ask_multiple([question])
                assert len(answers) == 1
                assert isinstance(answers[0], Answer)
                assert interviewer.inform("heads up", "review") is None
