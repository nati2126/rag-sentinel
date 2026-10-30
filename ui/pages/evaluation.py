import altair as alt
import pandas as pd
import streamlit as st
from api import get, safe
from components import page_setup

page_setup(
    "Evaluation", "VersionConflict benchmark results, read from results/*.json written by `python -m evaluation.run`."
)

data = safe(get, "/evaluation") or {}
summaries = {k.replace("_summary", ""): v for k, v in data.items() if k.endswith("_summary")}
if not summaries:
    st.info("No experiment results yet. Run: `python -m evaluation.run --split test --ablations`")
    st.stop()

split = st.radio("Split", sorted(summaries, key=lambda s: s != "test"), horizontal=True)
S = summaries[split]
env = S["environment"]
st.caption(
    f"{S['questions']} questions · as of {S['as_of']} · generated {S['generated_at']} · LLM {env['llm']} · "
    f"embedder {env['embedder']} · reranker {env['reranker']} · min relevance {env['min_relevance']}"
)

METRICS = [
    (
        "reliability",
        "Reliability",
        "Correct answer presented as reliable, or abstention when the gold decision is abstain",
        True,
    ),
    (
        "answer_accuracy",
        "Answer accuracy",
        "Presented answers containing the expected value (answerable questions)",
        True,
    ),
    (
        "stale_answer_rate",
        "Stale answer rate",
        "Presented answers that state an outdated / draft / future value",
        False,
    ),
    (
        "unsupported_answer_rate",
        "Unsupported answer rate",
        "Answers presented as reliable when gold says abstain",
        False,
    ),
    ("recall_at_5", "Recall@5", "Gold evidence found in the 5 passages given to the generator", True),
    ("mrr_at_5", "MRR@5", "Reciprocal rank of the first gold passage", True),
    ("citation_precision", "Citation precision", "Cited passages that are gold evidence", True),
    (
        "faithfulness_numeric",
        "Faithfulness (numeric grounding)",
        "Answers whose numbers all appear in cited passages",
        True,
    ),
    ("abstention_precision", "Abstention precision", "", True),
    ("abstention_recall", "Abstention recall", "", True),
    ("over_abstention_rate", "Over-abstention", "Answerable questions the system refused", False),
    ("decision_accuracy", "Decision accuracy (3-class)", "", True),
]
rows = []
for name, p in S["pipelines"].items():
    m = p["metrics"]
    row = {"Pipeline": name, "Description": p["description"]}
    for key, label, _, _ in METRICS:
        row[label] = m.get(key)
    row["Latency p50 (s)"] = (m["latency_ms"]["p50"] or 0) / 1000
    row["Latency p95 (s)"] = (m["latency_ms"]["p95"] or 0) / 1000
    rows.append(row)
df = pd.DataFrame(rows)

BLUE = "#2a78d6"


def bar(metric_label: str, higher_better: bool, help_text: str) -> alt.Chart:
    d = df[["Pipeline", metric_label]].dropna()
    base = alt.Chart(d).encode(
        y=alt.Y("Pipeline:N", sort=list(df["Pipeline"]), title=None),
        x=alt.X(f"{metric_label}:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", grid=True), title=None),
        tooltip=["Pipeline", alt.Tooltip(f"{metric_label}:Q", format=".1%")],
    )
    bars = base.mark_bar(color=BLUE, cornerRadiusEnd=4, height=14)
    labels = base.mark_text(align="left", dx=4, fontSize=11).encode(text=alt.Text(f"{metric_label}:Q", format=".0%"))
    arrow = "higher is better" if higher_better else "lower is better"
    return (bars + labels).properties(
        title=alt.TitleParams(metric_label, subtitle=f"{help_text} ({arrow})"), height=40 + 22 * len(d)
    )


st.subheader("Baselines and ablations")
main = ["Reliability", "Stale answer rate", "Unsupported answer rate", "Answer accuracy"]
cols = st.columns(2)
lookup = {label: (hb, h) for _, label, h, hb in METRICS}
for i, label in enumerate(main):
    hb, h = lookup[label]
    cols[i % 2].altair_chart(bar(label, hb, h), width="stretch")

with st.expander("All metrics (table)", expanded=True):
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={lbl: st.column_config.NumberColumn(format="percent") for _, lbl, _, _ in METRICS},
    )

st.subheader("Retrieval")
cols = st.columns(2)
for i, label in enumerate(["Recall@5", "MRR@5"]):
    hb, h = lookup[label]
    cols[i].altair_chart(bar(label, hb, h), width="stretch")

if "comparisons_vs_B4" in S:
    st.subheader("Paired comparison with B4 (reliability)")
    st.dataframe(pd.DataFrame([{
        "Pipeline": p, "B4 minus pipeline": c["reliability_diff"]["diff"] if c["reliability_diff"] else None,
        "95% CI (bootstrap)": str(c["reliability_diff"]["ci95"]) if c["reliability_diff"] else None,
        "McNemar p": c["mcnemar"]["p_value"], "B4 better / worse (questions)": f"{c['mcnemar']['b01']} / {c['mcnemar']['b10']}",
    } for p, c in S["comparisons_vs_B4"].items()]), hide_index=True, width="stretch")  # fmt: skip
    st.caption(
        "Exact McNemar test on per-question reliability. With ~80 questions, small differences are not significant."
    )

st.subheader("Contradiction detection (corpus level)")
cd = S["conflict_detection"]
st.dataframe(pd.DataFrame([{
    "Detector": name.replace("_", " "), "Precision": v["precision"], "Recall": v["recall"], "F1": v["f1"],
    "TP": v["tp"], "FP": v["fp"], "FN": v["fn"], "Kind accuracy (matched gold pairs)": v["kind_accuracy_on_matched_gold_pairs"],
} for name, v in cd.items() if isinstance(v, dict) and "precision" in v]), hide_index=True, width="stretch")  # fmt: skip
st.caption(
    f"Gold: {cd['gold_actionable']} actionable pairs (contradiction + outdated) out of {cd['gold_pairs']} annotated."
)
with st.expander("Missed and false-positive findings (full detector)"):
    full = cd["rules_plus_llm_judge"]
    st.markdown("**Missed**")
    st.dataframe(pd.DataFrame(full["missed"]), hide_index=True, width="stretch")
    st.markdown("**False positives**")
    st.dataframe(pd.DataFrame(full["false_positive_examples"]), hide_index=True, width="stretch")

st.subheader("Reliability by question category")
cat = pd.DataFrame({name: p["metrics"]["reliability_by_category"] for name, p in S["pipelines"].items()})
st.dataframe(
    cat, width="stretch", column_config={c: st.column_config.NumberColumn(format="percent") for c in cat.columns}
)

st.subheader("Ingestion")
st.json(S["ingestion"], expanded=False)
