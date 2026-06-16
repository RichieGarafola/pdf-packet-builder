from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import logging
from typing import Protocol, Sequence, cast

import streamlit as st

from services.pdf_service import (
    PdfIssue,
    PdfMergeResult,
    PdfServiceError,
    PdfSource,
    UploadLimits,
    merge_pdfs,
    validate_source,
)
from utils.file_utils import (
    DEFAULT_OUTPUT_FILENAME,
    format_file_size,
    sanitize_pdf_filename,
)

APP_TITLE = "PDF Packet Builder"
APP_SUBTITLE = (
    "Upload and merge documents into a single professional packet for review, "
    "delivery, or internal distribution."
)
UPLOAD_LIMITS = UploadLimits(
    max_file_count=25,
    max_file_size_bytes=25 * 1024 * 1024,
    max_total_size_bytes=100 * 1024 * 1024,
)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UploadViewModel:
    display_files: tuple["DisplayFile", ...]
    sources: tuple[PdfSource, ...]
    total_files: int
    total_size_bytes: int
    batch_error: str | None
    validation_issues: tuple[PdfIssue, ...]

    @property
    def has_uploads(self) -> bool:
        return self.total_files > 0

    @property
    def ready_file_count(self) -> int:
        if self.batch_error:
            return 0
        return max(self.total_files - len(self.validation_issues), 0)

    @property
    def can_merge(self) -> bool:
        return self.has_uploads and self.batch_error is None

    @property
    def validation_label(self) -> str:
        if not self.has_uploads:
            return "Waiting"
        if self.batch_error:
            return "Blocked"
        if self.validation_issues:
            return "Review"
        return "Ready"

    @classmethod
    def empty(cls) -> "UploadViewModel":
        return cls(
            display_files=(),
            sources=(),
            total_files=0,
            total_size_bytes=0,
            batch_error=None,
            validation_issues=(),
        )


@dataclass(frozen=True, slots=True)
class DisplayFile:
    name: str
    size_bytes: int

    @property
    def display_name(self) -> str:
        return self.name.strip() or "unnamed.pdf"


