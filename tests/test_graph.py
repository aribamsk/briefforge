from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.graph import build_graph, parse_questions

QUESTIONS = '["What is the market size?", "Who are the buyers?", "What are the risks?", "What should we do next?"]'


def test_parse_questions_accepts_json_array():
    assert parse_questions(QUESTIONS) == [
        "What is the market size?",
        "Who are the buyers?",
        "What are the risks?",
        "What should we do next?",
    ]


def test_parse_questions_recovers_from_prose():
    raw = f"Sure, here you go:\n{QUESTIONS}\nLet me know!"
    assert len(parse_questions(raw)) == 4


def test_parse_questions_falls_back_on_garbage():
    questions = parse_questions("not json", "edge computing")
    assert questions == ["What are the key considerations for edge computing?"]


def test_graph_finishes_when_editor_approves():
    fake = FakeListChatModel(
        responses=[
            QUESTIONS,
            "finding 1",
            "finding 2",
            "finding 3",
            "finding 4",
            "# Draft brief",
            "APPROVED",
        ]
    )
    result = build_graph(fake).invoke(
        {"topic": "Edge AI", "audience": "CTO", "notes": ""}
    )

    assert result["final"] == "# Draft brief"
    assert result["revision"] == 1
    assert len(result["questions"]) == 4


def test_graph_revises_once_before_finalizing():
    fake = FakeListChatModel(
        responses=[
            QUESTIONS,
            "finding 1",
            "finding 2",
            "finding 3",
            "finding 4",
            "# Draft v1",
            "GAP: missing risk section",
            "# Draft v2",
            "APPROVED",
        ]
    )
    result = build_graph(fake).invoke(
        {"topic": "Edge AI", "audience": "CTO", "notes": "internal notes"}
    )

    assert result["final"] == "# Draft v2"
    assert result["revision"] == 2
