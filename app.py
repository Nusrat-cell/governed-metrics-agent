"""A small web front end for the agent. Run with: streamlit run app.py

The role is picked in the sidebar to make the access rules easy to see. In a real deployment it
would come from the login, never from the page.
"""
import json
import os
import re

import pandas as pd
import streamlit as st

from metricagent.access import User
from metricagent.agent import Agent
from metricagent.data import STORES, build
from metricagent.planner import RulePlanner
from metricagent.semantic import Layer

LOG = os.environ.get("ASK_LOG", "logs/asks.jsonl")
USERS = {
    "Admin (sees every store)": User("admin", "admin"),
    "Store manager, Odense": User("odense", "store_manager", ("S06",)),
    "Store manager, Oslo": User("oslo", "store_manager", ("S11",)),
    "Manager of two Aarhus stores": User("aarhus", "store_manager", ("S04", "S05")),
}
EXAMPLES = ["revenue by category in Q3 2026", "top 5 stores by margin percent last year", "target attainment by region in March 2026",
            "what were our sales", "units for Denmark by month in 2026"]


@st.cache_resource
def get_agent(log_path):
    db, layer = build(), Layer()
    return Agent(db, layer, RulePlanner(layer, db), log_path=log_path), layer


def show(ans, key):
    st.write(ans.text.split("\n")[0] if ans.status == "answered" else ans.text)
    if ans.rows and ans.spec is not None:
        cols = list(ans.spec.group_by) + ["value"]
        df = pd.DataFrame(ans.rows, columns=cols)
        st.dataframe(df, hide_index=True, width="stretch", column_config={"value": st.column_config.NumberColumn("value", format="localized")})
        if len(ans.spec.group_by) == 1 and len(df) > 1:
            x = ans.spec.group_by[0]
            (st.line_chart if x in ("month", "quarter", "year") else st.bar_chart)(df.set_index(x)["value"].sort_index() if x in ("month", "quarter", "year") else df.set_index(x)["value"])
    for c in ans.caveats:
        st.caption("Note: " + c)
    if ans.sql:
        with st.expander("How this was worked out"):
            st.write("Built from the metric definition, not from the question text:")
            st.json({k: v for k, v in vars(ans.spec).items() if v not in (None, [], {})} if ans.spec else {})
            st.code(ans.sql, language="sql")


def monitoring():
    if not os.path.exists(LOG):
        st.info("No questions logged yet.")
        return
    df = pd.DataFrame([json.loads(l) for l in open(LOG, encoding="utf-8")])
    a, b, c = st.columns(3)
    a.metric("Questions", len(df))
    b.metric("Answered", f"{100 * (df.status == 'answered').mean():.0f}%")
    c.metric("Median time", f"{df.ms.median():.0f} ms")
    st.bar_chart(df.status.value_counts())
    refused = df[df.status.isin(["refused", "clarify"])]
    if len(refused):
        st.subheader("Why questions were not answered")
        st.dataframe(refused.groupby("reason").size().sort_values(ascending=False).rename("times"))


st.set_page_config(page_title="Governed metrics agent", layout="wide")
agent, layer = get_agent(LOG)
who = st.sidebar.selectbox("Signed in as", list(USERS))
user = USERS[who]
st.sidebar.caption("Metrics: " + ", ".join(layer.metrics))
st.sidebar.caption("Data loaded up to 2026-10-31. Synthetic.")
st.title("Ask about the numbers")
ask_tab, mon_tab = st.tabs(["Ask", "Monitoring"])

with ask_tab:
    if "chat" not in st.session_state or st.session_state.get("who") != who:
        st.session_state.chat, st.session_state.who = [], who
    for i, (q, ans) in enumerate(st.session_state.chat):
        with st.chat_message("user"):
            st.write(q)
        with st.chat_message("assistant"):
            show(ans, i)
            if ans.status == "clarify":
                for opt in ans.options:
                    if st.button(opt, key=f"opt{i}{opt}"):
                        fixed = re.sub(r"\b(sales|performance|performing)\b", opt.replace("_", " "), q, flags=re.I)
                        st.session_state.chat.append((fixed, agent.ask(fixed, user)))
                        st.rerun()
    if not st.session_state.chat:
        st.caption("Try one of these:")
        for ex in EXAMPLES:
            if st.button(ex):
                st.session_state.chat.append((ex, agent.ask(ex, user)))
                st.rerun()
    q = st.chat_input("Ask a question, for example: revenue by country in 2026")
    if q:
        st.session_state.chat.append((q, agent.ask(q, user)))
        st.rerun()

with mon_tab:
    monitoring()
