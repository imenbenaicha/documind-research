"""DocuMind Research — shared paper library and readable research workspace."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.documind.research_library import (
    init_research_schema,
    add_paper,
    list_papers,
    get_paper,
    update_paper_metadata,
    delete_paper,
    create_collection,
    list_collections,
    add_paper_to_collection,
    papers_in_collection,
)
from src.documind.research_analysis import FEATURES, run_research_analysis

st.set_page_config(page_title="DocuMind Research", page_icon="🔬", layout="wide")
init_research_schema()


def _clean(value):
    """Return readable text for model-generated values."""
    if value is None or value == "":
        return "Not reported in the supplied paper text."
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return value
    return str(value)


def _show_list(items, empty_message="Not reported in the supplied paper text."):
    if not items:
        st.caption(empty_message)
        return
    for item in items:
        if isinstance(item, dict):
            main = item.get("claim") or item.get("name") or item.get("item") or item.get("topic") or json.dumps(item, ensure_ascii=False)
            detail = item.get("details") or item.get("description") or item.get("purpose")
            st.markdown(f"- **{main}**" + (f" — {detail}" if detail else ""))
        else:
            st.markdown(f"- {item}")


def _show_evidence(evidence):
    if not evidence:
        st.info("No passage-level evidence was returned for this analysis. Check the original PDF before relying on the findings.")
        return
    for index, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            st.write(item)
            continue
        claim = item.get("claim") or item.get("finding") or item.get("item") or f"Evidence {index}"
        page = item.get("page") or item.get("page_number")
        paper = item.get("paper") or item.get("filename")
        quote = item.get("quote") or item.get("passage") or item.get("evidence")
        heading = str(claim)
        if page:
            heading += f" · PDF page {page}"
        if paper:
            heading += f" · {paper}"
        with st.expander(heading):
            if quote:
                st.markdown(f"> {quote}")
            if item.get("details"):
                st.write(item["details"])
            if not quote and not item.get("details"):
                st.caption("The model did not return an exact supporting quotation.")


def _render_paper_summary(result):
    papers_data = result.get("papers", [])
    if not papers_data:
        st.info("No paper summary was returned.")
        return
    for paper in papers_data:
        st.markdown(f"### {paper.get('paper', 'Research paper')}")
        overview_tab, technical_tab, evidence_tab = st.tabs(["Overview", "Technical Analysis", "Evidence"])
        with overview_tab:
            st.markdown("#### Research problem")
            st.write(_clean(paper.get("research_problem")))
            st.markdown("#### Research objectives")
            _show_list(paper.get("objectives", []))
            st.markdown("#### Main contributions")
            _show_list(paper.get("contributions", []))
            st.markdown("#### Main findings")
            _show_list(paper.get("results", []))
            st.markdown("#### Limitations and future work")
            left, right = st.columns(2)
            with left:
                st.markdown("**Limitations**")
                _show_list(paper.get("limitations", []))
            with right:
                st.markdown("**Future work**")
                _show_list(paper.get("future_work", []))
        with technical_tab:
            st.markdown("#### Methodology")
            st.write(_clean(paper.get("methodology")))
            for title, key in [
                ("Datasets", "datasets"),
                ("Baselines", "baselines"),
                ("Evaluation metrics", "metrics"),
                ("Information not reported", "not_reported"),
            ]:
                st.markdown(f"**{title}**")
                _show_list(paper.get(key, []))
        with evidence_tab:
            _show_evidence(paper.get("evidence", []))


def _render_methodology(result):
    for paper in result.get("papers", []):
        st.markdown(f"### {paper.get('paper', 'Research paper')}")
        overview_tab, technical_tab, evidence_tab = st.tabs(["Overview", "Technical Analysis", "Evidence"])
        with overview_tab:
            st.markdown("**Study design**")
            st.write(_clean(paper.get("study_design")))
            st.markdown("**Research questions**")
            _show_list(paper.get("research_questions", []))
            st.markdown("**Data sources and dataset size**")
            _show_list(paper.get("data_sources", []))
            st.write(_clean(paper.get("sample_or_dataset_size")))
        with technical_tab:
            for title, key in [
                ("Preprocessing", "preprocessing"),
                ("Features and variables", "features_or_variables"),
                ("Models and algorithms", "models_and_algorithms"),
                ("Experimental setup", "experimental_setup"),
                ("Baselines", "baselines"),
                ("Evaluation protocol", "evaluation_protocol"),
                ("Metrics", "metrics"),
                ("Statistical tests", "statistical_tests"),
                ("Software and hardware", "software_hardware"),
                ("Implementation details", "implementation_details"),
                ("Not reported", "not_reported"),
            ]:
                st.markdown(f"**{title}**")
                value = paper.get(key)
                if isinstance(value, list):
                    _show_list(value)
                else:
                    st.write(_clean(value))
        with evidence_tab:
            _show_evidence(paper.get("evidence", []))


def _render_reproducibility(result):
    for paper in result.get("papers", []):
        st.markdown(f"### {paper.get('paper', 'Research paper')}")
        assessment = paper.get("assessment", [])
        if assessment:
            rows = []
            for item in assessment:
                rows.append({
                    "Reproducibility item": item.get("item", ""),
                    "Status": str(item.get("status", "not reported")).replace("_", " ").title(),
                    "Details": item.get("details", ""),
                    "Page": item.get("page", ""),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        a, b, c = st.columns(3)
        with a:
            st.markdown("**Strengths**")
            _show_list(paper.get("reproducibility_strengths", []))
        with b:
            st.markdown("**Gaps**")
            _show_list(paper.get("reproducibility_gaps", []))
        with c:
            st.markdown("**Questions for authors**")
            _show_list(paper.get("questions_for_authors", []))
        st.caption("A missing detail in the extracted text does not prove that the authors never reported it elsewhere.")


def _render_benchmark(result):
    rows = result.get("benchmark_rows", [])
    if rows:
        st.markdown("#### Results and benchmark comparison")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No benchmark rows were extracted from the selected papers.")
    with st.expander("Comparability notes and missing information", expanded=True):
        st.markdown("**Comparability notes**")
        _show_list(result.get("comparability_notes", []))
        st.markdown("**Missing information**")
        _show_list(result.get("missing_information", []))


def _render_synthesis(result):
    tabs = st.tabs(["Agreements", "Differences", "Contradictions", "Research gaps"])
    with tabs[0]:
        _show_list(result.get("agreements", []))
    with tabs[1]:
        _show_list(result.get("differences", []))
        st.markdown("**Non-comparable results**")
        _show_list(result.get("non_comparable_results", []))
    with tabs[2]:
        _show_list(result.get("direct_contradictions", []), "No direct contradictions were identified in the supplied text.")
    with tabs[3]:
        _show_list(result.get("research_gaps", []))
        st.markdown("**Open questions**")
        _show_list(result.get("open_questions", []))


def _render_paper_to_code(result):
    for paper in result.get("papers", []):
        st.markdown(f"### {paper.get('paper', 'Research paper')}")
        urls = paper.get("repository_urls", [])
        st.markdown("**Repository links explicitly found in the paper**")
        if urls:
            for url in urls:
                st.markdown(f"- [{url}]({url})")
        else:
            st.caption("No repository URL was found in the supplied text.")
        for title, key in [("Software and libraries", "software_and_libraries"), ("Models and packages", "models_or_packages"), ("Implementation steps", "implementation_steps"), ("Missing implementation details", "missing_implementation_details")]:
            st.markdown(f"**{title}**")
            _show_list(paper.get(key, []))
        st.markdown("**Method-to-code map**")
        _show_list(paper.get("method_to_code_map", []))


def _render_citation_context(result):
    for paper in result.get("papers", []):
        st.markdown(f"### {paper.get('paper', 'Research paper')}")
        citations = paper.get("citations", [])
        if citations:
            st.dataframe(pd.DataFrame([{
                "Citation": c.get("citation_as_written", ""),
                "Role": c.get("role", ""),
                "Context": c.get("context", ""),
                "Page": c.get("page", ""),
                "Identity resolved": c.get("identity_resolved_from_text", False),
            } for c in citations]), use_container_width=True, hide_index=True)
        else:
            st.info("No citation-context records were extracted.")
        st.markdown("**Unresolved references**")
        _show_list(paper.get("unresolved_references", []))


def _render_knowledge_graph(result):
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])
    if nodes:
        node_ids = {str(n.get("id")) for n in nodes}
        dot_lines = ["digraph ResearchGraph {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fillcolor="#EAF2F8"];']
        for node in nodes:
            node_id = str(node.get("id", "")).replace('"', "'")
            label = str(node.get("label", node.get("id", ""))).replace('"', "'")
            node_type = str(node.get("type", "Entity")).replace('"', "'")
            dot_lines.append(f'"{node_id}" [label="{label}\\n({node_type})"];')
        for edge in edges:
            source, target = str(edge.get("source")), str(edge.get("target"))
            if source in node_ids and target in node_ids:
                relation = str(edge.get("relation", "")).replace('"', "'")
                dot_lines.append(f'"{source}" -> "{target}" [label="{relation}"];')
        dot_lines.append("}")
        st.graphviz_chart("\n".join(dot_lines), use_container_width=True)
        st.markdown("**Relationships and evidence**")
        st.dataframe(pd.DataFrame(edges), use_container_width=True, hide_index=True) if edges else st.caption("No relationships were extracted.")
    else:
        st.info("No knowledge-graph entities were extracted.")
    st.markdown("**Notes**")
    _show_list(result.get("notes", []))


def _render_math_analysis(result):
    for paper in result.get("papers", []):
        st.markdown(f"### {paper.get('paper', 'Research paper')}")
        equations = paper.get("equations", [])
        if equations:
            for equation in equations:
                with st.expander(equation.get("name") or "Equation", expanded=True):
                    st.code(equation.get("expression_as_extracted", ""), language="text")
                    st.write(_clean(equation.get("purpose")))
                    _show_list(equation.get("variables", []), "No variable definitions were extracted.")
                    if equation.get("page"):
                        st.caption(f"PDF page {equation['page']}")
        else:
            st.info("No equations were extracted from the supplied text.")
        st.markdown("**Algorithms**")
        for algorithm in paper.get("algorithms", []):
            st.markdown(f"**{algorithm.get('name') or 'Algorithm'}**")
            st.write("Inputs: " + ", ".join(map(str, algorithm.get("inputs", []))))
            _show_list(algorithm.get("steps", []))
            st.write("Outputs: " + ", ".join(map(str, algorithm.get("outputs", []))))
        st.markdown("**Undefined symbols and formatting warnings**")
        _show_list(paper.get("undefined_symbols", []) + paper.get("formatting_warnings", []))


def _render_analysis_result(result, feature):
    """Render structured analysis JSON as a readable research report."""
    renderers = {
        "paper_summary": _render_paper_summary,
        "methodology": _render_methodology,
        "reproducibility": _render_reproducibility,
        "benchmark": _render_benchmark,
        "synthesis": _render_synthesis,
        "paper_to_code": _render_paper_to_code,
        "citation_context": _render_citation_context,
        "knowledge_graph": _render_knowledge_graph,
        "math_analysis": _render_math_analysis,
    }
    renderer = renderers.get(feature)
    if renderer:
        renderer(result)
    else:
        st.info("This analysis type does not yet have a dedicated report layout.")


st.title("🔬 DocuMind Research")
st.caption("A shared library for organizing, understanding, comparing and synthesizing research papers.")

with st.sidebar:
    st.header("Research workspace")
    st.write("Upload papers, organize collections, then run focused analyses.")
    st.info("AI analyses are generated from extracted PDF text. Always verify findings and page references against the original paper.")

library_tab, collection_tab, analysis_tab = st.tabs(
    ["📚 Paper library", "🗂️ Collections", "🧪 Research analysis"]
)

with library_tab:
    st.subheader("Research paper library")
    st.caption("PDFs uploaded in Papers Discussions appear here automatically. You can also import papers directly below.")
    uploaded = st.file_uploader(
        "Upload PDF papers",
        type=["pdf"],
        accept_multiple_files=True,
        key="research_pdf_upload",
        help="Text-based PDFs are supported. Scanned PDFs require OCR, which is not included in this release.",
    )
    if uploaded:
        st.caption(f"{len(uploaded)} PDF(s) selected. Metadata can be edited after import.")
        if st.button("Import selected papers", type="primary"):
            imported, duplicates, failures = 0, 0, []
            progress = st.progress(0)
            for index, file in enumerate(uploaded):
                try:
                    _, created = add_paper(file.getvalue(), file.name)
                    imported += int(created)
                    duplicates += int(not created)
                except Exception as exc:
                    failures.append(f"{file.name}: {type(exc).__name__}: {exc}")
                progress.progress((index + 1) / len(uploaded))
            progress.empty()
            st.success(f"Imported {imported} paper(s); skipped {duplicates} duplicate(s).")
            for failure in failures:
                st.warning(failure)
            st.rerun()

    papers = list_papers()
    st.divider()
    st.subheader(f"Library ({len(papers)} papers)")
    search_text = st.text_input("Search title, author, year, DOI or keywords", key="library_search")
    filtered = [
        paper for paper in papers
        if search_text.lower() in " ".join(str(paper.get(k, "")) for k in (
            "title", "authors", "publication_year", "doi", "keywords", "filename"
        )).lower()
    ] if search_text else papers

    if filtered:
        st.dataframe(
            [{
                "Title": p["title"], "Authors": p["authors"], "Year": p["publication_year"],
                "Venue": p["venue"], "Pages": p["page_count"], "Filename": p["filename"],
            } for p in filtered],
            use_container_width=True, hide_index=True,
        )
        options = {f'{p["title"]} — {p["publication_year"] or "Year unknown"} ({p["filename"]})': p["paper_id"] for p in filtered}
        selected_label = st.selectbox("Edit paper metadata", list(options), key="edit_paper_select")
        selected_paper = get_paper(options[selected_label])
        if selected_paper:
            with st.form("edit_paper_metadata"):
                c1, c2 = st.columns(2)
                title = c1.text_input("Title", selected_paper["title"])
                authors = c2.text_input("Authors", selected_paper["authors"])
                year = c1.text_input("Publication year", selected_paper["publication_year"])
                venue = c2.text_input("Journal / conference", selected_paper["venue"])
                doi = c1.text_input("DOI", selected_paper["doi"])
                keywords = c2.text_input("Keywords (comma-separated)", selected_paper["keywords"])
                abstract = st.text_area("Abstract", selected_paper["abstract"], height=120)
                notes = st.text_area("Your notes", selected_paper["notes"], height=80)
                save_metadata = st.form_submit_button("Save metadata")
            if save_metadata:
                update_paper_metadata(selected_paper["paper_id"], {
                    "title": title, "authors": authors, "publication_year": year, "venue": venue,
                    "doi": doi, "keywords": keywords, "abstract": abstract, "notes": notes,
                })
                st.success("Paper metadata saved.")
                st.rerun()
            with st.expander("Preview extracted text"):
                st.text(selected_paper["text_content"][:6000])
            stored_path = Path(selected_paper["stored_path"])
            if stored_path.exists():
                st.download_button("Download original PDF", data=stored_path.read_bytes(), file_name=selected_paper["filename"], mime="application/pdf")
            if st.button("Delete this paper from library", type="secondary"):
                delete_paper(selected_paper["paper_id"])
                st.warning("Paper removed from the library.")
                st.rerun()
    else:
        st.info("No papers found. Upload one or more research PDFs to get started.")

with collection_tab:
    st.subheader("Organize papers into research collections")
    with st.form("create_collection_form"):
        collection_name = st.text_input("Collection name", placeholder="e.g. RAG evaluation methods")
        collection_description = st.text_area("Description (optional)")
        create_clicked = st.form_submit_button("Create collection")
    if create_clicked:
        try:
            create_collection(collection_name, collection_description)
            st.success("Collection created.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    papers = list_papers()
    collections = list_collections()
    if collections:
        labels = {f'{c["name"]} ({c["paper_count"]} papers)': c["collection_id"] for c in collections}
        selected_collection_label = st.selectbox("Choose collection", list(labels))
        collection_id = labels[selected_collection_label]
        if papers:
            paper_labels = {f'{p["title"]} — {p["filename"]}': p["paper_id"] for p in papers}
            chosen_labels = st.multiselect("Add papers to this collection", list(paper_labels))
            if st.button("Add selected papers to collection"):
                for label in chosen_labels:
                    add_paper_to_collection(collection_id, paper_labels[label])
                st.success("Collection updated.")
                st.rerun()
        members = papers_in_collection(collection_id)
        st.markdown("**Papers in this collection**")
        if members:
            st.dataframe([{"Title": p["title"], "Authors": p["authors"], "Year": p["publication_year"], "Filename": p["filename"]} for p in members], use_container_width=True, hide_index=True)
        else:
            st.info("This collection is empty.")
    else:
        st.info("Create a collection to group related papers.")

with analysis_tab:
    st.subheader("Research analysis")
    papers = list_papers()
    collections = list_collections()
    if not papers:
        st.info("Import research papers in the Paper library first.")
    else:
        mode = st.radio("Select papers from", ["Entire library", "A collection"], horizontal=True)
        available = papers
        if mode == "A collection" and collections:
            labels = {c["name"]: c["collection_id"] for c in collections}
            chosen_collection = st.selectbox("Collection", list(labels))
            available_ids = {p["paper_id"] for p in papers_in_collection(labels[chosen_collection])}
            available = [p for p in papers if p["paper_id"] in available_ids]
        elif mode == "A collection" and not collections:
            st.warning("Create a collection first.")
            available = []

        if available:
            paper_options = {f'{p["title"]} — {p["publication_year"] or "Year unknown"}': p["paper_id"] for p in available}
            chosen_paper_labels = st.multiselect("Choose papers to analyze (start with 1–3 papers for best results)", list(paper_options), default=list(paper_options)[:1])
            chosen_ids = [paper_options[label] for label in chosen_paper_labels]
            selected_papers = [get_paper(pid) for pid in chosen_ids]
            selected_papers = [p for p in selected_papers if p]
            st.caption("Large papers are limited to the first 18,000 extracted characters per paper per analysis. Select fewer papers for deeper coverage.")

            feature_labels = {spec["label"]: key for key, spec in FEATURES.items()}
            chosen_feature_label = st.selectbox("Research tool", list(feature_labels))
            feature = feature_labels[chosen_feature_label]
            st.write(FEATURES[feature]["description"])

            if st.button("Run analysis", type="primary", disabled=not selected_papers):
                with st.spinner(f"Running {chosen_feature_label.lower()}..."):
                    try:
                        result = run_research_analysis(feature, selected_papers)
                        st.session_state["research_last_result"] = result
                        st.session_state["research_last_feature"] = feature
                        st.session_state["research_last_title"] = chosen_feature_label
                        st.session_state["research_last_papers"] = [p["title"] for p in selected_papers]
                    except Exception as exc:
                        st.error(f"{type(exc).__name__}: {exc}")

            result = st.session_state.get("research_last_result")
            active_feature = st.session_state.get("research_last_feature")
            if result and active_feature:
                st.divider()
                st.subheader(st.session_state.get("research_last_title", "Analysis result"))
                st.caption("Sources: " + ", ".join(st.session_state.get("research_last_papers", [])))
                if result.get("_meta"):
                    st.caption(result["_meta"].get("grounding", ""))
                _render_analysis_result(result, active_feature)
                with st.expander("View raw analysis data (JSON)"):
                    st.json(result)
                st.download_button(
                    "Download analysis data (JSON)",
                    data=json.dumps(result, ensure_ascii=False, indent=2),
                    file_name=f"documind_{active_feature}_analysis.json",
                    mime="application/json",
                )
