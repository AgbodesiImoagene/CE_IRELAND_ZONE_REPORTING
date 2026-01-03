"""Export generators for CSV and Excel formats."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class CSVGenerator:
    """Generate CSV exports from query results."""

    @staticmethod
    def generate(results: list[dict[str, Any]], filename: str = "export.csv") -> bytes:
        """
        Generate CSV file from query results.

        Args:
            results: List of result dictionaries
            filename: Output filename (for metadata)

        Returns:
            CSV file content as bytes
        """
        if not results:
            # Return empty CSV with headers if possible
            return b""

        # Convert to DataFrame for easier handling
        df = pd.DataFrame(results)

        # Write to bytes buffer
        buffer = io.BytesIO()
        df.to_csv(buffer, index=False, encoding="utf-8")
        buffer.seek(0)

        return buffer.read()


class ExcelGenerator:
    """Generate Excel exports from query results."""

    @staticmethod
    def generate(
        results: list[dict[str, Any]],
        filename: str = "export.xlsx",
        sheet_name: str = "Data",
    ) -> bytes:
        """
        Generate Excel file from query results.

        Args:
            results: List of result dictionaries
            filename: Output filename (for metadata)
            sheet_name: Sheet name

        Returns:
            Excel file content as bytes
        """
        if not results:
            # Return empty Excel with headers if possible
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(results)

        # Write to bytes buffer
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Format header row
            worksheet = writer.sheets[sheet_name]
            from openpyxl.styles import Font

            for cell in worksheet[1]:
                cell.font = Font(bold=True)

            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def generate_multi_sheet(
        sheets: dict[str, list[dict[str, Any]]],
        filename: str = "export.xlsx",
    ) -> bytes:
        """
        Generate Excel file with multiple sheets.

        Args:
            sheets: Dictionary mapping sheet names to result lists
            filename: Output filename

        Returns:
            Excel file content as bytes
        """
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet_name, results in sheets.items():
                if results:
                    df = pd.DataFrame(results)
                else:
                    df = pd.DataFrame()

                df.to_excel(writer, sheet_name=sheet_name, index=False)

                # Format header row
                worksheet = writer.sheets[sheet_name]
                from openpyxl.styles import Font

                for cell in worksheet[1]:
                    cell.font = Font(bold=True)

                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

        buffer.seek(0)
        return buffer.read()


