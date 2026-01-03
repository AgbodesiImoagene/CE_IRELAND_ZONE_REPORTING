"""File parsers for different import formats using pandas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from io import BytesIO
from typing import Iterator, Optional
import mimetypes

import pandas as pd


class ImportFormat(str, Enum):
    """Supported import formats."""

    CSV = "csv"
    TSV = "tsv"
    XLSX = "xlsx"
    JSON = "json"
    UNKNOWN = "unknown"


class FileParser(ABC):
    """Abstract base class for file parsers."""

    @abstractmethod
    def detect_format(
        self, file_content: bytes, filename: str
    ) -> ImportFormat:
        """Detect file format from content and filename."""

    @abstractmethod
    def parse_headers(self, file_content: bytes) -> list[str]:
        """Parse and return column headers."""

    @abstractmethod
    def parse_rows(
        self,
        file_content: bytes,
        limit: Optional[int] = None,
    ) -> Iterator[dict[str, str]]:
        """Parse rows and yield as dictionaries."""

    @abstractmethod
    def get_row_count(self, file_content: bytes) -> int:
        """Get total row count (excluding header)."""


class CSVParser(FileParser):
    """CSV parser using pandas chunksize for memory efficiency."""

    def detect_format(
        self, file_content: bytes, filename: str
    ) -> ImportFormat:
        """Detect CSV format."""
        if filename.lower().endswith((".csv",)):
            return ImportFormat.CSV
        # Try to detect by content
        try:
            # Try to read first few bytes as CSV
            df = pd.read_csv(BytesIO(file_content), nrows=1)
            if len(df.columns) > 0:
                return ImportFormat.CSV
        except Exception:
            pass
        return ImportFormat.UNKNOWN

    def parse_headers(self, file_content: bytes) -> list[str]:
        """Parse CSV headers."""
        df = pd.read_csv(BytesIO(file_content), nrows=0)
        return [str(col).strip() for col in df.columns.tolist()]

    def parse_rows(
        self, file_content: bytes, limit: Optional[int] = None
    ) -> Iterator[dict[str, str]]:
        """Parse CSV rows using pandas chunksize for memory efficiency."""
        chunk_size = 1000
        total_count = 0

        for chunk in pd.read_csv(
            BytesIO(file_content),
            chunksize=chunk_size,
            dtype=str,  # Keep everything as string for import
            na_values=[],  # Don't treat any values as NaN
            keep_default_na=False,  # Don't treat default NA values as NaN
            encoding_errors="replace",  # Handle encoding errors gracefully
        ):
            chunk = chunk.fillna("")  # Replace NaN with empty string
            for _, row in chunk.iterrows():
                if limit and total_count >= limit:
                    return
                # Convert values to strings and strip whitespace
                cleaned_row = {
                    str(k).strip(): (
                        str(v).strip() if pd.notna(v) else ""
                    )
                    for k, v in row.items()
                }
                yield cleaned_row
                total_count += 1

    def get_row_count(self, file_content: bytes) -> int:
        """Get CSV row count."""
        # Use chunksize to count without loading entire file
        count = 0
        for chunk in pd.read_csv(
            BytesIO(file_content), chunksize=1000
        ):
            count += len(chunk)
        return count


class TSVParser(FileParser):
    """TSV parser using pandas chunksize."""

    def detect_format(
        self, file_content: bytes, filename: str
    ) -> ImportFormat:
        """Detect TSV format."""
        if filename.lower().endswith((".tsv", ".txt")):
            # Check content for tab-separated values
            try:
                # Try to read first row as TSV
                df = pd.read_csv(
                    BytesIO(file_content), sep="\t", nrows=1
                )
                if len(df.columns) > 1:  # TSV should have multiple cols
                    return ImportFormat.TSV
            except Exception:
                pass
        return ImportFormat.UNKNOWN

    def parse_headers(self, file_content: bytes) -> list[str]:
        """Parse TSV headers."""
        df = pd.read_csv(BytesIO(file_content), sep="\t", nrows=0)
        return [str(col).strip() for col in df.columns.tolist()]

    def parse_rows(
        self, file_content: bytes, limit: Optional[int] = None
    ) -> Iterator[dict[str, str]]:
        """Parse TSV rows using pandas chunksize for memory efficiency."""
        chunk_size = 1000
        total_count = 0

        for chunk in pd.read_csv(
            BytesIO(file_content),
            sep="\t",
            chunksize=chunk_size,
            dtype=str,
            na_values=[],
            keep_default_na=False,
            encoding_errors="replace",
        ):
            chunk = chunk.fillna("")
            for _, row in chunk.iterrows():
                if limit and total_count >= limit:
                    return
                cleaned_row = {
                    str(k).strip(): str(v).strip() if pd.notna(v) else ""
                    for k, v in row.items()
                }
                yield cleaned_row
                total_count += 1

    def get_row_count(self, file_content: bytes) -> int:
        """Get TSV row count."""
        count = 0
        for chunk in pd.read_csv(
            BytesIO(file_content), sep="\t", chunksize=1000
        ):
            count += len(chunk)
        return count


class XLSXParser(FileParser):
    """Excel XLSX file parser using pandas."""

    def detect_format(
        self, file_content: bytes, filename: str
    ) -> ImportFormat:
        """Detect XLSX format."""
        if filename.lower().endswith((".xlsx", ".xlsm")):
            return ImportFormat.XLSX
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type in [
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ]:
            return ImportFormat.XLSX
        return ImportFormat.UNKNOWN

    def parse_headers(self, file_content: bytes) -> list[str]:
        """Parse XLSX headers from first row."""
        df = pd.read_excel(BytesIO(file_content), nrows=0)
        return [str(col).strip() for col in df.columns.tolist()]

    def parse_rows(
        self, file_content: bytes, limit: Optional[int] = None
    ) -> Iterator[dict[str, str]]:
        """Parse XLSX rows."""
        df = pd.read_excel(BytesIO(file_content))
        # Convert to string and handle NaN
        df = df.fillna("")
        df = df.astype(str)
        count = 0
        for _, row in df.iterrows():
            if limit and count >= limit:
                break
            # Filter out 'nan' string values and strip whitespace
            cleaned_row = {
                str(k): str(v).strip()
                for k, v in row.items()
                if str(v).strip() != "nan"
            }
            yield cleaned_row
            count += 1

    def get_row_count(self, file_content: bytes) -> int:
        """Get XLSX row count."""
        df = pd.read_excel(BytesIO(file_content))
        return len(df)


class JSONParser(FileParser):
    """JSON file parser using pandas."""

    def detect_format(
        self, file_content: bytes, filename: str
    ) -> ImportFormat:
        """Detect JSON format."""
        if filename.lower().endswith((".json",)):
            return ImportFormat.JSON
        # Try to parse as JSON
        try:
            import json
            json.loads(file_content.decode("utf-8"))
            return ImportFormat.JSON
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return ImportFormat.UNKNOWN

    def parse_headers(self, file_content: bytes) -> list[str]:
        """Parse JSON headers from first object."""
        import json

        # Try to parse as JSON first
        try:
            data = json.loads(file_content.decode("utf-8"))
            if isinstance(data, list) and len(data) > 0:
                first_obj = data[0]
                if isinstance(first_obj, dict):
                    return list(first_obj.keys())
            elif isinstance(data, dict):
                # Single object or nested structure
                return list(data.keys())
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fallback to pandas for complex JSON structures
            try:
                df = pd.read_json(BytesIO(file_content), nrows=1)
                return [str(col).strip() for col in df.columns.tolist()]
            except Exception:
                pass
        return []

    def parse_rows(
        self, file_content: bytes, limit: Optional[int] = None
    ) -> Iterator[dict[str, str]]:
        """Parse JSON rows."""
        import json

        # Try to parse as JSON array
        try:
            data = json.loads(file_content.decode("utf-8"))
            if isinstance(data, list):
                count = 0
                for item in data:
                    if limit and count >= limit:
                        break
                    if isinstance(item, dict):
                        # Convert all values to strings
                        yield {
                            k: str(v) if v is not None else ""
                            for k, v in item.items()
                        }
                        count += 1
            elif isinstance(data, dict):
                # Single object
                yield {
                    k: str(v) if v is not None else ""
                    for k, v in data.items()
                }
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fallback to pandas for complex JSON structures
            try:
                df = pd.read_json(BytesIO(file_content))
                df = df.fillna("")
                count = 0
                for _, row in df.iterrows():
                    if limit and count >= limit:
                        break
                    yield {
                        str(k): str(v).strip() if pd.notna(v) else ""
                        for k, v in row.items()
                    }
                    count += 1
            except Exception:
                # If all else fails, return empty
                pass

    def get_row_count(self, file_content: bytes) -> int:
        """Get JSON row count."""
        import json

        try:
            data = json.loads(file_content.decode("utf-8"))
            if isinstance(data, list):
                return len(data)
            elif isinstance(data, dict):
                return 1
        except Exception:
            # Fallback to pandas
            try:
                df = pd.read_json(BytesIO(file_content))
                return len(df)
            except Exception:
                pass
        return 0


def detect_file_format(file_content: bytes, filename: str) -> ImportFormat:
    """Detect file format using all available parsers."""
    parsers = [
        XLSXParser(),
        JSONParser(),
        TSVParser(),
        CSVParser(),
    ]

    for parser in parsers:
        format_type = parser.detect_format(file_content, filename)
        if format_type != ImportFormat.UNKNOWN:
            return format_type

    return ImportFormat.UNKNOWN


def get_parser(format_type: ImportFormat) -> FileParser:
    """Get appropriate parser for format."""
    parsers = {
        ImportFormat.CSV: CSVParser(),
        ImportFormat.TSV: TSVParser(),
        ImportFormat.XLSX: XLSXParser(),
        ImportFormat.JSON: JSONParser(),
    }
    return parsers.get(format_type, CSVParser())  # Default to CSV
