import os
import pytest
st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


@pytest.fixture
def at(tmp_path, monkeypatch):
    monkeypatch.setenv("ASK_LOG", str(tmp_path / "asks.jsonl"))
    t = AppTest.from_file(APP, default_timeout=60)
    t.run()
    assert not t.exception
    return t


def test_an_answer_shows_a_table_and_the_sql(at):
    at.chat_input[0].set_value("revenue by category in Q3 2026").run()
    assert not at.exception
    assert len(at.dataframe) >= 1 and len(at.expander) >= 1
    assert any("quarantine" in c.value for c in at.caption)


def test_ambiguous_question_offers_buttons_that_work(at):
    at.chat_input[0].set_value("what were our sales").run()
    labels = [b.label for b in at.button]
    assert "revenue" in labels and "units" in labels
    next(b for b in at.button if b.label == "revenue").click().run()
    assert not at.exception and len(at.session_state.chat) == 2
    assert at.session_state.chat[1][1].status == "answered" and at.session_state.chat[1][1].spec.metric == "revenue"


def test_switching_role_changes_what_is_allowed(at):
    at.sidebar.selectbox[0].select("Store manager, Odense").run()
    at.chat_input[0].set_value("revenue in Oslo").run()
    assert any("do not have access" in m.value for m in at.markdown)


def test_monitoring_tab_counts_questions(at):
    at.chat_input[0].set_value("revenue").run()
    at.chat_input[0].set_value("DROP TABLE x").run()
    assert any(m.label == "Questions" and m.value == "2" for m in at.metric)
