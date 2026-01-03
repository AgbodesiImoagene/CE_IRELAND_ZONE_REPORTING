"""Tests for export generators (CSV, Excel)."""

from __future__ import annotations

import io
from decimal import Decimal

import pytest

from app.reports.export_generators import CSVGenerator, ExcelGenerator


class TestCSVGenerator:
    """Test CSV generator."""

    def test_generate_csv_with_data(self):
        """Test generating CSV with data."""
        results = [
            {"id": "1", "name": "John", "amount": Decimal("100.50")},
            {"id": "2", "name": "Jane", "amount": Decimal("200.75")},
        ]

        csv_content = CSVGenerator.generate(results)

        assert csv_content is not None
        assert len(csv_content) > 0
        assert b"id,name,amount" in csv_content
        assert b"John" in csv_content

    def test_generate_csv_empty(self):
        """Test generating CSV with empty data."""
        results = []

        csv_content = CSVGenerator.generate(results)

        # Should return empty bytes or minimal CSV
        assert csv_content is not None

    def test_generate_csv_with_special_characters(self):
        """Test generating CSV with special characters."""
        results = [
            {"name": "O'Brien", "description": "Test, with comma"},
        ]

        csv_content = CSVGenerator.generate(results)

        assert csv_content is not None
        assert b"O'Brien" in csv_content


class TestExcelGenerator:
    """Test Excel generator."""

    def test_generate_excel_with_data(self):
        """Test generating Excel with data."""
        results = [
            {"id": "1", "name": "John", "amount": Decimal("100.50")},
            {"id": "2", "name": "Jane", "amount": Decimal("200.75")},
        ]

        excel_content = ExcelGenerator.generate(results)

        assert excel_content is not None
        assert len(excel_content) > 0
        # Excel files start with PK (ZIP signature)
        assert excel_content[:2] == b"PK"

    def test_generate_excel_empty(self):
        """Test generating Excel with empty data."""
        results = []

        excel_content = ExcelGenerator.generate(results)

        assert excel_content is not None
        assert len(excel_content) > 0

    def test_generate_excel_multi_sheet(self):
        """Test generating Excel with multiple sheets."""
        sheets = {
            "Sheet1": [
                {"id": "1", "name": "John"},
            ],
            "Sheet2": [
                {"id": "2", "name": "Jane"},
            ],
        }

        excel_content = ExcelGenerator.generate_multi_sheet(sheets)

        assert excel_content is not None
        assert len(excel_content) > 0
        assert excel_content[:2] == b"PK"

    def test_generate_excel_with_large_dataset(self):
        """Test generating Excel with large dataset."""
        results = [
            {"id": str(i), "value": f"Value {i}"} for i in range(1000)
        ]

        excel_content = ExcelGenerator.generate(results)

        assert excel_content is not None
        assert len(excel_content) > 0

