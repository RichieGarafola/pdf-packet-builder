from __future__ import annotations

from io import BytesIO
import unittest

from pypdf import PdfReader, PdfWriter

from services.pdf_service import (
    PdfMergeError,
    PdfSource,
    PdfValidationError,
    UploadLimits,
    merge_pdfs,
    validate_source,
)


def build_pdf(page_count: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)

    output = BytesIO()
    writer.write(output)
    writer.close()
    return output.getvalue()


class PdfMergeTests(unittest.TestCase):
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

    def test_merge_raises_when_all_files_are_invalid(self) -> None:
        with self.assertRaises(PdfMergeError):
            merge_pdfs(
                [
                    PdfSource(name="bad1.pdf", content=b"not-a-pdf"),
                    PdfSource(name="bad2.pdf", content=b"also-not-a-pdf"),
                ]
            )

    def test_merge_raises_on_empty_source_list(self) -> None:
        with self.assertRaises(PdfValidationError):
            merge_pdfs([])

    def test_merge_result_output_size_is_positive(self) -> None:
        result = merge_pdfs(
            [PdfSource(name="single.pdf", content=build_pdf(page_count=3))]
        )
        self.assertGreater(result.output_size_bytes, 0)
        self.assertEqual(3, result.total_pages)

    def test_merge_records_input_size(self) -> None:
        pdf_bytes = build_pdf(page_count=1)
        result = merge_pdfs(
            [PdfSource(name="a.pdf", content=pdf_bytes)]
        )
        self.assertEqual(len(pdf_bytes), result.input_size_bytes)


class PdfValidateSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.limits = UploadLimits()

    def test_valid_source_returns_none(self) -> None:
        source = PdfSource(name="valid.pdf", content=b"x" * 100)
        self.assertIsNone(validate_source(source, self.limits))

    def test_empty_file_returns_issue(self) -> None:
        source = PdfSource(name="empty.pdf", content=b"")
        issue = validate_source(source, self.limits)
        self.assertIsNotNone(issue)
        self.assertEqual("empty.pdf", issue.file_name)
        self.assertIn("empty", issue.message.lower())

    def test_oversized_file_returns_issue(self) -> None:
        source = PdfSource(name="big.pdf", content=b"x" * (26 * 1024 * 1024))
        issue = validate_source(source, self.limits)
        self.assertIsNotNone(issue)
        self.assertEqual("big.pdf", issue.file_name)
        self.assertIn("25 MB", issue.message)

    def test_wrong_extension_returns_issue(self) -> None:
        source = PdfSource(name="document.docx", content=b"x" * 100)
        issue = validate_source(source, self.limits)
        self.assertIsNotNone(issue)
        self.assertEqual("document.docx", issue.file_name)
        self.assertIn(".pdf", issue.message)

    def test_custom_limits_applied(self) -> None:
        tight_limits = UploadLimits(max_file_size_bytes=50)
        source = PdfSource(name="just_over.pdf", content=b"x" * 51)
        issue = validate_source(source, tight_limits)
        self.assertIsNotNone(issue)


if __name__ == "__main__":
    unittest.main()
