"""
Tagurit — metadata scrub (secondary safety net on top of rewrite_engine.py).

Even though the rewrite engine already guarantees the PDF's *content* was
re-typed rather than copied, the renderer (reportlab, via xhtml2pdf) fills
in its own PDF /Info dict by default and may embed an XMP metadata stream.
Nothing about that reads the source .md file's OS metadata (path, mtime,
author) today, but nothing controls it either. This module makes it
explicit: only four whitelisted /Info fields survive, values are
app-controlled (never the source file's path/timestamps), and any XMP
stream is stripped.
"""

from __future__ import annotations

import time
from pathlib import Path

from pypdf import PdfReader, PdfWriter

APP_NAME = "Tagurit"
ALLOWED_INFO_KEYS = {"/Title", "/Author", "/Producer", "/Creator", "/CreationDate"}


def _pdf_creation_date() -> str:
    """Conversion-time timestamp in PDF date format — never the source
    file's mtime/ctime, which are never read anywhere in this module."""
    return time.strftime("D:%Y%m%d%H%M%S+00'00'", time.gmtime())


def clean_pdf_metadata(pdf_path: str, title: str) -> None:
    """Rewrite `pdf_path` in place so its /Info dict contains only the
    whitelisted, app-controlled fields, and any XMP metadata stream is
    removed. `title` should be content-derived (e.g. the document's own
    heading or bare filename stem) — never a full filesystem path."""
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    writer.add_metadata({
        "/Title": title,
        "/Author": "",
        "/Producer": APP_NAME,
        "/Creator": APP_NAME,
        "/CreationDate": _pdf_creation_date(),
    })

    writer.xmp_metadata = None

    with open(pdf_path, "wb") as f:
        writer.write(f)


def dump_pdf_metadata(pdf_path: str) -> dict:
    """Read back what actually survived — for verification, not trust."""
    reader = PdfReader(pdf_path)
    info = dict(reader.metadata) if reader.metadata else {}
    xmp = reader.xmp_metadata
    return {"info": info, "has_xmp": xmp is not None}


def title_from_md_path(md_path: str) -> str:
    """Content-derived title: bare filename stem only, never the full path."""
    return Path(md_path).stem
