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
                return Answer(selected_values=[question.title])

        interviewer = _StubInterviewer()
        questions = [
            Question(title="q1", prompt="p1", question_type=QuestionType.SINGLE_SELECT),
            Question(title="q2", prompt="p2", question_type=QuestionType.SINGLE_SELECT),
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
        q = Question(title="Deploy", prompt="Ship it?", question_type=QuestionType.YES_NO)
        answer = AutoApproveInterviewer().ask(q)
        assert answer.value == AnswerValue.YES.value

    def test_autoapprove_multiple_choice_picks_first_option_key(self):
        first = QuestionOption(label="A", value="a", key="A")
        second = QuestionOption(label="B", value="b", key="B")
        q = Question(
            title="Pick",
            prompt="choose",
            question_type=QuestionType.MULTIPLE_CHOICE,
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
        answer = interviewer.ask(Question(title="T", prompt="P", question_type=QuestionType.CONFIRMATION))
        assert answer.selected_values == ["x"]

    def test_queue_interviewer(self):
        interviewer = QueueInterviewer([Answer(selected_values=["first"]), Answer(text="second")])
        a1 = interviewer.ask(Question(title="1", prompt="1", question_type=QuestionType.SINGLE_SELECT))
        a2 = interviewer.ask(Question(title="2", prompt="2", question_type=QuestionType.FREE_TEXT))
        assert a1.selected_values == ["first"]
        assert a2.text == "second"

    def test_builtin_interviewer_variants_satisfy_adapter_contracts(self):
        question = Question(
            title="Pick",
            prompt="Choose one",
            question_type=QuestionType.MULTIPLE_CHOICE,
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
