import re

import io

import hashlib

import streamlit as st

import fitz

from pypdf import PdfReader

from src.documind.ingestion.pdf_parser import extract_chunks
from src.documind.evidence.highlighting import (
    get_words,
    apply_green_highlights,
    _highlight_tokens,
    _split_evidence_sentences,
    _sentence_evidence_score,
    highlight_normal_text,
    highlight_table_evidence,
    highlight_passage,
)

from src.documind.semantic_search import build_index, hybrid_search

from src.documind.generation import generate_answer, rewrite_question

from src.documind.vision import (
    extract_pdf_visuals,
    analyze_image,
    visual_to_text,
)

from src.documind.research_library import init_research_schema, add_paper

from src.documind.conversation_store import (

    init_db,

    create_conversation,

    list_conversations,

    add_message,

    get_messages,

    delete_conversation

)

# ============================================================

# 1. PAGE CONFIGURATION

# ============================================================

st.set_page_config(

    page_title="Papers Discussions | DocuMind Research",

    page_icon="📄",

    layout="wide"

)

# Initialize persistent conversation storage

init_db()
init_research_schema()

if "visual_analysis_cache" not in st.session_state:
    st.session_state["visual_analysis_cache"] = {}

if "conversation_id" not in st.session_state:

    st.session_state["conversation_id"] = None

if "conversation_document_id" not in st.session_state:

    st.session_state["conversation_document_id"] = None

if "show_pdf_viewer" not in st.session_state:

    st.session_state["show_pdf_viewer"] = False

if "selected_page" not in st.session_state:

    st.session_state["selected_page"] = None

st.title("📄 Papers Discussions")

st.write(

    "Upload a PDF, ask questions, and get AI-generated "

    "answers grounded in your document."

)

# ============================================================

# 2. PDF TEXT EXTRACTION AND CHUNKING

# ============================================================


# ============================================================

# 3. TEXT UTILITIES

# ============================================================


# ============================================================

# 4. APPLY GREEN HIGHLIGHTS

# ============================================================


# ============================================================

# 5. NORMAL TEXT HIGHLIGHTING

# ============================================================













# ============================================================

# 8. CLICKABLE CITATION RENDERING

# ============================================================

def render_answer_with_citations(answer, results):

    """Display the answer and make page citations clickable."""

    available_pages = {

        result["page"] for result in results

    }

    citation_pattern = re.compile(r"\[Page\s+(\d+)\]|【Page\s+(\d+)】", re.IGNORECASE)

    cursor = 0

    for index, match in enumerate(

        citation_pattern.finditer(answer)

    ):

        text_before = answer[cursor:match.start()]

        if text_before.strip():

            st.markdown(text_before)

        page_number = int(

            match.group(1) or match.group(2)

        )

        if page_number in available_pages:

            if st.button(

                f"📄 Open Page {page_number}",

                key=f"citation_{index}_{page_number}"

            ):

                st.session_state["selected_page"] = page_number

                st.rerun()

        else:

            st.caption(f"[Page {page_number}]")

        cursor = match.end()

    remaining_text = answer[cursor:]

    if remaining_text.strip():

        st.markdown(remaining_text)

# ============================================================

# ============================================================

# 9. MULTI-PDF UPLOAD, INDEXING, CONVERSATIONS, AND CHAT

# ============================================================

uploaded_pdfs = st.file_uploader(

    "Upload PDF documents",

    type=["pdf"],

    accept_multiple_files=True,

    help="Upload one or more PDFs. DocuMind will search across the full collection."

)

if not uploaded_pdfs:

    st.info("Upload one or more PDF documents to start.")

    st.stop()

