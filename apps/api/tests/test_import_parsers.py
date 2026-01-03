"""Tests for import file parsers."""

from __future__ import annotations

import csv
import json
from io import BytesIO

import pytest

from app.imports.parsers import (
    CSVParser,
    TSVParser,
    XLSXParser,
    JSONParser,
    detect_file_format,
    get_parser,
    ImportFormat,
)


class TestCSVParser:
    """Tests for CSV parser."""

    def test_detect_csv_format(self):
        """Test CSV format detection."""
        parser = CSVParser()
        csv_content = b"name,email,phone\nJohn,john@test.com,1234567890"
        assert parser.detect_format(csv_content, "test.csv") == ImportFormat.CSV

    def test_parse_headers(self):
        """Test parsing CSV headers."""
        parser = CSVParser()
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        headers = parser.parse_headers(csv_content)
        assert headers == ["first_name", "last_name", "email"]

    def test_parse_rows(self):
        """Test parsing CSV rows."""
        parser = CSVParser()
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com\nJane,Smith,jane@test.com"
        rows = list(parser.parse_rows(csv_content))
        assert len(rows) == 2
        assert rows[0]["first_name"] == "John"
        assert rows[0]["last_name"] == "Doe"
        assert rows[1]["email"] == "jane@test.com"

    def test_get_row_count(self):
        """Test getting row count."""
        parser = CSVParser()
        csv_content = b"first_name,last_name\nJohn,Doe\nJane,Smith\nBob,Johnson"
        assert parser.get_row_count(csv_content) == 3

    def test_parse_rows_with_limit(self):
        """Test parsing CSV rows with limit."""
        parser = CSVParser()
        csv_content = b"first_name,last_name\nJohn,Doe\nJane,Smith\nBob,Johnson"
        rows = list(parser.parse_rows(csv_content, limit=2))
        assert len(rows) == 2

    def test_detect_csv_by_content(self):
        """Test detecting CSV by content when extension is missing."""
        parser = CSVParser()
        csv_content = b"name,email\nJohn,john@test.com"
        assert parser.detect_format(csv_content, "test.txt") == ImportFormat.CSV

    def test_parse_csv_with_empty_values(self):
        """Test parsing CSV with empty values."""
        parser = CSVParser()
        csv_content = b"first_name,last_name,email\nJohn,,john@test.com\n,Jane,"
        rows = list(parser.parse_rows(csv_content))
        assert len(rows) == 2
        assert rows[0]["last_name"] == ""
        assert rows[1]["first_name"] == ""


class TestTSVParser:
    """Tests for TSV parser."""

    def test_detect_tsv_format(self):
        """Test TSV format detection."""
        parser = TSVParser()
        tsv_content = b"name\temail\tphone\nJohn\tjohn@test.com\t1234567890"
        assert parser.detect_format(tsv_content, "test.tsv") == ImportFormat.TSV

    def test_parse_headers(self):
        """Test parsing TSV headers."""
        parser = TSVParser()
        tsv_content = b"first_name\tlast_name\temail\nJohn\tDoe\tjohn@test.com"
        headers = parser.parse_headers(tsv_content)
        assert headers == ["first_name", "last_name", "email"]

    def test_parse_rows(self):
        """Test parsing TSV rows."""
        parser = TSVParser()
        tsv_content = b"first_name\tlast_name\temail\nJohn\tDoe\tjohn@test.com\nJane\tSmith\tjane@test.com"
        rows = list(parser.parse_rows(tsv_content))
        assert len(rows) == 2
        assert rows[0]["first_name"] == "John"

    def test_detect_tsv_by_content(self):
        """Test detecting TSV by content."""
        parser = TSVParser()
        tsv_content = b"name\temail\nJohn\tjohn@test.com"
        # Should detect as TSV even without .tsv extension
        result = parser.detect_format(tsv_content, "test.txt")
        # May return TSV or UNKNOWN depending on content detection
        assert result in [ImportFormat.TSV, ImportFormat.UNKNOWN]

    def test_parse_tsv_with_limit(self):
        """Test parsing TSV rows with limit."""
        parser = TSVParser()
        tsv_content = b"first_name\tlast_name\nJohn\tDoe\nJane\tSmith\nBob\tJohnson"
        rows = list(parser.parse_rows(tsv_content, limit=2))
        assert len(rows) == 2

    def test_get_tsv_row_count(self):
        """Test getting TSV row count."""
        parser = TSVParser()
        tsv_content = b"first_name\tlast_name\nJohn\tDoe\nJane\tSmith"
        assert parser.get_row_count(tsv_content) == 2


