from attractor.interviewer import Answer, Question, QuestionOption, QuestionType


def test_question_supports_full_payload_fields():
    default_answer = Answer(text="fallback")
    options = [QuestionOption(label="Proceed", value="proceed", key="P")]

    question = Question(
        text="Proceed with deployment?",
        type=QuestionType.MULTIPLE_CHOICE,
        options=options,
        default=default_answer,
        timeout_seconds=30.0,
        stage="release_gate",
        metadata={"ticket": "ABC-123"},
    )

    assert question.text == "Proceed with deployment?"
    assert question.type == QuestionType.MULTIPLE_CHOICE
    assert question.options == options
    assert question.default == default_answer
    assert question.timeout_seconds == 30.0
    assert question.stage == "release_gate"
    assert question.metadata == {"ticket": "ABC-123"}


def test_question_rejects_unknown_question_type():
    try:
        Question(text="Proceed?", type="UNKNOWN")
    except ValueError as exc:
        assert "Unknown question type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported question type")


def test_question_rejects_non_option_items():
    try:
        Question(
            text="Pick one",
            type=QuestionType.MULTIPLE_CHOICE,
            options=[{"label": "A", "value": "a"}],
        )
    except TypeError as exc:
        assert "Question options" in str(exc)
    else:
        raise AssertionError("Expected TypeError for non-QuestionOption item")


def test_question_allows_blank_option_value_for_multiple_choice():
    question = Question(
        text="Pick one",
        type=QuestionType.MULTIPLE_CHOICE,
        options=[QuestionOption(label="Option A", key="A", value="   ")],
    )

    assert question.options[0].value == "A"


def test_question_accepts_spec_question_types():
    question = Question(
        text="Pick one",
        type="MULTIPLE_CHOICE",
        options=[QuestionOption(label="A", key="A", value="a")],
    )

    assert question.type.value == "MULTIPLE_CHOICE"

    yes_no = Question(text="Approve deploy?", type="YES_NO")
    freeform = Question(text="Why?", type="FREEFORM")
    confirmation = Question(text="Confirm?", type="CONFIRMATION")

    assert yes_no.type.value == "YES_NO"
    assert freeform.type.value == "FREEFORM"
    assert confirmation.type.value == "CONFIRMATION"


def test_question_rejects_options_for_non_multiple_choice():
    try:
        Question(
            text="Explain",
            type="FREEFORM",
            options=[QuestionOption(label="A", key="A", value="a")],
        )
    except ValueError as exc:
        assert "only valid for multiple-choice" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-multiple-choice options")


def test_question_rejects_blank_option_key_for_multiple_choice():
    try:
        Question(
            text="Pick one",
            type="MULTIPLE_CHOICE",
            options=[QuestionOption(label="A", key="   ", value="a")],
        )
    except ValueError as exc:
        assert "non-empty key" in str(exc)
    else:
        raise AssertionError("Expected ValueError for blank multiple-choice option key")
