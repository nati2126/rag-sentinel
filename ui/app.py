"""RAG Sentinel dashboard. Run: streamlit run ui/app.py  (the API must be running)."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(page_title="RAG Sentinel", page_icon=":material/shield:", layout="wide")

pages = [
    st.Page("pages/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("pages/knowledge_base.py", title="Knowledge Base", icon=":material/folder_open:"),
    st.Page("pages/ask.py", title="Ask AI", icon=":material/question_answer:"),
    st.Page("pages/conflict_center.py", title="Conflict Center", icon=":material/compare_arrows:"),
    st.Page("pages/evaluation.py", title="Evaluation", icon=":material/monitoring:"),
]
with st.sidebar:
    st.markdown("### :material/shield: RAG Sentinel")
    st.caption("Trust the evidence, not just the answer.")
st.navigation(pages).run()
