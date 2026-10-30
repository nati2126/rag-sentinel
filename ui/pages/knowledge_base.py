import pandas as pd
import streamlit as st
from api import delete, get, patch, post, safe
from components import doc_label, page_setup

page_setup("Knowledge Base", "Upload documents, review metadata and browse version history.")

with st.expander(":material/upload_file: Upload a document", expanded=False):
    with st.form("upload", clear_on_submit=True):
        f = st.file_uploader("PDF, DOCX or Markdown", type=["pdf", "docx", "md", "markdown"])
        st.caption(
            "Metadata you enter overrides what is found in the file. Leave fields empty if unknown: nothing is guessed."
        )
        c = st.columns(3)
        title = c[0].text_input("Title")
        family = c[1].text_input(
            "Document family", help="Groups versions of one document. Default: derived from filename."
        )
        version = c[2].text_input("Version")
        c = st.columns(3)
        publication = c[0].text_input("Publication date (YYYY-MM-DD)")
        effective = c[1].text_input("Effective date (YYYY-MM-DD)")
        org = c[2].text_input("Source organisation")
        c = st.columns(3)
        authority = c[0].selectbox(
            "Authority level",
            ["", 1, 2, 3, 4, 5],
            help="1 = informal note / wiki, 3 = guide / handbook, 5 = official policy",
        )
        approval = c[1].selectbox("Approval status", ["", "approved", "pending", "draft", "withdrawn"])
        supersedes = c[2].text_input("Supersedes (filename or document id)")
        if st.form_submit_button("Upload and index", type="primary") and f is not None:
            data = {
                "title": title,
                "family": family,
                "version": version,
                "publication_date": publication,
                "effective_date": effective,
                "source_org": org,
                "authority_level": authority,
                "approval_status": approval,
                "supersedes": supersedes,
            }
            with st.spinner("Extracting text, embedding and extracting claims with the local LLM..."):
                res = safe(
                    post,
                    "/documents",
                    files={"file": (f.name, f.getvalue())},
                    data={k: str(v) for k, v in data.items() if v not in ("", None)},
                )
            if res:
                msg = {
                    "created": "Indexed as a new document",
                    "new_version": "Indexed as a NEW VERSION",
                    "duplicate": "Identical file already indexed (SHA-256 match); nothing changed",
                }[res["status"]]
                st.success(
                    f"{msg}: {res['document']['filename']} - {res['chunks']} chunks, {res['claims']} claims "
                    f"({res['claims_rejected']} rejected by grounding checks)."
                )
                for w in res["warnings"]:
                    st.warning(w)

docs = safe(get, "/documents", include_deleted=st.toggle("Show deleted versions", value=False)) or []
if not docs:
    st.info("The knowledge base is empty.")
    st.stop()

table = pd.DataFrame([{
    "Family": d["family_id"], "v#": d["version_number"], "File": d["filename"], "Title": d["title"],
    "Version": d["version_label"], "Effective": d["effective_date"], "Authority": d["authority_level"],
    "Approval": d["approval_status"], "Superseded": "yes" if d.get("superseded") else "",
    "Deleted": "yes" if d["is_deleted"] else "",
} for d in docs])  # fmt: skip
st.dataframe(table, hide_index=True, width="stretch")

options = {doc_label({**d, "version": d["version_label"]}): d for d in docs}
sel = st.selectbox("Select a document", list(options))
d = options[sel]
detail = safe(get, f"/documents/{d['id']}") or d

tab_meta, tab_versions, tab_history, tab_claims, tab_chunks, tab_actions = st.tabs(
    ["Metadata", "Versions", "History", "Claims", "Chunks", "Actions"]
)
with tab_meta:
    fields = ["title", "family_id", "version_label", "version_number", "publication_date", "effective_date",
              "created_date", "last_modified", "source_org", "authority_level", "approval_status", "supersedes_ref",
              "supersedes_id", "content_type", "sha256", "page_count", "char_count", "ingested_at"]  # fmt: skip
    src = detail.get("metadata_sources", {})
    st.dataframe(pd.DataFrame([{"Field": k, "Value": str(detail.get(k)) if detail.get(k) is not None else "unknown",
                                "Source": src.get(k.replace("_label", "").replace("_id", "").replace("_ref", ""), "")}
                               for k in fields]), hide_index=True, width="stretch")  # fmt: skip
    if detail.get("suggested_metadata"):
        st.info(
            "Suggested from the text (not trusted until you confirm): "
            + ", ".join(f"{k} = {v}" for k, v in detail["suggested_metadata"].items())
        )
    for w in detail.get("extraction_warnings") or []:
        st.warning(w)
