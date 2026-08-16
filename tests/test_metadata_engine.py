"""Tagurit — metadata_engine tests. Run: py -m unittest discover -s R:\\MD-Convert\\tests"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mistune
from xhtml2pdf import pisa

import metadata_engine
import rewrite_engine

ALLOWED = {"/Title", "/Author", "/Producer", "/Creator", "/CreationDate"}


def _make_pdf(md_text: str, out_path: Path) -> None:
    md = rewrite_engine.rewrite(md_text)
    html_body = mistune.html(md)
    html = f"<!doctype html><meta charset='utf-8'><body>{html_body}</body>"
    with open(out_path, "wb") as f:
        result = pisa.CreatePDF(html, dest=f)
    if result.err:
        raise RuntimeError(f"xhtml2pdf reported {result.err} error(s)")


class MetadataEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.pdf_path = Path(self.tmpdir.name) / "sample.pdf"
        _make_pdf("# A Title\n\nSome **bold** body text with a - list item.\n", self.pdf_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_scrub_leaves_only_whitelisted_keys(self):
        metadata_engine.clean_pdf_metadata(str(self.pdf_path), title="sample")
        dumped = metadata_engine.dump_pdf_metadata(str(self.pdf_path))
        for key in dumped["info"].keys():
            self.assertIn(key, ALLOWED, f"unexpected /Info key survived: {key}")

    def test_scrub_sets_app_producer_and_creator(self):
        metadata_engine.clean_pdf_metadata(str(self.pdf_path), title="sample")
        dumped = metadata_engine.dump_pdf_metadata(str(self.pdf_path))
        self.assertEqual(dumped["info"].get("/Producer"), metadata_engine.APP_NAME)
        self.assertEqual(dumped["info"].get("/Creator"), metadata_engine.APP_NAME)

    def test_scrub_strips_xmp(self):
        metadata_engine.clean_pdf_metadata(str(self.pdf_path), title="sample")
        dumped = metadata_engine.dump_pdf_metadata(str(self.pdf_path))
        self.assertFalse(dumped["has_xmp"])

    def test_title_never_contains_full_path(self):
        fake_path = str(Path(self.tmpdir.name) / "secret_folder" / "notes.md")
        title = metadata_engine.title_from_md_path(fake_path)
        self.assertNotIn(self.tmpdir.name, title)
        self.assertEqual(title, "notes")

    def test_creation_date_is_actually_written(self):
        # Found via adversarial testing: /CreationDate was in ALLOWED_INFO_KEYS
        # but clean_pdf_metadata() never actually set it — a real inconsistency
        # between the whitelist and what was written. Fixed; this pins it.
        metadata_engine.clean_pdf_metadata(str(self.pdf_path), title="sample")
        dumped = metadata_engine.dump_pdf_metadata(str(self.pdf_path))
        self.assertIn("/CreationDate", dumped["info"])
        self.assertTrue(dumped["info"]["/CreationDate"].startswith("D:"))

    def test_xmp_strip_path_actually_exercised(self):
        # xhtml2pdf never emits XMP itself, so the has_xmp-False check above is
        # vacuous against real xhtml2pdf output (confirmed via adversarial
        # testing — has_xmp was already False pre-scrub in every case tried).
        # Inject a REAL, valid XMP stream (containing something that looks
        # like a leaked path, deliberately) so the strip path is genuinely
        # exercised, not just trivially true.
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import DecodedStreamObject, NameObject

        reader = PdfReader(str(self.pdf_path))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        xmp_bytes = (
            b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            b'<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            b'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">leaked/original/path.md</rdf:li></rdf:Alt></dc:title>'
            b"</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
        )
        stream = DecodedStreamObject()
        stream.set_data(xmp_bytes)
        stream[NameObject("/Type")] = NameObject("/Metadata")
        stream[NameObject("/Subtype")] = NameObject("/XML")
        ref = writer._add_object(stream)
        writer._root_object[NameObject("/Metadata")] = ref

        with open(self.pdf_path, "wb") as f:
            writer.write(f)

        # confirm the injection actually took, before trusting the scrub result
        pre_scrub_has_xmp = PdfReader(str(self.pdf_path)).xmp_metadata is not None
        self.assertTrue(pre_scrub_has_xmp, "test setup failed to inject real XMP")

        metadata_engine.clean_pdf_metadata(str(self.pdf_path), title="sample")
        dumped = metadata_engine.dump_pdf_metadata(str(self.pdf_path))
        self.assertFalse(dumped["has_xmp"])

    def test_pdf_still_opens_after_scrub(self):
        metadata_engine.clean_pdf_metadata(str(self.pdf_path), title="sample")
        from pypdf import PdfReader
        reader = PdfReader(str(self.pdf_path))
        self.assertGreaterEqual(len(reader.pages), 1)


if __name__ == "__main__":
    unittest.main()
