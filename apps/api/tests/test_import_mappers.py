"""Tests for import column mapping."""

from __future__ import annotations

import pytest

from app.imports.mappers import (
    auto_map_columns,
    suggest_mappings,
    normalize_column_name,
    calculate_similarity,
    ColumnMapping,
)


class TestColumnMapping:
    """Tests for column mapping."""

    def test_auto_map_columns_people(self):
        """Test auto-mapping columns for people entity."""
        source_columns = ["First Name", "Last Name", "Email Address", "Phone Number"]
        mappings = auto_map_columns(source_columns, "people")

        assert "First Name" in mappings
        assert mappings["First Name"].target_field == "first_name"
        assert mappings["Last Name"].target_field == "last_name"
        assert mappings["Email Address"].target_field == "email"

    def test_auto_map_columns_fuzzy_matching(self):
        """Test fuzzy matching for column names."""
        source_columns = ["fname", "lname", "e-mail"]
        mappings = auto_map_columns(source_columns, "people")

        assert "fname" in mappings
        assert mappings["fname"].target_field == "first_name"

    def test_auto_map_columns_memberships(self):
        """Test auto-mapping columns for memberships entity."""
        source_columns = ["Status", "Join Date", "Foundation Completed"]
        mappings = auto_map_columns(source_columns, "memberships")

        assert "Status" in mappings
        assert mappings["Status"].target_field == "status"
        assert mappings["Join Date"].target_field == "join_date"

    def test_auto_map_columns_cells(self):
        """Test auto-mapping columns for cells entity."""
        source_columns = ["Cell Name", "Leader", "Venue", "Meeting Day"]
        mappings = auto_map_columns(source_columns, "cells")

        assert "Cell Name" in mappings
        assert mappings["Cell Name"].target_field == "name"
        assert "Venue" in mappings
        assert mappings["Venue"].target_field == "venue"

    def test_auto_map_columns_cell_reports(self):
        """Test auto-mapping columns for cell_reports entity."""
        source_columns = [
            "Cell ID",
            "Report Date",
            "Attendance",
            "Offerings Total",
        ]
        mappings = auto_map_columns(source_columns, "cell_reports")

        assert "Cell ID" in mappings
        assert mappings["Cell ID"].target_field == "cell_id"
        assert "Report Date" in mappings
        assert mappings["Report Date"].target_field == "report_date"
        assert "Attendance" in mappings
        assert mappings["Attendance"].target_field == "attendance"

    def test_auto_map_columns_finance_entries(self):
        """Test auto-mapping columns for finance_entries entity."""
        source_columns = [
            "Fund ID",
            "Amount",
            "Transaction Date",
            "Payment Method",
        ]
        mappings = auto_map_columns(source_columns, "finance_entries")

        assert "Fund ID" in mappings
        assert mappings["Fund ID"].target_field == "fund_id"
        assert "Amount" in mappings
        assert mappings["Amount"].target_field == "amount"
        assert "Transaction Date" in mappings
        assert mappings["Transaction Date"].target_field == "transaction_date"

    def test_suggest_mappings(self):
        """Test suggesting column mappings."""
        source_columns = ["First Name", "Last Name", "Email"]
        suggestions = suggest_mappings(source_columns, "people")

        assert "First Name" in suggestions
        assert suggestions["First Name"]["best_match"] is not None
        assert suggestions["First Name"]["best_match"]["target_field"] == "first_name"

    def test_normalize_column_name(self):
        """Test normalizing column names."""
        assert normalize_column_name("First_Name") == "first name"
        assert normalize_column_name("First-Name") == "first name"
        assert normalize_column_name("First.Name") == "first name"

    def test_calculate_similarity(self):
        """Test calculating similarity between column names."""
        score = calculate_similarity("first_name", "First Name")
        assert score > 80  # Should be high similarity

        score = calculate_similarity("first_name", "email")
        assert score < 50  # Should be low similarity

