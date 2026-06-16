from __future__ import annotations

import unittest

from utils.file_utils import DEFAULT_OUTPUT_FILENAME, format_file_size, sanitize_pdf_filename


class SanitizePdfFilenameTests(unittest.TestCase):
    # --- Empty / None / whitespace inputs ---

    def test_empty_string_returns_default(self) -> None:
        self.assertEqual(DEFAULT_OUTPUT_FILENAME, sanitize_pdf_filename(""))

    def test_none_returns_default(self) -> None:
        self.assertEqual(DEFAULT_OUTPUT_FILENAME, sanitize_pdf_filename(None))

    def test_whitespace_only_returns_default(self) -> None:
        self.assertEqual(DEFAULT_OUTPUT_FILENAME, sanitize_pdf_filename("   "))

    def test_all_invalid_characters_returns_default_stem(self) -> None:
        # "!!!" -> safe_stem="" -> falls back to default stem
        self.assertEqual(DEFAULT_OUTPUT_FILENAME, sanitize_pdf_filename("!!!"))

    # --- Extension handling ---

    def test_plain_stem_receives_pdf_extension(self) -> None:
        self.assertEqual("report.pdf", sanitize_pdf_filename("report"))

    def test_existing_pdf_extension_preserved(self) -> None:
        self.assertEqual("report.pdf", sanitize_pdf_filename("report.pdf"))

    def test_non_pdf_extension_replaced(self) -> None:
        # Strip foreign extension, keep stem, add .pdf
        self.assertEqual("report.pdf", sanitize_pdf_filename("report.docx"))

    def test_dot_prefix_stripped(self) -> None:
        # ".hidden" has no suffix under PurePath; stem is stripped of leading dot
        self.assertEqual("hidden.pdf", sanitize_pdf_filename(".hidden"))

    # --- Character sanitization ---

    def test_spaces_replaced_with_underscores(self) -> None:
        self.assertEqual("My_Report.pdf", sanitize_pdf_filename("My Report!"))

    def test_multiple_spaces_collapsed(self) -> None:
        self.assertEqual("my_report_here.pdf", sanitize_pdf_filename("my report  here"))

    def test_hyphens_preserved(self) -> None:
        # Hyphens are allowed by the INVALID_FILENAME_CHARS pattern
        self.assertEqual("quarterly-summary.pdf", sanitize_pdf_filename("quarterly-summary"))

    def test_uppercase_preserved(self) -> None:
        self.assertEqual("REPORT.pdf", sanitize_pdf_filename("REPORT"))

    def test_dots_in_stem_preserved(self) -> None:
        # "my.report.pdf" -> suffix=".pdf", stem="my.report" -> "my.report.pdf"
        self.assertEqual("my.report.pdf", sanitize_pdf_filename("my.report.pdf"))

    # --- Long filenames ---

    def test_long_stem_passes_through(self) -> None:
        # No length limit is enforced; documents the current contract
        long_stem = "a" * 200
        result = sanitize_pdf_filename(long_stem)
        self.assertTrue(result.endswith(".pdf"))
        self.assertEqual(f"{long_stem}.pdf", result)

    # --- Custom default ---

    def test_custom_default_name_used_on_empty_input(self) -> None:
        self.assertEqual("custom.pdf", sanitize_pdf_filename("", default_name="custom.pdf"))


class FormatFileSizeTests(unittest.TestCase):
    # --- Byte range ---

    def test_zero_bytes(self) -> None:
        self.assertEqual("0 B", format_file_size(0))

    def test_512_bytes(self) -> None:
        self.assertEqual("512 B", format_file_size(512))

    def test_1023_bytes_stays_in_bytes(self) -> None:
        self.assertEqual("1023 B", format_file_size(1023))

    # --- Kilobyte boundary ---

    def test_exactly_1_kb(self) -> None:
        self.assertEqual("1.0 KB", format_file_size(1024))

    def test_1_5_kb(self) -> None:
        self.assertEqual("1.5 KB", format_file_size(1536))

    # --- Megabyte range ---

    def test_exactly_1_mb(self) -> None:
        self.assertEqual("1.0 MB", format_file_size(1024 * 1024))

    def test_25_mb_per_file_limit(self) -> None:
        self.assertEqual("25.0 MB", format_file_size(25 * 1024 * 1024))

    # --- Gigabyte range ---

    def test_exactly_1_gb(self) -> None:
        self.assertEqual("1.0 GB", format_file_size(1024 * 1024 * 1024))

    def test_value_larger_than_gb_clips_at_gb(self) -> None:
        # 1 TB expressed in GB because GB is the largest unit
        result = format_file_size(1024 * 1024 * 1024 * 1024)
        self.assertTrue(result.endswith(" GB"))

    # --- Error handling ---

    def test_negative_size_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            format_file_size(-1)


if __name__ == "__main__":
    unittest.main()
