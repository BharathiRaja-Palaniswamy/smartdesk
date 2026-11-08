"""A document's text, whatever kind of file it came in.

    Markdown, text   read as they are
    PDF              pdfplumber, page by page, each page marked "[Page n]"
    Word (.docx)     python-docx, paragraphs and then tables, a row per line

A file's kind is checked from its first bytes, not only its name: a PDF
starts with "%PDF", a Word document is a zip ("PK"), and text must decode as
UTF-8. A file that is not what its name says, too big, or empty is refused
with the reason, before anything reads it.
"""

import io
from dataclasses import dataclass

import docx
import pdfplumber

MAX_BYTES = 50 * 1024 * 1024  # 50 MB, as the onboarding spec says
KINDS = {".md": "text", ".txt": "text", ".csv": "text", ".pdf": "pdf", ".docx": "word"}


class Unreadable(ValueError):
    """A file that cannot be used, with the reason for the owner."""


@dataclass(frozen=True)
class Document:
    """One uploaded document, as text."""

    name: str
    kind: str  # "text", "pdf" or "word"
    text: str
    pages: int  # PDF pages; 1 for other kinds


def read(name: str, data: bytes) -> Document:
    """The text of the file `name` holding `data`. Raises Unreadable with the reason."""
    suffix = name[name.rfind("."):].lower() if "." in name else ""
    kind = KINDS.get(suffix)
    if kind is None:
        raise Unreadable(f"{name}: this kind of file isn't supported (Markdown, text, CSV, PDF or Word).")
    if not data:
        raise Unreadable(f"{name}: the file is empty.")
    if len(data) > MAX_BYTES:
        raise Unreadable(f"{name}: larger than 50 MB.")
    if kind == "pdf":
        return _pdf(name, data)
    if kind == "word":
        return _word(name, data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Unreadable(f"{name}: not a text file.") from None
    return Document(name, kind, text, 1)


def _pdf(name: str, data: bytes) -> Document:
    if not data.startswith(b"%PDF"):
        raise Unreadable(f"{name}: not a PDF, though its name says so.")
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as error:  # a damaged PDF: refused, never crashing the server
        raise Unreadable(f"{name}: the PDF could not be read ({type(error).__name__}).") from error
    if not any(page.strip() for page in pages):
        raise Unreadable(f"{name}: no text found; scanned pages are not read yet.")
    text = "\n\n".join(f"[Page {n}]\n{page}" for n, page in enumerate(pages, start=1))
    return Document(name, "pdf", text, len(pages))


def _word(name: str, data: bytes) -> Document:
    if not data.startswith(b"PK"):
        raise Unreadable(f"{name}: not a Word document, though its name says so.")
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as error:
        raise Unreadable(f"{name}: the Word document could not be read ({type(error).__name__}).") from error
    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        lines += [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
    text = "\n".join(line for line in lines if line.strip())
    if not text:
        raise Unreadable(f"{name}: no text found.")
    return Document(name, "word", text, 1)
