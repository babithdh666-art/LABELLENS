from __future__ import annotations

import hashlib
import shutil
from io import BytesIO
from pathlib import Path

import pytesseract
import os

pytesseract.pytesseract.tesseract_cmd = os.getenv(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError
from pytesseract import TesseractNotFoundError

from field_detection import (
    DETECTED,
    MANUAL_REVIEW,
    NOT_DETECTED,
    FieldResult,
    validate_label_text,
)
from samples import SAMPLE_LABELS


st.set_page_config(page_title="LabelLens", layout="wide")
st.markdown("""
<style>
    @import url(
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
    );

    .stApp {
        background-color: #F5F7FB;
        color: #172033;
        font-family: 'Inter', sans-serif;
    }

    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5EAF2;
    }

    h1, h2, h3 {
        color: #172033;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E3EAF2;
        padding: 20px;
        border-radius: 14px;
        box-shadow: 0 3px 12px rgba(20, 40, 80, 0.04);
    }

    div[data-testid="stMetricLabel"] {
        color: #64748B;
        font-weight: 600;
    }

    div[data-testid="stMetricValue"] {
        color: #0F766E;
        font-weight: 800;
    }

    div[data-testid="stButton"] > button[kind="primary"] {
        background: #0F766E;
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        padding: 0.65rem 1.2rem;
        transition: background 0.2s ease;
    }

    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #115E59;
        color: white;
        border: none;
    }

    div[data-testid="stFileUploader"] {
        background: #FFFFFF;
        border: 1px dashed #99B8B5;
        border-radius: 14px;
        padding: 12px;
    }

    div[data-testid="stTextArea"] textarea {
        border-radius: 10px;
        border: 1px solid #D7E0EB;
        background: #FFFFFF;
    }

    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    hr {
        border-color: #E3EAF2;
    }

    #MainMenu, footer {
        visibility: hidden;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding: 12px 0 28px 0;">
    <div style="font-size: 13px; font-weight: 600; color: #0F766E;
                letter-spacing: 1.5px; text-transform: uppercase;">
        PRODUCT INTELLIGENCE
    </div>
    <h1 style="font-size: 44px; font-weight: 800;
               letter-spacing: -1.8px; margin: 8px 0 10px 0;
               color: #172033; line-height: 1.15;">
        Label<span style="color: #0F766E;">Lens</span>
    </h1>
    <p style="font-size: 16px; color: #64748B;
              margin: 0; line-height: 1.7; max-width: 650px;">
        Understand product labels at a glance.
        Extract essential details, identify missing information,
        and review potential issues in seconds.
    </p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Choose a starting point")
    mode = st.radio(
        "Input method",
        ("Upload a label", "Try a sample"),
        label_visibility="collapsed",
    )
    st.divider()
    st.caption(
        "LabelLens uses local OCR and transparent text-matching rules. "
        "Optional GroqCloud AI receives only the text you submit for analysis; "
        "uploaded images are not sent to Groq."
    )


def load_uploaded_image(uploaded_file) -> Image.Image:
    """Validate an uploaded image and return an orientation-corrected RGB copy."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("Please choose a JPG, JPEG, or PNG image.")

    raw_bytes = uploaded_file.getvalue()
    try:
        with Image.open(BytesIO(raw_bytes)) as source:
            source.verify()
        with Image.open(BytesIO(raw_bytes)) as source:
            return ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError(
            "This image could not be opened. Try another clear JPG or PNG."
        ) from error


def run_ocr(image: Image.Image) -> tuple[str, str | None]:
    """Return recognized text and an optional user-facing OCR error."""
    try:
        text = pytesseract.image_to_string(image, lang="eng")
    except TesseractNotFoundError:
        return "", (
            "The Tesseract OCR engine is not installed or is not on PATH. "
            "Install it using the steps in README.md, then restart LabelLens. "
            "You can still paste or type label text below."
        )
    except Exception:
        return "", (
            "OCR could not read this image. Try a sharper, well-lit image or "
            "paste the label text below."
        )

    if not text.strip():
        return "", (
            "No text was recognized. Try a sharper, well-lit image or paste "
            "the label text below."
        )
    return text, None


def report_text(
    results: list[FieldResult],
    original_text: str,
    source_label: str,
    is_sample: bool,
) -> str:
    detected_count = sum(result.status == DETECTED for result in results)
    missing_count = sum(result.status == NOT_DETECTED for result in results)
    review_count = sum(result.status == MANUAL_REVIEW for result in results)
    lines = [
        "LabelLens — visible label information report",
        f"Input: {source_label}",
        (
            "DEMO SAMPLE — this report is based on example text, not OCR "
            "or an actual product label."
            if is_sample
            else "This report reflects the edited text shown in LabelLens."
        ),
        "",
        f"Detected: {detected_count}",
        f"Not detected: {missing_count}",
        f"Requires manual review: {review_count}",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"{result.label} — {result.status}",
                f"Value: {result.value or 'No value recognized'}",
                f"Note: {result.explanation}",
                "",
            ]
        )
    lines.extend(
        [
            "Important: This is a visibility check, not a legal compliance "
            "determination. Requirements can vary by product category and "
            "applicable rules. OCR errors, incomplete images, or text edits "
            "can cause false warnings.",
            "",
            "Text checked:",
            original_text,
        ]
    )
    return "\n".join(lines)


def render_results(
    results: list[FieldResult],
    original_text: str,
    source_label: str,
    is_sample: bool,
) -> None:
    st.divider()
    st.subheader("Label check")
    st.caption(f"Source: {source_label}")

    detected_count = sum(result.status == DETECTED for result in results)
    missing_count = sum(result.status == NOT_DETECTED for result in results)
    review_count = sum(result.status == MANUAL_REVIEW for result in results)
    summary_columns = st.columns(3)
    summary_columns[0].metric("Detected", detected_count)
    summary_columns[1].metric("Not detected", missing_count)
    summary_columns[2].metric("Manual review", review_count)

    if is_sample:
        st.info(
            "Demo sample only — these results come from example text, not "
            "OCR and not a real product package."
        )

    st.warning(
        "This check does not declare a product legal, illegal, compliant, or "
        "non-compliant. Rules vary by product category; verify the package "
        "yourself and consult the applicable requirements."
    )
    st.caption(
        "OCR can misread small, curved, blurry, or low-contrast print. "
        "A missing result can be a false warning."
    )

    for start in range(0, len(results), 2):
        columns = st.columns(2)
        for column, result in zip(columns, results[start : start + 2]):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{result.label}**")
                    st.caption(result.status)
                    st.write(result.value or "No value recognized")
                    st.caption(result.explanation)
                    if result.status == DETECTED:
                        st.success("Detected")
                    elif result.status == NOT_DETECTED:
                        st.warning("Not detected")
                    else:
                        st.info("Requires manual review")

    st.download_button(
        "Download text report",
        data=report_text(results, original_text, source_label, is_sample),
        file_name="labellens-report.txt",
        mime="text/plain",
        use_container_width=False,
    )



def run_ai_review(label_text: str) -> str:
    """Ask GroqCloud to review OCR text without replacing deterministic findings."""
    import os
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        try:
            api_key = str(st.secrets.get("GROQ_API_KEY", "")).strip()
        except Exception:
            api_key = ""
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. Set it as an environment variable "
            "or in Streamlit secrets, then restart the app."
        )

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.1,
        max_tokens=900,
        messages=[
            {
                "role": "system",
                "content": (
                    "You assist with preliminary reading of Indian packaged-product labels. "
                    "Review only the supplied OCR text. Do not claim legal compliance or "
                    "certify a product. Do not invent missing values or silently correct OCR. "
                    "Separate clearly visible evidence from uncertain interpretation. "
                    "Flag likely OCR ambiguities (such as 2009 versus 200 g) for human review. "
                    "Mention that the original package must be checked. Keep the answer concise "
                    "and use headings: Possible findings, Items to verify, Limitations."
                ),
            },
            {"role": "user", "content": "Review this OCR text:\n\n" + label_text[:12000]},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("GroqCloud returned an empty response.")
    return content

if "analysis" not in st.session_state:
    st.session_state.analysis = None

current_text = ""
source_label = ""
is_sample = False

if mode == "Upload a label":
    image_column, text_column = st.columns([0.9, 1.1], gap="large")
    with image_column:
        st.subheader("Upload a package image")
        uploaded_file = st.file_uploader(
            "Choose a JPG, JPEG, or PNG",
            type=["jpg", "jpeg", "png"],
            help="Use a sharp, well-lit image with the label text in focus.",
        )
        image = None
        if uploaded_file is not None:
            image_hash = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
            if st.session_state.get("upload_hash") != image_hash:
                st.session_state.upload_hash = image_hash
                st.session_state.upload_text = ""
                st.session_state.analysis = None
                st.session_state.ocr_error = None
                try:
                    image = load_uploaded_image(uploaded_file)
                    recognized_text, ocr_error = run_ocr(image)
                    st.session_state.upload_text = recognized_text
                    st.session_state.ocr_error = ocr_error
                except ValueError as error:
                    st.session_state.image_error = str(error)
                else:
                    st.session_state.image_error = None
            else:
                try:
                    image = load_uploaded_image(uploaded_file)
                except ValueError as error:
                    st.session_state.image_error = str(error)

            if st.session_state.get("image_error"):
                st.error(st.session_state.image_error)
            elif image is not None:
                st.image(image, caption=uploaded_file.name, use_container_width=True)
            if st.session_state.get("ocr_error"):
                st.info(st.session_state.ocr_error)
            elif st.session_state.get("upload_text", "").strip():
                st.success("Text extraction complete. Review it before checking.")
        else:
            st.info("Your label image will appear here after you upload it.")

    with text_column:
        st.subheader("Review extracted text")
        st.caption(
            "Correct recognition errors before running the check. You can also "
            "paste label text here without an image."
        )
        if "upload_text" not in st.session_state:
            st.session_state.upload_text = ""
        current_text = st.text_area(
            "Extracted or pasted label text",
            key="upload_text",
            height=300,
            placeholder="Upload an image to run OCR, or paste the visible label text here.",
        )
        if st.button("Check this label", type="primary"):
            if not current_text.strip():
                st.warning("Add or extract some label text before running the check.")
                st.session_state.analysis = None
            else:
                st.session_state.analysis = {
                    "mode": mode,
                    "source_label": uploaded_file.name if uploaded_file else "Pasted text",
                    "text": current_text,
                    "results": validate_label_text(current_text),
                    "is_sample": False,
                }
        source_label = uploaded_file.name if uploaded_file else "Pasted text"
else:
    st.subheader("Try a sample label")
    st.caption(
        "Choose one of the fictional examples to see how the text rules work. "
        "No image is processed in demo mode."
    )
    selected_sample = st.selectbox(
        "Sample product",
        options=list(SAMPLE_LABELS),
    )
    if st.session_state.get("selected_sample") != selected_sample:
        st.session_state.selected_sample = selected_sample
        st.session_state.demo_text = SAMPLE_LABELS[selected_sample]
        st.session_state.analysis = None

    current_text = st.text_area(
        "Sample label text — editable",
        key="demo_text",
        height=300,
        help="You can edit this sample before running the rules.",
    )
    if st.button("Check sample text", type="primary"):
        if not current_text.strip():
            st.warning("Add some label text before running the check.")
            st.session_state.analysis = None
        else:
            st.session_state.analysis = {
                "mode": mode,
                "source_label": selected_sample,
                "text": current_text,
                "results": validate_label_text(current_text),
                "is_sample": True,
            }
    source_label = selected_sample
    is_sample = True

analysis = st.session_state.get("analysis")
if analysis:
    if analysis["mode"] == mode and analysis["text"] == current_text:
        render_results(
            analysis["results"],
            analysis["text"],
            analysis["source_label"],
            analysis["is_sample"],
        )
        st.divider()
        st.subheader("Optional AI-assisted review (GroqCloud)")
        st.caption(
            "Sends the current text only—not the image—to GroqCloud. AI output may be wrong "
            "and does not determine legal compliance. Your normal rule-based results remain separate."
        )
        if not st.session_state.get("groq_ai_review"):
            if st.button("Review text with AI", key="groq_review_button"):
                with st.spinner("Reviewing text with GroqCloud…"):
                    try:
                        st.session_state.groq_ai_review = run_ai_review(analysis["text"])
                        st.session_state.groq_ai_error = None
                    except Exception as error:
                        st.session_state.groq_ai_error = (
                            "AI review failed. Check your API key, internet connection, "
                            "available API quota, and GROQ_MODEL setting. Details: " + str(error)
                        )
        if st.session_state.get("groq_ai_error"):
            st.error(st.session_state.groq_ai_error)
        if st.session_state.get("groq_ai_review"):
            st.markdown(st.session_state.groq_ai_review)
            if st.button("Clear AI review", key="clear_groq_review"):
                st.session_state.groq_ai_review = None
                st.session_state.groq_ai_error = None
                st.rerun()
    else:
        st.info("The text has changed. Run the check again to refresh the results.")