try:

    # Read and identify every uploaded PDF by its content.

    documents = []

    for uploaded_pdf in uploaded_pdfs:

        pdf_bytes = uploaded_pdf.getvalue()

        if not pdf_bytes:

            st.warning(f"{uploaded_pdf.name} is empty and was skipped.")

            continue

        document_id = hashlib.sha256(pdf_bytes).hexdigest()

        # Every PDF added to a discussion is also registered in the shared
        # Research Workspace library. Content hashing prevents duplicate rows.
        try:
            add_paper(pdf_bytes, uploaded_pdf.name)
        except Exception as library_error:
            st.warning(
                f"The PDF is available for discussion, but could not be added "
                f"to Research Workspace: {library_error}"
            )

        documents.append({

            "document_id": document_id,

            "document_name": uploaded_pdf.name,

            "pdf_bytes": pdf_bytes,

        })

    if not documents:

        st.warning("No valid PDF files were uploaded.")

        st.stop()

    # Avoid duplicate copies of the same PDF content in one collection.

    unique_documents = {}

    for document in documents:

        unique_documents[document["document_id"]] = document

    documents = list(unique_documents.values())

    # Keep the legacy document ID for a single PDF so existing

    # single-document conversation histories remain available.

    sorted_document_ids = sorted(

        document["document_id"] for document in documents

    )

    if len(sorted_document_ids) == 1:

        collection_id = sorted_document_ids[0]

    else:

        collection_id = hashlib.sha256(

            "|".join(sorted_document_ids).encode("utf-8")

        ).hexdigest()

    collection_name = ", ".join(

        document["document_name"] for document in documents

    )

    if len(collection_name) > 450:

        collection_name = (

            f"{len(documents)} PDFs: "

            + ", ".join(d["document_name"] for d in documents[:3])

            + ", ..."

        )

    # Re-extract and re-index only when the uploaded collection changes.

    if st.session_state.get("active_collection_id") != collection_id:

        combined_chunks = []
        document_bytes = {}

        visual_cache = st.session_state["visual_analysis_cache"]

        for document in documents:
            document_id = document["document_id"]
            document_name = document["document_name"]
            pdf_bytes = document["pdf_bytes"]

            document_bytes[document_id] = pdf_bytes

            # 1. Extract normal PDF text
            with st.spinner(f"Extracting text from {document_name}..."):
                document_chunks = extract_chunks(
                    io.BytesIO(pdf_bytes),
                    document_name=document_name,
                    document_id=document_id,
                )

            combined_chunks.extend(document_chunks)

            # 2. Extract visual content from every PDF page
            with st.spinner(f"Extracting images and diagrams from {document_name}..."):
                visuals = extract_pdf_visuals(pdf_bytes)

            # 3. Analyze visuals and convert them into searchable chunks
            if visuals:
                st.write(
                    f"Found {len(visuals)} visual elements in {document_name}."
                )

                progress = st.progress(0)
                successful_analyses = 0

                for index, visual in enumerate(visuals):
                    image_id = visual["image_id"]

                    try:
                        # Reuse a previous analysis if this image was already processed
                        if image_id in visual_cache:
                            analysis = visual_cache[image_id]

                        else:
                            analysis = analyze_image(visual["image_bytes"])
                            visual_cache[image_id] = analysis

                        visual_chunk = visual_to_text(
                            visual,
                            analysis,
                            document_id=document_id,
                            document_name=document_name,
                        )

                        combined_chunks.append(visual_chunk)
                        successful_analyses += 1

                    except Exception as error:
                        st.warning(
                            f"Could not analyze visual on page "
                            f"{visual['page']} of {document_name}: {error}"
                        )

                    progress.progress((index + 1) / len(visuals))

                progress.empty()

                st.success(
                    f"Analyzed {successful_analyses} visual elements "
                    f"in {document_name}."
                )


        st.session_state["active_collection_id"] = collection_id

        st.session_state["active_documents"] = documents

        st.session_state["document_bytes"] = document_bytes

        st.session_state["chunks"] = combined_chunks

        for key in [

            "model", "embeddings", "bm25", "indexed_collection_id",

            "results", "answer", "has_support", "selected_page",

            "selected_document_id", "question", "reason",

        ]:

            st.session_state.pop(key, None)

        st.session_state["conversation_id"] = None

        st.session_state["conversation_document_id"] = None

        st.session_state["show_pdf_viewer"] = False

    chunks = st.session_state["chunks"]

    if not chunks:
        st.warning(
            "No usable text or visual content was extracted from these PDFs."
        )
        st.stop()

    st.success(

        f"Loaded {len(documents)} PDF(s) and extracted "

        f"{len(chunks)} text chunks."

    )

    with st.expander("Uploaded documents", expanded=False):

        for document in documents:

            doc_chunk_count = sum(

                1 for chunk in chunks

                if chunk["document_id"] == document["document_id"]

            )

            st.write(f"📄 **{document['document_name']}** — {doc_chunk_count} chunks")

    # ------------------------------------------------------------

    # 10. BUILD ONE COMBINED SEMANTIC + BM25 INDEX

    # ------------------------------------------------------------

    if st.session_state.get("indexed_collection_id") != collection_id:

        with st.spinner("Building combined search index..."):

            model, embeddings, bm25 = build_index(chunks)

            st.session_state["model"] = model

            st.session_state["embeddings"] = embeddings

            st.session_state["bm25"] = bm25

            st.session_state["indexed_collection_id"] = collection_id

        st.success("All uploaded PDFs indexed successfully!")

    # ------------------------------------------------------------

    # 11. CONVERSATION SIDEBAR

    # ------------------------------------------------------------

    if st.session_state.get("conversation_document_id") != collection_id:

        st.session_state["conversation_id"] = None

        st.session_state["conversation_document_id"] = collection_id

        st.session_state.pop("results", None)

        st.session_state.pop("has_support", None)

        st.session_state.pop("selected_page", None)

        st.session_state.pop("selected_document_id", None)

        st.session_state["show_pdf_viewer"] = False

    conversations = list_conversations(collection_id)

    with st.sidebar:

        st.title("💬 Conversations")

        if st.button("＋ New chat", use_container_width=True):

            new_id = create_conversation(collection_id, collection_name)

            st.session_state["conversation_id"] = new_id

            st.session_state["conversation_document_id"] = collection_id

            for key in ["results", "has_support", "selected_page", "selected_document_id"]:

                st.session_state.pop(key, None)

            st.session_state["show_pdf_viewer"] = False

            st.rerun()

        st.divider()

        st.caption("Conversations for this PDF collection")

        if conversations:

            for conversation in conversations:

                conversation_id_value = conversation["id"]

                is_active = (

                    conversation_id_value

                    == st.session_state.get("conversation_id")

                )

                if st.button(

                    ("● " if is_active else "") + conversation["title"],

                    key=f"conversation_{conversation_id_value}",

                    use_container_width=True,

                ):

                    st.session_state["conversation_id"] = conversation_id_value

                    st.session_state["conversation_document_id"] = collection_id

                    for key in ["results", "has_support", "selected_page", "selected_document_id"]:

                        st.session_state.pop(key, None)

                    st.session_state["show_pdf_viewer"] = False

                    st.rerun()

        else:

            st.info("No conversations yet. Start a new chat!")

        current_conversation_id = st.session_state.get("conversation_id")

        if current_conversation_id is not None:

            st.divider()

            if st.button("🗑️ Delete current conversation", use_container_width=True):

                delete_conversation(current_conversation_id)

                st.session_state["conversation_id"] = None

                for key in ["results", "has_support", "selected_page", "selected_document_id"]:

                    st.session_state.pop(key, None)

                st.session_state["show_pdf_viewer"] = False

                st.rerun()

    # ------------------------------------------------------------

    # 12. CHAT AND OPTIONAL SIDE-BY-SIDE PDF VIEWER

    # ------------------------------------------------------------

    conversation_id = st.session_state.get("conversation_id")

    if not conversation_id:

        st.info("Start a new chat using the button in the sidebar.")

    else:

        if st.session_state.get("show_pdf_viewer", False):

            chat_col, pdf_col = st.columns([1.05, 0.95], gap="large")

        else:

            chat_col = st.container()

            pdf_col = None

        with chat_col:

            st.subheader("💬 Document conversation")

            messages = get_messages(conversation_id)

            for message in messages:

                with st.chat_message(message["role"]):

                    st.markdown(message["content"])

            if st.session_state.get("last_error"):

                st.error(st.session_state["last_error"])

            question = st.chat_input(

                "Ask a question across your uploaded PDFs...",

                key=f"chat_input_{conversation_id}",

            )

            if question and question.strip():

                question = question.strip()

                add_message(conversation_id, "user", question)

                with st.chat_message("assistant"):

                    try:

                        previous_history = get_messages(conversation_id)[:-1]

                        with st.spinner("Understanding your question..."):

                            standalone_question = rewrite_question(

                                question,

                                previous_history,

                            )

                        with st.spinner("Searching all uploaded PDFs..."):

                            retrieved_results = hybrid_search(

                                standalone_question,

                                chunks,

                                st.session_state["model"],

                                st.session_state["embeddings"],

                                st.session_state["bm25"],

                                top_k=8,

                                semantic_weight=0.5,

                                bm25_weight=0.5,

                            )

                        if retrieved_results:

                            with st.spinner("Generating answer..."):

                                answer_result = generate_answer(

                                    standalone_question,

                                    retrieved_results,

                                )
                                with st.expander("Evidence provenance — debugging"):
                                    for evidence in answer_result.get("supporting_evidence", []):
                                        st.write({
                                            "document": evidence["document_name"],
                                            "page": evidence["page"],
                                            "evidence_type": evidence["evidence_type"],
                                            "source_type": evidence["source_type"],
                                            "image_id": evidence["image_id"],
                                        })

                            answer = answer_result["answer"]

                            supporting_sources = {

                                (source["document_id"], source["page"])

                                for source in answer_result.get("supporting_sources", [])

                            }

                            supporting_results = [

                                result for result in retrieved_results

                                if (

                                    result["document_id"],

                                    result["page"],

                                ) in supporting_sources

                            ]

                            has_support = (

                                answer_result["is_answerable"]

                                and bool(supporting_results)

                            )

                        else:

                            answer = (

                                "I couldn't find relevant evidence "

                                "in the uploaded PDFs to answer this question."

                            )

                            supporting_results = []

                            has_support = False

                            answer_result = {

                                "reason": "No relevant passages were retrieved."

                            }

                        st.markdown(answer)

                        if has_support:

                            source_pairs = sorted({

                                (result["document_id"], result["document_name"], result["page"])

                                for result in supporting_results

                            }, key=lambda item: (item[1].lower(), item[2]))

                            st.markdown("**Sources:**")

                            source_cols = st.columns(min(len(source_pairs), 3))

                            for source_index, (doc_id, doc_name, page_number) in enumerate(source_pairs):

                                with source_cols[source_index % len(source_cols)]:

                                    if st.button(

                                        f"📄 {doc_name} — Page {page_number}",

                                        key=(

                                            f"answer_source_{conversation_id}_"

                                            f"{doc_id[:10]}_{page_number}_{len(messages)}"

                                        ),

                                    ):

                                        st.session_state["selected_document_id"] = doc_id

                                        st.session_state["selected_page"] = page_number

                                        st.session_state[f"pdf_page_selector_{doc_id[:12]}"] = page_number

                                        st.session_state["show_pdf_viewer"] = True

                                        st.rerun()

                            st.session_state["results"] = supporting_results

                            first_source = source_pairs[0]

                            st.session_state["selected_document_id"] = first_source[0]

                            st.session_state["selected_page"] = first_source[2]

                            st.session_state[f"pdf_page_selector_{first_source[0][:12]}"] = first_source[2]

                        else:

                            st.info(

                                "The uploaded PDFs do not contain sufficient "

                                "evidence to answer this question."

                            )

                            reason = answer_result.get("reason", "")

                            if reason:

                                st.caption(f"Reason: {reason}")

                            st.session_state["results"] = []

                        st.session_state["has_support"] = has_support

                        add_message(conversation_id, "assistant", answer)

                    except Exception as error:

                        st.session_state["last_error"] = (

                            f"{type(error).__name__}: {error}"

                        )

                        st.session_state["results"] = []

                        st.session_state["has_support"] = False

                st.rerun()

                # Persistent source citation buttons

                results = st.session_state.get("results", [])

                has_support = st.session_state.get("has_support", False)

                if results and has_support:

                    st.markdown("**Sources:**")

                    source_pairs = sorted({

                        (

                            result["document_id"],

                            result["document_name"],

                            result["page"],

                        )

                        for result in results

                    }, key=lambda item: (item[1].lower(), item[2]))

                    source_cols = st.columns(min(len(source_pairs), 3))

                    for index, (doc_id, doc_name, page_number) in enumerate(source_pairs):

                        with source_cols[index % len(source_cols)]:

                            if st.button(

                                f"📄 {doc_name} — Page {page_number}",

                                key=f"persistent_source_{doc_id[:10]}_{page_number}",

                                use_container_width=True,

                            ):

                                st.session_state["selected_document_id"] = doc_id

                                st.session_state["selected_page"] = page_number

                                st.session_state[

                                    f"pdf_page_selector_{doc_id[:12]}"

                                ] = page_number

                                st.session_state["show_pdf_viewer"] = True

                                st.rerun()

            # Supporting evidence

            results = st.session_state.get("results", [])

            has_support = st.session_state.get("has_support", False)

            if results and has_support:

                st.divider()

                st.subheader("📚 Supporting evidence")

                for index, result in enumerate(results):

                    page_number = result["page"]

                    document_name = result["document_name"]

                    with st.expander(

                        f"{document_name} — Page {page_number} "

                        f"— RRF score {result['score']:.4f}"

                    ):

                        st.write(result["text"])

                        if st.button(

                            f"Open {document_name}, page {page_number}",

                            key=(

                                f"chat_evidence_{conversation_id}_"

                                f"{index}_{result['document_id'][:10]}"

                            ),

                        ):

                            st.session_state["selected_document_id"] = result["document_id"]

                            st.session_state["selected_page"] = page_number

                            st.session_state[

                                f"pdf_page_selector_{result['document_id'][:12]}"

                            ] = page_number

                            st.session_state["show_pdf_viewer"] = True

                            st.rerun()

        # --------------------------------------------------------

        # 13. RIGHT-SIDE PDF VIEWER

        # --------------------------------------------------------

        if pdf_col is not None:

            with pdf_col:

                viewer_header, close_col = st.columns([0.82, 0.18])

                with viewer_header:

                    selected_doc_id = st.session_state.get("selected_document_id")

                    selected_doc = next(

                        (

                            doc for doc in documents

                            if doc["document_id"] == selected_doc_id

                        ),

                        None,

                    )

                    viewer_title = (

                        selected_doc["document_name"]

                        if selected_doc else "Source PDF"

                    )

                    st.subheader(f"📄 {viewer_title}")

                with close_col:

                    if st.button("✕", key="close_pdf_viewer", help="Close PDF viewer"):

                        st.session_state["show_pdf_viewer"] = False

                        st.rerun()

                results = st.session_state.get("results", [])

                selected_doc_id = st.session_state.get("selected_document_id")

                selected_page = st.session_state.get("selected_page")

                if selected_doc_id not in st.session_state["document_bytes"]:

                    st.warning("Select a source citation to open its PDF.")

                else:

                    pdf_bytes = st.session_state["document_bytes"][selected_doc_id]

                    document = fitz.open(stream=pdf_bytes, filetype="pdf")

                    try:

                        if selected_page is None:

                            selected_page = 1

                        if 1 <= selected_page <= len(document):

                            page = document.load_page(selected_page - 1)

                            total_highlights = 0

                            current_question = next(

                                (

                                    message["content"]

                                    for message in reversed(get_messages(conversation_id))

                                    if message["role"] == "user"

                                ),

                                "",

                            )

                            current_answer = next(
                                (
                                    message["content"]
                                    for message in reversed(get_messages(conversation_id))
                                    if message["role"] == "assistant"
                                ),
                                "",
                            )

                            for result in results:

                                if (

                                    result["document_id"] == selected_doc_id

                                    and result["page"] == selected_page

                                ):

                                    total_highlights += highlight_passage(

                                        page,

                                        result["text"],

                                        current_question,
                                        current_answer,
                                    )

                            st.caption(f"Page {selected_page} of {len(document)}")

                            next_page = st.selectbox(

                                "Go to page",

                                options=list(range(1, len(document) + 1)),

                                index=selected_page - 1,

                                label_visibility="collapsed",

                                key=f"pdf_page_selector_{selected_doc_id[:12]}",

                            )

                            if next_page != selected_page:

                                st.session_state["selected_page"] = next_page

                                st.rerun()

                            if total_highlights > 0:

                                st.success("Supporting evidence highlighted in green.")

                            pixmap = page.get_pixmap(

                                matrix=fitz.Matrix(1.5, 1.5),

                                alpha=False,

                                annots=True,

                            )

                            st.image(

                                pixmap.tobytes("png"),

                                use_container_width=True,

                            )

                        else:

                            st.warning("The selected page does not exist.")

                    finally:

                        document.close()

except Exception as error:

    st.error(

        "An error occurred while processing the uploaded PDFs: "

        f"{type(error).__name__}: {error}"

    )

    st.exception(error)
