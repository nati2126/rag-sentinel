import pandas as pd
import streamlit as st
from api import get, post, safe
from components import KIND_LABEL, STANDING_ICON, page_setup, quote, status_badge

page_setup("Ask AI", "Answers are generated only from cited evidence and checked by explicit evidence rules.")

pipes = safe(get, "/pipelines") or [{"name": "B4", "description": "RAG Sentinel"}]
names = [p["name"] for p in pipes]
desc = {p["name"]: p["description"] for p in pipes}

with st.form("ask"):
    q = st.text_input("Question", placeholder="How many days of annual leave do full-time employees get?")
    c = st.columns([2, 1])
    pipe = c[0].selectbox(
        "Pipeline",
        names,
        index=names.index("B4") if "B4" in names else 0,
        format_func=lambda n: f"{n} - {desc.get(n, '')}",
    )
    as_of = c[1].date_input("As-of date (optional)", value=None)
    go = st.form_submit_button("Ask", type="primary")

if go and q.strip():
    with st.spinner("Retrieving evidence, checking conflicts and generating with the local LLM..."):
        st.session_state["last"] = safe(
            post, "/ask", json={"question": q, "pipeline": pipe, "as_of": as_of.isoformat() if as_of else None}
        )
res = st.session_state.get("last")
if not res:
    st.stop()

status_badge(res["status"])
a = res["analysis"]
st.caption(
    f"Pipeline {res['pipeline']} · mode **{a['mode']}** · as of **{a['as_of']}** · {res['latency_ms'] / 1000:.1f}s"
    + (f" · {a['note']}" if a.get("note") else "")
)
st.markdown(f"#### {res['answer']}" if res["answer"] else "#### (no answer)")
if res["status"] == "NEEDS_REVIEW":
    st.warning(
        "This answer is **not verified**. Review the reasons and conflicting sources below before relying on it."
    )
for r in res["reasons"]:
    st.markdown(f"- :material/rule: {r}")
for w in res["warnings"]:
    st.markdown(f"- :material/info: {w}")

st.subheader("Citations")
if not res["citations"]:
    st.caption("No valid citations.")
for c in res["citations"]:
    with st.expander(
        f"[{c['label']}] {c['title']} {('v' + c['version']) if c.get('version') else ''} · {c['filename']}"
        + (f" · page {c['page']}" if c.get("page") else "")
    ):
        st.caption(
            f"{STANDING_ICON.get(c['standing_status'], '')} {c['standing_status'].replace('_', ' ')} · effective "
            f"{c.get('effective_date') or 'unknown'} · {c.get('approval_status')} · chunk `{c['chunk_id']}`"
        )
        quote(c["text"])

if res["conflicts"]:
    st.subheader("Conflict analysis")
    for c in res["conflicts"]:
        st.markdown(
            f"**{KIND_LABEL.get(c['kind'], c['kind'])}** ({c['detected_by']}, {c['status']}): {c['explanation']}"
        )

st.subheader("Retrieved evidence (ranked)")
if res["evidence"]:
    st.dataframe(pd.DataFrame([{
        "Label": e["label"], "Document": e["filename"], "Status": e["standing_status"], "Score": e["score"],
        "Relevance": e["relevance"], "Effective": e["effective_date"], "Approval": e["approval_status"],
        "Authority": e["authority_level"], "Why": e["explanation"],
    } for e in res["evidence"]]), hide_index=True, width="stretch")  # fmt: skip
else:
    st.caption("No evidence retrieved.")

with st.expander("Decision trace"):
    st.dataframe(pd.DataFrame(res["trace"]), hide_index=True, width="stretch")
    if res.get("generation"):
        st.json(res["generation"])
