from __future__ import annotations

from io import BytesIO
import unittest

from pypdf import PdfReader, PdfWriter

from services.pdf_service import (
    PdfSource,
    PdfValidationError,
    UploadLimits,
    merge_pdfs,
)


def build_pdf(page_count: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)

    output = BytesIO()
    writer.write(output)
    writer.close()
    return output.getvalue()


class PdfServiceTests(unittest.TestCase):
    def test_merge_pdfs_combines_pages_in_order(self) -> None:
        result = merge_pdfs(
            [
                PdfSource(name="first.pdf", content=build_pdf(page_count=1)),
                PdfSource(name="second.pdf", content=build_pdf(page_count=2)),
            ]
        )

        merged_reader = PdfReader(BytesIO(result.content))

        self.assertEqual(3, len(merged_reader.pages))
        self.assertEqual(("first.pdf", "second.pdf"), result.merged_files)
        self.assertEqual(0, len(result.skipped_files))

    def test_merge_pdfs_skips_invalid_documents(self) -> None:
        result = merge_pdfs(
            [
                PdfSource(name="valid.pdf", content=build_pdf(page_count=1)),
                PdfSource(name="broken.pdf", content=b"not-a-pdf"),
            ]
        )

        self.assertEqual(("valid.pdf",), result.merged_files)
        self.assertEqual(1, len(result.skipped_files))
        self.assertEqual("broken.pdf", result.skipped_files[0].file_name)

    def test_merge_pdfs_rejects_oversized_batch(self) -> None:
        with self.assertRaises(PdfValidationError):
            merge_pdfs(
                [
                    PdfSource(name="first.pdf", content=build_pdf(page_count=1)),
                    PdfSource(name="second.pdf", content=build_pdf(page_count=1)),
                ],
                limits=UploadLimits(max_file_count=1),
            )


if __name__ == "__main__":
    unittest.main()