with tab_versions:
    vers = safe(get, f"/documents/{d['id']}/versions") or []
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "v#": v["version_number"],
                    "File": v["filename"],
                    "Version": v["version_label"],
                    "Effective": v["effective_date"],
                    "Approval": v["approval_status"],
                    "Supersedes": v["supersedes_id"],
                    "SHA-256": v["sha256"][:12],
                    "Deleted": v["is_deleted"],
                }
                for v in vers
            ]
        ),
        hide_index=True,
        width="stretch",
    )
with tab_history:
    hist = safe(get, f"/documents/{d['id']}/history") or []
    st.dataframe(
        pd.DataFrame(
            [{"When": e["at"][:19].replace("T", " "), "Event": e["event"], "Detail": e["detail"]} for e in hist]
        ),
        hide_index=True,
        width="stretch",
    )
with tab_claims:
    claims = safe(get, f"/documents/{d['id']}/claims") or []
    if claims:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Subject": c["subject"],
                        "Attribute": c["predicate_key"],
                        "Value": c["value"],
                        "Normalized": c["value_norm"],
                        "Condition": c["qualifier"],
                        "Quote": c["source_quote"],
                    }
                    for c in claims
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("No claims extracted.")
with tab_chunks:
    for ch in safe(get, f"/documents/{d['id']}/chunks") or []:
        st.markdown(f"**#{ch['seq']}** `{ch['id']}`" + (f" page {ch['page']}" if ch["page"] else ""))
        st.text(ch["text"])
with tab_actions:
    if d["is_deleted"]:
        st.caption("Deleted versions are kept for history only.")
    else:
        c1, c2 = st.columns(2)
        if c1.button(":material/refresh: Reindex this document"):
            res = safe(post, f"/documents/{d['id']}/reindex")
            if res:
                st.success(f"Reindexed: {res['chunks']} chunks, {res['claims']} claims")
        confirm = c2.checkbox("I want to delete this document version")
        if c2.button(":material/delete: Delete", disabled=not confirm):
            if safe(delete, f"/documents/{d['id']}"):
                st.success("Deleted (history kept).")
                st.rerun()
        st.divider()
        others = {
            doc_label({**o, "version": o["version_label"]}): o["id"]
            for o in docs
            if o["id"] != d["id"] and not o["is_deleted"]
        }
        target = st.selectbox("Mark this document as superseded by", ["", *others])
        if st.button("Mark superseded", disabled=not target):
            if safe(post, f"/documents/{d['id']}/supersede", json={"superseded_by": others[target]}):
                st.success("Supersession recorded; conflicts re-analysed.")
        st.divider()
        with st.form("meta"):
            st.markdown("**Edit metadata**")
            c = st.columns(3)
            eff = c[0].text_input("Effective date", value=d["effective_date"] or "")
            auth = c[1].selectbox("Authority level", ["", 1, 2, 3, 4, 5], index=(d["authority_level"] or 0))
            appr = c[2].selectbox(
                "Approval",
                ["", "approved", "pending", "draft", "withdrawn", "unknown"],
                index=["", "approved", "pending", "draft", "withdrawn", "unknown"].index(d["approval_status"]),
            )
            if st.form_submit_button("Save"):
                body = {
                    k: v
                    for k, v in {
                        "effective_date": eff or None,
                        "authority_level": auth or None,
                        "approval_status": appr or None,
                    }.items()
                    if v
                }
                if safe(patch, f"/documents/{d['id']}/metadata", body):
                    st.success("Saved; conflicts re-analysed.")