class StreamlitUploadedFile(Protocol):
    name: str
    size: int

    def getbuffer(self) -> memoryview:
        ...

    def seek(self, offset: int, whence: int = 0) -> int:
        ...


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_styles()
    render_sidebar()

    with st.container():
        render_header()

    st.divider()

    controls_column, status_column = st.columns([1.18, 0.92], gap="small")

    with controls_column:
        with st.container():
            render_section_heading(
                "Upload and Configure",
                "Build your packet by uploading PDF files in the exact order you want them merged.",
            )
            raw_uploads = st.file_uploader(
                "Upload PDF files",
                type=["pdf"],
                accept_multiple_files=True,
                help="Upload up to 25 PDF files. Upload order becomes merge order.",
            )

    upload_state = build_upload_view_model(raw_uploads)
    sync_ui_state(upload_state)

    merge_result = get_merge_result()

    with controls_column:
        with st.container():
            render_upload_feedback(upload_state)
            input_column, action_column = st.columns([1.45, 0.7], gap="small")
            with input_column:
                output_name = st.text_input(
                    "Output filename",
                    value=DEFAULT_OUTPUT_FILENAME,
                    help="A .pdf extension will be enforced automatically.",
                )
            with action_column:
                st.markdown('<div class="cta-offset"></div>', unsafe_allow_html=True)
                merge_clicked = st.button(
                    "Merge PDFs",
                    type="primary",
                    disabled=not upload_state.can_merge,
                    use_container_width=True,
                )

            if merge_clicked:
                merge_result = execute_merge(upload_state)

    with status_column:
        with st.container():
            render_status_panel(upload_state, merge_result)

    st.divider()

    with st.container():
        render_output_section(merge_result, output_name)

    render_footer()


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f6f8fb 0%, #edf2f7 100%);
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1rem;
            padding-bottom: 1rem;
        }

        .hero-card {
            background: linear-gradient(135deg, #0f2742 0%, #1e4d72 100%);
            border-radius: 18px;
            padding: 1.1rem 1.35rem;
            color: #ffffff;
            box-shadow: 0 16px 34px rgba(15, 39, 66, 0.16);
        }

        .eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            color: #dbe7f3;
            margin-bottom: 0.3rem;
        }

        .hero-title {
            color: #ffffff;
            font-size: 2.05rem;
            line-height: 1.05;
            font-weight: 700;
            margin: 0;
        }

        .hero-subtitle {
            color: #e2e8f0;
            font-size: 0.96rem;
            line-height: 1.45;
            max-width: 48rem;
            margin-top: 0.45rem;
        }

        .section-title {
            color: #0f172a;
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.15rem;
        }

        .section-copy {
            color: #475569;
            font-size: 0.91rem;
            margin-bottom: 0.65rem;
        }

        .file-row {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: center;
            padding: 0.55rem 0.75rem;
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #dbe4ee;
            border-radius: 12px;
            margin-bottom: 0.4rem;
        }

        .file-row-left {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            min-width: 0;
        }

        .file-index {
            color: #0f4c81;
            background: #e7f0f8;
            border-radius: 999px;
            font-size: 0.73rem;
            font-weight: 700;
            line-height: 1;
            padding: 0.28rem 0.45rem;
            white-space: nowrap;
        }

        .file-name {
            color: #0f172a;
            font-weight: 600;
            font-size: 0.92rem;
            overflow-wrap: anywhere;
        }

        .file-size {
            color: #475569;
            font-size: 0.86rem;
            white-space: nowrap;
        }

        .footer-note {
            color: #64748b;
            text-align: center;
            font-size: 0.82rem;
            padding-top: 0.4rem;
        }

        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.84);
            border: 1px solid #dbe4ee;
            border-radius: 14px;
            padding: 0.5rem 0.7rem;
        }

        div[data-testid="stFileUploader"] {
            background: rgba(255, 255, 255, 0.78);
            border: 1px dashed #8aa4bc;
            border-radius: 14px;
            padding: 0.3rem 0.45rem;
        }

        div[data-testid="stFileUploaderDropzone"] {
            padding: 0.8rem 0.7rem;
        }

        div[data-testid="stAlert"] {
            padding: 0.45rem 0.75rem;
            border-radius: 12px;
            margin-bottom: 0.45rem;
        }

        div[data-testid="stAlert"] p {
            font-size: 0.9rem;
        }

        div[data-testid="stMetricLabel"] p {
            color: #64748b;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        div[data-testid="stMetricValue"] {
            color: #0f172a;
            font-size: 1.2rem;
            font-weight: 700;
        }

        div[data-testid="stTextInputRootElement"] > div > div input {
            background: rgba(255, 255, 255, 0.88);
            min-height: 2.6rem;
        }

        .stButton > button,
        .stDownloadButton > button {
            min-height: 2.7rem;
            border-radius: 10px;
            font-weight: 600;
        }

        .stButton > button {
            background: #0f4c81;
            border: 1px solid #0f4c81;
            color: #ffffff;
        }

        .stButton > button:disabled {
            background: #cbd5e1;
            border-color: #cbd5e1;
            color: #475569;
        }

        .stDownloadButton > button {
            background: #0f172a;
            border: 1px solid #0f172a;
            color: #ffffff;
        }

        .cta-offset {
            height: 1.55rem;
        }

        hr {
            margin: 0.75rem 0 0.85rem;
            border-color: #d7e0ea;
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 0.8rem;
            padding-bottom: 0.8rem;
        }

        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] li {
            font-size: 0.87rem;
            line-height: 1.45;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            margin-top: 0.25rem;
            margin-bottom: 0.2rem;
        }

        [data-testid="stSidebar"] hr {
            margin: 0.5rem 0 0.55rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="eyebrow">Document Assembly Tool</div>
            <h1 class="hero-title">{html.escape(APP_TITLE)}</h1>
            <div class="hero-subtitle">{html.escape(APP_SUBTITLE)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    st.sidebar.markdown("### PDF Packet Builder")
    st.sidebar.caption("Create a single polished packet without manual desktop assembly.")
    st.sidebar.divider()

    st.sidebar.markdown(
        "**Workflow**  \n"
        "1. Upload PDF files  \n"
        "2. Confirm order and filename  \n"
        "3. Merge and download"
    )
    st.sidebar.divider()

    st.sidebar.markdown(
        "**Limits**  \n"
        f"{UPLOAD_LIMITS.max_file_count} files max  \n"
        f"{format_file_size(UPLOAD_LIMITS.max_file_size_bytes)} per file  \n"
        f"{format_file_size(UPLOAD_LIMITS.max_total_size_bytes)} total"
    )


def render_section_heading(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="section-title">{html.escape(title)}</div>
        <div class="section-copy">{html.escape(subtitle)}</div>
        """,
        unsafe_allow_html=True,
    )


def build_upload_view_model(
    raw_uploads: Sequence[StreamlitUploadedFile] | None,
) -> UploadViewModel:
    if not raw_uploads:
        return UploadViewModel.empty()

    uploaded_files = cast(Sequence[StreamlitUploadedFile], raw_uploads)
    total_size_bytes = sum(file.size for file in uploaded_files)
    display_files = tuple(build_display_files(uploaded_files))
    batch_error = validate_uploaded_file_batch(uploaded_files, total_size_bytes)

    if batch_error is not None:
        return UploadViewModel(
            display_files=display_files,
            sources=(),
            total_files=len(uploaded_files),
            total_size_bytes=total_size_bytes,
            batch_error=batch_error,
            validation_issues=(),
        )

    sources = tuple(build_pdf_sources(uploaded_files))
    validation_issues = tuple(
        issue
        for source in sources
        if (issue := validate_source(source, UPLOAD_LIMITS)) is not None
    )

    return UploadViewModel(
        display_files=display_files,
        sources=sources,
        total_files=len(uploaded_files),
        total_size_bytes=total_size_bytes,
        batch_error=None,
        validation_issues=validation_issues,
    )


def build_pdf_sources(uploaded_files: Sequence[StreamlitUploadedFile]) -> list[PdfSource]:
    sources: list[PdfSource] = []
    for file in uploaded_files:
        file.seek(0)
        sources.append(
            PdfSource(
                name=file.name,
                file=file,
                signature=hashlib.sha256(file.getbuffer()).hexdigest(),
            )
        )
    return sources


def build_display_files(uploaded_files: Sequence[StreamlitUploadedFile]) -> list[DisplayFile]:
    return [DisplayFile(name=file.name, size_bytes=file.size) for file in uploaded_files]


def validate_uploaded_file_batch(
    uploaded_files: Sequence[StreamlitUploadedFile],
    total_size_bytes: int,
) -> str | None:
    if len(uploaded_files) > UPLOAD_LIMITS.max_file_count:
        return f"Too many files uploaded. The limit is {UPLOAD_LIMITS.max_file_count} files."

    if total_size_bytes > UPLOAD_LIMITS.max_total_size_bytes:
        return (
            "Total upload size exceeds the app limit of "
            f"{format_file_size(UPLOAD_LIMITS.max_total_size_bytes)}."
        )

    return None


def render_upload_feedback(upload_state: UploadViewModel) -> None:
    if not upload_state.has_uploads:
        st.info("Upload PDF files to begin. The upload order becomes the merge order.")
        return

    st.success(
        f"{upload_state.total_files} file(s) uploaded | "
        f"{format_file_size(upload_state.total_size_bytes)} total"
    )

    if upload_state.batch_error:
        st.error(upload_state.batch_error)
        return

    if upload_state.validation_issues:
        st.warning(
            f"{upload_state.ready_file_count} file(s) are ready. "
            f"{len(upload_state.validation_issues)} file(s) may be skipped during merge."
        )
    else:
        st.info("All uploaded files are within the supported limits and ready to merge.")


def render_status_panel(
    upload_state: UploadViewModel,
    merge_result: PdfMergeResult | None,
) -> None:
    render_section_heading(
        "Packet Status",
        "Review upload volume, validation state, and the current file queue before merging.",
    )

    metric_row_one = st.columns(2, gap="small")
    with metric_row_one[0]:
        st.metric("Total files", upload_state.total_files)
    with metric_row_one[1]:
        st.metric("Total size", format_file_size(upload_state.total_size_bytes))
    metric_row_two = st.columns(2, gap="small")
    with metric_row_two[0]:
        st.metric("Ready files", upload_state.ready_file_count)
    with metric_row_two[1]:
        st.metric("Validation", upload_state.validation_label)

    if not upload_state.has_uploads:
        st.info("Your uploaded files and validation details will appear here.")
    elif upload_state.batch_error:
        st.warning(upload_state.batch_error)
    elif upload_state.validation_issues:
        st.warning(
            f"{len(upload_state.validation_issues)} file(s) need attention before merge."
        )
        for issue in upload_state.validation_issues:
            st.write(f"- {issue.file_name}: {issue.message}")
    else:
        st.info("All uploaded files currently pass the app's pre-merge checks.")

    if merge_result is not None and merge_result.skipped_files:
        st.warning(f"{len(merge_result.skipped_files)} file(s) were skipped in the latest merge.")

    st.divider()
    st.markdown("##### File Queue")
    render_file_list(upload_state.display_files)


def render_file_list(display_files: Sequence[DisplayFile]) -> None:
    if not display_files:
        st.info("No files uploaded yet.")
        return

    for index, display_file in enumerate(display_files, start=1):
        st.markdown(
            f"""
            <div class="file-row">
                <div class="file-row-left">
                    <div class="file-index">{index}</div>
                    <div class="file-name">{html.escape(display_file.display_name)}</div>
                </div>
                <div class="file-size">{format_file_size(display_file.size_bytes)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def execute_merge(upload_state: UploadViewModel) -> PdfMergeResult | None:
    with st.spinner("Merging PDFs..."):
        try:
            merge_result = merge_pdfs(upload_state.sources, limits=UPLOAD_LIMITS)
        except PdfServiceError as exc:
            st.session_state.pop("merge_result", None)
            logger.error(
                "merge_failed file_count=%s total_size_bytes=%s error=%s",
                upload_state.total_files,
                upload_state.total_size_bytes,
                exc,
            )
            st.error(f"Merge failed. {exc}")
            return None

    st.session_state["merge_result"] = merge_result
    return merge_result


def render_output_section(
    merge_result: PdfMergeResult | None,
    output_name: str,
) -> None:
    render_section_heading(
        "Merged Output",
        "Download the completed packet once the merge finishes.",
    )

    if merge_result is None:
        st.info("Your merged PDF will appear here after you click Merge PDFs.")
        return

    safe_output_name = sanitize_pdf_filename(output_name)

    metric_column_one, metric_column_two, metric_column_three = st.columns(3)
    with metric_column_one:
        st.metric("Merged files", len(merge_result.merged_files))
    with metric_column_two:
        st.metric("Total pages", merge_result.total_pages)
    with metric_column_three:
        st.metric("Output size", format_file_size(merge_result.output_size_bytes))

    summary_column, download_column = st.columns([1.15, 0.85], gap="small")
    with summary_column:
        st.success(f"Packet ready for download: {safe_output_name}")
    with download_column:
        st.download_button(
            label="Download merged PDF",
            data=merge_result.content,
            file_name=safe_output_name,
            mime="application/pdf",
            use_container_width=True,
        )

    if merge_result.skipped_files:
        st.warning("Some uploaded files were excluded from the final packet.")
        for issue in merge_result.skipped_files:
            st.write(f"- {issue.file_name}: {issue.message}")


def sync_ui_state(upload_state: UploadViewModel) -> None:
    if not upload_state.has_uploads or upload_state.batch_error:
        clear_merge_result()
        return

    upload_signature = build_upload_signature(upload_state.sources)
    if st.session_state.get("upload_signature") != upload_signature:
        logger.info(
            "uploaded_files_received file_count=%s total_size_bytes=%s",
            upload_state.total_files,
            upload_state.total_size_bytes,
        )
    sync_merge_result(upload_signature)


def get_merge_result() -> PdfMergeResult | None:
    merge_result = st.session_state.get("merge_result")
    if isinstance(merge_result, PdfMergeResult):
        return merge_result
    return None


def build_upload_signature(
    sources: Sequence[PdfSource],
) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        (
            source.display_name,
            source.size_bytes,
            source.signature,
        )
        for source in sources
    )


def sync_merge_result(upload_signature: tuple[tuple[str, int, str], ...]) -> None:
    current_signature = st.session_state.get("upload_signature")
    if current_signature != upload_signature:
        st.session_state["upload_signature"] = upload_signature
        st.session_state.pop("merge_result", None)


def clear_merge_result() -> None:
    st.session_state.pop("merge_result", None)
    st.session_state.pop("upload_signature", None)


def render_footer() -> None:
    st.markdown(
        """
        <div class="footer-note">
            Clean packet assembly for stakeholder-ready document workflows.
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
