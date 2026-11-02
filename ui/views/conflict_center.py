import pandas as pd
import streamlit as st
from api import get, post, safe
from components import KIND_LABEL, doc_label, page_setup, quote

page_setup("Conflict Center", "Claim-level findings across documents, with the evidence and reasoning behind each.")

c = st.columns(3)
kind = c[0].selectbox("Kind", ["(actionable)", "(all)", *KIND_LABEL], format_func=lambda k: KIND_LABEL.get(k, k))
status = c[1].selectbox("Status", ["open", "resolved", "dismissed", "(any)"])
if c[2].button(":material/sync: Re-run analysis"):
    with st.spinner("Re-analysing claims..."):
        safe(post, "/analysis/refresh")

params = {"status": None if status == "(any)" else status}
if kind == "(actionable)":
    params["actionable_only"] = True
elif kind != "(all)":
    params["kind"] = kind
rows = safe(get, "/conflicts", **params) or []
st.caption(f"{len(rows)} findings")
if not rows:
    st.info("No findings match the filters.")

order = {"contradiction": 0, "outdated": 1, "insufficient_evidence": 2}
for r in sorted(rows, key=lambda r: (order.get(r["kind"], 9), r["predicate_key"])):
    head = f"{KIND_LABEL.get(r['kind'], r['kind'])} · `{r['predicate_key']}`"
    if r["kind"] == "outdated" and not r["confirmed"]:
        head += " · possible (needs review)"
    if r.get("judge_opinion"):
        head += f" · contested by LLM judge ({r['judge_opinion'].replace('_', ' ')})"
    with st.expander(head, expanded=r["kind"] == "contradiction" and not r["preferred_doc_id"]):
        st.markdown(r["explanation"])
        a, b = st.columns(2)
        for col, side in ((a, "a"), (b, "b")):
            dd, cl = r[f"doc_{side}"], r[f"claim_{side}"]
            with col:
                pref = " :material/star: preferred" if r.get("preferred_doc_id") == (dd or {}).get("id") else ""
                st.markdown(f"**{doc_label(dd)}**{pref}")
                if dd:
                    st.caption(
                        f"effective {dd['effective_date'] or 'unknown'} · authority {dd['authority_level'] or '?'}/5 · "
                        f"{dd['approval_status']}"
                    )
                if cl:
                    st.markdown(f"Value: **{cl['value']}**" + (f" ({cl['qualifier']})" if cl.get("qualifier") else ""))
                    quote(cl["source_quote"])
        st.caption(
            f"Detected by: {r['detected_by']} · standing margin: {r['margin']} · status: {r['status']}"
            + (f" · note: {r['resolution_note']}" if r.get("resolution_note") else "")
        )
        with st.form(f"resolve-{r['id']}"):
            ids = {doc_label(r["doc_a"]): r["doc_a_id"], doc_label(r["doc_b"]): r["doc_b_id"]}
            c1, c2 = st.columns(2)
            pref = c1.selectbox("Authoritative source", ["(keep)", *ids])
            new_status = c2.selectbox("Set status", ["resolved", "dismissed", "open"])
            note = st.text_input("Review note")
            if st.form_submit_button("Save review"):
                ok = safe(
                    post,
                    f"/conflicts/{r['id']}/resolve",
                    json={"status": new_status, "preferred_doc_id": ids.get(pref), "note": note or None},
                )
                if ok:
                    st.success("Saved. Future answers use this resolution.")

st.divider()
st.subheader("Affected documents")
st.caption("When a document changes a value, find other documents still stating the old value.")
docs = [d for d in (safe(get, "/documents") or [])]
if docs:
    opts = {doc_label({**d, "version": d["version_label"]}): d["id"] for d in docs}
    pick = st.selectbox("Changed document", list(opts))
    rep = safe(get, f"/documents/{opts[pick]}/affected")
    if rep:
        if not rep["changes"]:
            st.caption("No value changes compared with earlier versions of this document.")
        for ch in rep["changes"]:
            st.markdown(
                f"- `{ch['predicate_key']}`: **{ch['old_value']} → {ch['new_value']}** (previously in {ch['previous_filename']})"
            )
        if rep["references"]:
            st.dataframe(pd.DataFrame([{
                "Document": x["filename"], "Attribute": x["predicate_key"], "Old value": x["old_value"],
                "Match": "confirmed" if x["confirmed"] else "possible - review", "Reason": x["reason"], "Text": x["quote"],
            } for x in rep["references"]]), hide_index=True, width="stretch")  # fmt: skip