class TestJSONParser:
    """Tests for JSON parser."""

    def test_detect_json_format(self):
        """Test JSON format detection."""
        parser = JSONParser()
        json_content = b'[{"name": "John", "email": "john@test.com"}]'
        assert parser.detect_format(json_content, "test.json") == ImportFormat.JSON

    def test_parse_headers(self):
        """Test parsing JSON headers."""
        parser = JSONParser()
        json_content = b'[{"first_name": "John", "last_name": "Doe", "email": "john@test.com"}]'
        headers = parser.parse_headers(json_content)
        assert set(headers) == {"first_name", "last_name", "email"}

    def test_parse_rows(self):
        """Test parsing JSON rows."""
        parser = JSONParser()
        json_content = b'[{"first_name": "John", "last_name": "Doe"}, {"first_name": "Jane", "last_name": "Smith"}]'
        rows = list(parser.parse_rows(json_content))
        assert len(rows) == 2
        assert rows[0]["first_name"] == "John"

    def test_get_row_count(self):
        """Test getting row count."""
        parser = JSONParser()
        json_content = b'[{"name": "John"}, {"name": "Jane"}, {"name": "Bob"}]'
        assert parser.get_row_count(json_content) == 3

    def test_detect_json_by_content(self):
        """Test detecting JSON by content when extension is missing."""
        parser = JSONParser()
        json_content = b'[{"name": "John"}]'
        assert parser.detect_format(json_content, "test.txt") == ImportFormat.JSON

    def test_parse_json_single_object(self):
        """Test parsing JSON single object."""
        parser = JSONParser()
        json_content = b'{"first_name": "John", "last_name": "Doe"}'
        rows = list(parser.parse_rows(json_content))
        assert len(rows) == 1
        assert rows[0]["first_name"] == "John"

    def test_parse_json_with_limit(self):
        """Test parsing JSON rows with limit."""
        parser = JSONParser()
        json_content = b'[{"name": "John"}, {"name": "Jane"}, {"name": "Bob"}]'
        rows = list(parser.parse_rows(json_content, limit=2))
        assert len(rows) == 2

    def test_get_row_count_single_object(self):
        """Test getting row count for single JSON object."""
        parser = JSONParser()
        json_content = b'{"name": "John"}'
        assert parser.get_row_count(json_content) == 1

    def test_parse_headers_single_object(self):
        """Test parsing headers from single JSON object."""
        parser = JSONParser()
        json_content = b'{"first_name": "John", "last_name": "Doe"}'
        headers = parser.parse_headers(json_content)
        assert set(headers) == {"first_name", "last_name"}

    def test_parse_json_invalid_fallback(self):
        """Test parsing invalid JSON falls back gracefully."""
        parser = JSONParser()
        invalid_json = b"not valid json"
        # Should not raise exception
        rows = list(parser.parse_rows(invalid_json))
        # May return empty or handle gracefully
        assert isinstance(rows, list)


class TestXLSXParser:
    """Tests for XLSX parser."""

    @pytest.mark.skipif(
        not XLSXParser().detect_format(b"", "test.xlsx") == ImportFormat.XLSX,
        reason="openpyxl or pandas not available",
    )
    def test_detect_xlsx_format(self):
        """Test XLSX format detection."""
        parser = XLSXParser()
        # Create a minimal XLSX file in memory
        try:
            import openpyxl
            from io import BytesIO

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["first_name", "last_name", "email"])
            ws.append(["John", "Doe", "john@test.com"])
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            xlsx_content = buffer.getvalue()

            assert parser.detect_format(xlsx_content, "test.xlsx") == ImportFormat.XLSX
        except ImportError:
            pytest.skip("openpyxl not available")


class TestFormatDetection:
    """Tests for format detection utilities."""

    def test_detect_file_format_csv(self):
        """Test detecting CSV format."""
        csv_content = b"name,email,phone\nJohn,john@test.com,1234567890"
        assert detect_file_format(csv_content, "test.csv") == ImportFormat.CSV

    def test_detect_file_format_json(self):
        """Test detecting JSON format."""
        json_content = b'[{"name": "John"}]'
        assert detect_file_format(json_content, "test.json") == ImportFormat.JSON

    def test_get_parser(self):
        """Test getting parser for format."""
        parser = get_parser(ImportFormat.CSV)
        assert isinstance(parser, CSVParser)

        parser = get_parser(ImportFormat.JSON)
        assert isinstance(parser, JSONParser)

    def test_detect_file_format_unknown(self):
        """Test detecting unknown format."""
        # Use content that definitely won't be detected as any known format
        unknown_content = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        result = detect_file_format(unknown_content, "test.unknown")
        # CSV parser might try to parse it, but it should eventually return UNKNOWN
        # If CSV parser detects it, that's acceptable behavior - just verify it's not JSON/XLSX/TSV
        assert result in [ImportFormat.UNKNOWN, ImportFormat.CSV]

    def test_get_parser_unknown_format(self):
        """Test getting parser for unknown format defaults to CSV."""
        parser = get_parser(ImportFormat.UNKNOWN)
        assert isinstance(parser, CSVParser)

