from attractor.interviewer import Answer, Question, QuestionOption, QuestionType


def test_question_supports_full_payload_fields():
    default_answer = Answer(text="fallback")
    options = [QuestionOption(label="Proceed", value="proceed", key="P")]

    question = Question(
        text="Proceed with deployment?",
        type=QuestionType.CONFIRM,
        options=options,
        default=default_answer,
        timeout_seconds=30.0,
        stage="release_gate",
        metadata={"ticket": "ABC-123"},
    )

    assert question.text == "Proceed with deployment?"
    assert question.type == QuestionType.CONFIRM
    assert question.options == options
    assert question.default == default_answer
    assert question.timeout_seconds == 30.0
    assert question.stage == "release_gate"
    assert question.metadata == {"ticket": "ABC-123"}
