"""Tests for PDF report generator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.reports.pdf_generator import PDFReportGenerator


class TestPDFReportGenerator:
    """Test PDF report generator."""

    def test_generate_pdf_basic(self):
        """Test generating basic PDF."""
        results = [
            {"id": "1", "name": "John", "amount": Decimal("100.50")},
            {"id": "2", "name": "Jane", "amount": Decimal("200.75")},
        ]

        generator = PDFReportGenerator()
        pdf_content = generator.generate(
            results=results,
            template_config={"name": "Test Report"},
        )

        assert pdf_content is not None
        assert len(pdf_content) > 0
        # PDF files start with %PDF
        assert pdf_content[:4] == b"%PDF"

    def test_generate_pdf_with_charts(self):
        """Test generating PDF with charts."""
        results = [
            {"month": "2024-01", "amount": Decimal("100.50")},
            {"month": "2024-02", "amount": Decimal("200.75")},
            {"month": "2024-03", "amount": Decimal("150.25")},
        ]

        generator = PDFReportGenerator()
        pdf_content = generator.generate(
            results=results,
            template_config={"name": "Report with Charts"},
            visualization_config={
                "type": "line_chart",
                "x_axis": "month",
                "y_axis": "amount",
                "title": "Monthly Trends",
            },
            pdf_config={"include_charts": True},
        )

        assert pdf_content is not None
        assert len(pdf_content) > 0
        assert pdf_content[:4] == b"%PDF"

    def test_generate_pdf_empty_data(self):
        """Test generating PDF with empty data."""
        results = []

        generator = PDFReportGenerator()
        pdf_content = generator.generate(
            results=results,
            template_config={"name": "Empty Report"},
        )

        assert pdf_content is not None
        assert len(pdf_content) > 0

    def test_generate_pdf_with_table(self):
        """Test generating PDF with data table."""
        results = [
            {"id": "1", "name": "John", "amount": Decimal("100.50")},
            {"id": "2", "name": "Jane", "amount": Decimal("200.75")},
            {"id": "3", "name": "Bob", "amount": Decimal("150.25")},
        ]

        generator = PDFReportGenerator()
        pdf_content = generator.generate(
            results=results,
            template_config={"name": "Table Report"},
            pdf_config={"include_charts": False},
        )

        assert pdf_content is not None
        assert len(pdf_content) > 0

    def test_generate_line_chart(self):
        """Test line chart generation."""
        results = [
            {"month": "2024-01", "amount": Decimal("100.50")},
            {"month": "2024-02", "amount": Decimal("200.75")},
        ]

        generator = PDFReportGenerator()
        chart_bytes = generator._generate_line_chart(
            results,
            {
                "type": "line_chart",
                "x_axis": "month",
                "y_axis": "amount",
                "title": "Test Chart",
            },
        )

        assert chart_bytes is not None
        assert len(chart_bytes.read()) > 0

    def test_generate_bar_chart(self):
        """Test bar chart generation."""
        results = [
            {"category": "A", "value": Decimal("100")},
            {"category": "B", "value": Decimal("200")},
        ]

        generator = PDFReportGenerator()
        chart_bytes = generator._generate_bar_chart(
            results,
            {
                "type": "bar_chart",
                "x_axis": "category",
                "y_axis": "value",
                "title": "Bar Chart",
            },
        )

        assert chart_bytes is not None
        assert len(chart_bytes.read()) > 0

    def test_generate_pie_chart(self):
        """Test pie chart generation."""
        results = [
            {"label": "A", "value": Decimal("100")},
            {"label": "B", "value": Decimal("200")},
        ]

        generator = PDFReportGenerator()
        chart_bytes = generator._generate_pie_chart(
            results,
            {
                "type": "pie_chart",
                "x_axis": "label",
                "y_axis": "value",
                "title": "Pie Chart",
            },
        )

        assert chart_bytes is not None
        assert len(chart_bytes.read()) > 0

