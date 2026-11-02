import pandas as pd
import streamlit as st
from api import get, safe
from components import KIND_LABEL, page_setup, status_icon

page_setup("Overview", "Knowledge health at a glance. All numbers come from the live knowledge base.")

stats = safe(get, "/stats")
health = safe(get, "/health")
if stats is None:
    st.stop()

if health and not health.get("llm_available"):
    st.warning(f"LLM `{health.get('llm')}` is not reachable. Start Ollama to ask questions and extract claims.")

c = st.columns(5)
c[0].metric("Documents", stats["documents"], help="Active (not deleted) document versions")
c[1].metric("Versions stored", stats["document_versions"], help="Every uploaded version, including deleted ones")
c[2].metric("Open contradictions", stats["open_contradictions"])
c[3].metric("Outdated references", stats["outdated_references"])
c[4].metric(
    "Knowledge health",
    f"{stats['health_score']:.0%}",
    help="Share of active documents not involved in an open contradiction or outdated reference",
)

c = st.columns(5)
c[0].metric("Families", stats["families"])
c[1].metric("Superseded", stats["superseded"], help=f"Superseded at {stats['as_of']}")
c[2].metric("Chunks", stats["chunks"])
c[3].metric("Extracted claims", stats["claims"])
c[4].metric(
    "Unresolved contradictions",
    stats["unresolved_contradictions"],
    help="Contradictions where no source clearly outranks the other",
)

left, right = st.columns(2)
with left:
    st.subheader("Findings by kind")
    kinds = stats["conflicts_by_kind"]
    if kinds:
        df = pd.DataFrame(
            [{"Kind": KIND_LABEL.get(k, k), "Count": v} for k, v in sorted(kinds.items(), key=lambda x: -x[1])]
        )
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("No findings yet. Upload documents on the Knowledge Base page.")
with right:
    st.subheader("Metadata completeness")
    comp = stats["metadata_completeness"]
    for field, share in comp.items():
        st.progress(share, text=f"{field.replace('_', ' ')}: {share:.0%} of documents")
    st.caption("Missing metadata is never guessed. Unknown values lower ranking confidence.")

st.subheader("Recent changes")
events = safe(get, "/events", limit=15) or []
if events:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "When": e["at"][:19].replace("T", " "),
                    "Event": e["event"],
                    "Document": e["filename"],
                    "Detail": e["detail"],
                }
                for e in events
            ]
        ),
        hide_index=True,
        width="stretch",
    )
else:
    st.caption("No events yet.")

st.subheader("Recent questions")
queries = safe(get, "/queries", limit=10) or []
if queries:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Status": f"{status_icon(q['status'])} {q['status']}",
                    "Question": q["question"],
                    "Pipeline": q["pipeline"],
                    "Latency (s)": round(q["latency_ms"] / 1000, 1),
                }
                for q in queries
            ]
        ),
        hide_index=True,
        width="stretch",
    )
else:
    st.caption("No questions asked yet.")
