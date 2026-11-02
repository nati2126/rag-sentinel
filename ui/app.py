"""RAG Sentinel dashboard. Run: streamlit run ui/app.py  (the API must be running)."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(page_title="RAG Sentinel", page_icon=":material/shield:", layout="wide")

# Pages live in views/, not pages/: Streamlit would auto-discover a pages/ folder and bypass this navigation
# when a page URL is opened directly on a fresh server.
pages = [
    st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("views/knowledge_base.py", title="Knowledge Base", icon=":material/folder_open:"),
    st.Page("views/ask.py", title="Ask AI", icon=":material/question_answer:"),
    st.Page("views/conflict_center.py", title="Conflict Center", icon=":material/compare_arrows:"),
    st.Page("views/evaluation.py", title="Evaluation", icon=":material/monitoring:"),
]
with st.sidebar:
    st.markdown("### :material/shield: RAG Sentinel")
    st.caption("Trust the evidence, not just the answer.")
st.navigation(pages).run()
