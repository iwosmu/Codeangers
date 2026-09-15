"""Request-local file handling. No filesystem extraction, OCR, ASR, or shared cache."""
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from ..envelope import ApiError

MB = 1024 * 1024
MAX_FILE_BYTES = 50 * MB
MAX_REQUEST_BYTES = 120 * MB
MAX_TEXT = 100_000
INLINE_LIMIT = 20 * MB
NATIVE = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".webp": "image/webp", ".heic": "image/heic",
    ".heif": "image/heif", ".mp3": "audio/mpeg", ".wav": "audio/wav",
    ".m4a": "audio/mp4", ".aac": "audio/aac", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".aiff": "audio/aiff",
}
CV_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".txt", ".md"}
PROJECT_EXTENSIONS = set(NATIVE) | {".docx", ".pptx", ".txt", ".md"}


@dataclass
class Asset:
    data: bytes
    mime: str
    location: str = "attachment"
    force_upload: bool = False


@dataclass
class Source:
    id: str
    label: str
    owner: str | None = None
    text: str = ""
    assets: list[Asset] = field(default_factory=list)
    notes: str = ""


def clean_label(name: str) -> str:
    return PurePosixPath(name.replace("\\", "/")).name[:180]


def xml_root(raw: bytes):
    # Never resolve document-defined entities, even in an otherwise valid ZIP.
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Document-defined XML entities are not supported")
    return ET.fromstring(raw)


def office_source(data: bytes, source: Source, extension: str) -> Source:
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(i.file_size for i in entries) > MAX_FILE_BYTES:
                raise ValueError("Document expands beyond the 50 MB limit")
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate document entries")
            if extension == ".docx":
                if "word/document.xml" not in names:
                    raise ValueError("Not a DOCX document")
                documents = ["word/document.xml"] + sorted(n for n in names if re.fullmatch(r"word/(header\d+|footer\d+|footnotes|endnotes)\.xml", n))
                prefix = "word/media/"
            else:
                # Respect presentation order, which can differ from slide filenames.
                root = xml_root(archive.read("ppt/presentation.xml"))
                rels = xml_root(archive.read("ppt/_rels/presentation.xml.rels"))
                targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels if r.attrib.get("TargetMode") != "External"}
                documents = []
                for item in root.iter():
                    if item.tag.endswith("}sldId"):
                        rid = item.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                        target = targets.get(rid, "")
                        path = target.lstrip("/") if target.startswith("/") else "ppt/" + target
                        if not re.fullmatch(r"ppt/slides/slide\d+\.xml", path):
                            raise ValueError("Unsupported slide relationship")
                        documents.append(path)
                documents += sorted(n for n in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n))
                prefix = "ppt/media/"
            paragraphs = []
            for doc in documents:
                root = xml_root(archive.read(doc))
                # Paragraph boundaries preserve readable quotes; runs within a paragraph are adjacent.
                for index, paragraph in enumerate((n for n in root.iter() if n.tag.endswith("}p")), 1):
                    text = "".join(n.text or "" for n in paragraph.iter() if n.tag.endswith("}t"))
                    if text.strip():
                        paragraphs.append(f"[{doc}, paragraph {index}] {text.strip()}")
            source.text = "\n".join(paragraphs)
            if len(source.text) > MAX_TEXT:
                raise ValueError("Extracted document text exceeds 100,000 characters")
            for name in names:
                ext = PurePosixPath(name).suffix.lower()
                if name.startswith(prefix) and ext in NATIVE and NATIVE[ext].startswith("image/"):
                    source.assets.append(Asset(archive.read(name), NATIVE[ext], name, len(data) > INLINE_LIMIT))
            if len(source.assets) > 40:
                raise ValueError("Document contains over 40 images; export a PDF")
            if not source.text and not source.assets:
                raise ValueError("No readable text or supported images")
            source.notes = "Office text and embedded images extracted in memory. Layout, charts, vector shapes, and image placement may be lost; use PDF when these carry meaning."
            # Large Office originals are not a native Gemini format. Route the converted text and assets through Files API.
            if len(data) > INLINE_LIMIT and source.text:
                source.assets.insert(0, Asset(source.text.encode(), "text/plain", "extracted Office text", True))
            return source
    except (BadZipFile, KeyError, ValueError, ET.ParseError, RuntimeError, NotImplementedError) as exc:
        raise ApiError("bad_input", f"Cannot read {source.label}. Use an unencrypted DOCX/PPTX, or export it as PDF.") from exc


def prepare_source(source_id: str, filename: str, data: bytes, *, owner: str | None = None) -> Source:
    source = Source(source_id, clean_label(filename), owner=owner)
    ext = PurePosixPath(source.label).suffix.lower()
    allowed = CV_EXTENSIONS if owner else PROJECT_EXTENSIONS
    if ext not in allowed:
        raise ApiError("bad_input", f"Unsupported file: {source.label}. Use PDF, DOCX, an image or text; project material also accepts PPTX and audio. Export legacy .doc/.ppt files as PDF.")
    if not data or len(data) > MAX_FILE_BYTES:
        raise ApiError("bad_input", f"{source.label} is empty or exceeds 50 MB.")
    if ext in {".txt", ".md"}:
        try:
            source.text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ApiError("bad_input", f"{source.label} must use UTF-8 text encoding.") from exc
        if not source.text.strip() or len(source.text) > MAX_TEXT:
            raise ApiError("bad_input", f"{source.label} must contain 1–100,000 characters.")
    elif ext in {".docx", ".pptx"}:
        return office_source(data, source, ext)
    else:
        if ext == ".pdf" and not data.startswith(b"%PDF-"):
            raise ApiError("bad_input", f"{source.label} is not a valid PDF.")
        source.assets.append(Asset(data, NATIVE[ext]))
    return source
