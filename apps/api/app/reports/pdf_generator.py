"""PDF report generator with embedded visualizations."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Optional

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.reports.export_generators import CSVGenerator

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Generate PDF reports with visualizations."""

    def __init__(self):
        """Initialize PDF generator."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Title"],
                fontSize=24,
                textColor=colors.HexColor("#1a1a1a"),
                spaceAfter=30,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="CustomHeading",
                parent=self.styles["Heading1"],
                fontSize=16,
                textColor=colors.HexColor("#333333"),
                spaceAfter=12,
            )
        )

    def generate(
        self,
        results: list[dict[str, Any]],
        template_config: Optional[dict[str, Any]] = None,
        visualization_config: Optional[dict[str, Any]] = None,
        pdf_config: Optional[dict[str, Any]] = None,
    ) -> bytes:
        """
        Generate PDF from query results and template configuration.

        Args:
            results: Query results
            template_config: Template metadata (name, description, etc.)
            visualization_config: Chart configuration
            pdf_config: PDF layout and styling configuration

        Returns:
            PDF file content as bytes
        """
        buffer = io.BytesIO()

        # Get PDF config with defaults
        config = pdf_config or {}
        page_size = config.get("page_size", "A4")
        layout = config.get("layout", "portrait")
        margins = config.get("margins", {"top": 50, "bottom": 50, "left": 50, "right": 50})

        # Set page size
        if page_size == "A4":
            pagesize = A4
        else:
            pagesize = letter

        if layout == "landscape":
            pagesize = (pagesize[1], pagesize[0])  # Swap width/height

        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=pagesize,
            rightMargin=margins.get("right", 50),
            leftMargin=margins.get("left", 50),
            topMargin=margins.get("top", 50),
            bottomMargin=margins.get("bottom", 50),
        )

        story = []

        # Cover page
        if template_config:
            story.append(Paragraph(template_config.get("name", "Report"), self.styles["CustomTitle"]))
            if template_config.get("description"):
                story.append(Spacer(1, 12))
                story.append(Paragraph(template_config["description"], self.styles["Normal"]))
            story.append(Spacer(1, 24))
            story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", self.styles["Normal"]))
            story.append(PageBreak())

        # Generate charts if requested
        if config.get("include_charts", True) and visualization_config:
            charts = self._generate_charts(results, visualization_config, config)
            for chart_img in charts:
                story.append(Image(chart_img, width=config.get("chart_size", {}).get("width", 500), height=config.get("chart_size", {}).get("height", 300)))
                story.append(Spacer(1, 12))

        # Data table
        if results:
            story.append(Paragraph("Data", self.styles["CustomHeading"]))
            story.append(Spacer(1, 12))
            table = self._create_data_table(results)
            story.append(table)

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.read()

    def _generate_charts(
        self,
        data: list[dict[str, Any]],
        viz_config: dict[str, Any],
        pdf_config: dict[str, Any],
    ) -> list[bytes]:
        """
        Generate chart images using matplotlib/seaborn.

        Args:
            data: Query results
            viz_config: Visualization configuration
            pdf_config: PDF configuration

        Returns:
            List of chart image bytes
        """
        charts = []
        chart_type = viz_config.get("type", "line_chart")

        if not data:
            return charts

        try:
            if chart_type == "line_chart":
                chart_bytes = self._generate_line_chart(data, viz_config)
                if chart_bytes:
                    charts.append(chart_bytes)
            elif chart_type == "bar_chart":
                chart_bytes = self._generate_bar_chart(data, viz_config)
                if chart_bytes:
                    charts.append(chart_bytes)
            elif chart_type == "pie_chart":
                chart_bytes = self._generate_pie_chart(data, viz_config)
                if chart_bytes:
                    charts.append(chart_bytes)
            elif chart_type == "heatmap":
                chart_bytes = self._generate_heatmap(data, viz_config)
                if chart_bytes:
                    charts.append(chart_bytes)
        except Exception as e:
            logger.error(f"Failed to generate chart: {e}", exc_info=True)

        return charts

    def _generate_line_chart(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> Optional[bytes]:
        """Generate line chart."""
        import pandas as pd

        df = pd.DataFrame(data)
        x_field = config.get("x_axis")
        y_field = config.get("y_axis")
        series_field = config.get("series", [None])[0] if config.get("series") else None

        if not x_field or not y_field:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        if series_field and series_field in df.columns:
            # Multiple series
            for series_value in df[series_field].unique():
                series_data = df[df[series_field] == series_value]
                ax.plot(series_data[x_field], series_data[y_field], label=str(series_value), marker='o')
            ax.legend()
        else:
            ax.plot(df[x_field], df[y_field], marker='o')

        ax.set_xlabel(config.get("x_label", x_field))
        ax.set_ylabel(config.get("y_label", y_field))
        ax.set_title(config.get("title", "Line Chart"))
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()

        return buffer

    def _generate_bar_chart(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> Optional[bytes]:
        """Generate bar chart."""
        import pandas as pd

        df = pd.DataFrame(data)
        x_field = config.get("x_axis")
        y_field = config.get("y_axis")

        if not x_field or not y_field:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(df[x_field], df[y_field])
        ax.set_xlabel(config.get("x_label", x_field))
        ax.set_ylabel(config.get("y_label", y_field))
        ax.set_title(config.get("title", "Bar Chart"))
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()

        return buffer

    def _generate_pie_chart(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> Optional[bytes]:
        """Generate pie chart."""
        import pandas as pd

        df = pd.DataFrame(data)
        x_field = config.get("x_axis")
        y_field = config.get("y_axis")

        if not x_field or not y_field:
            return None

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.pie(df[y_field], labels=df[x_field], autopct='%1.1f%%', startangle=90)
        ax.set_title(config.get("title", "Pie Chart"))
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()

        return buffer

    def _generate_heatmap(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> Optional[bytes]:
        """Generate heatmap."""
        import pandas as pd

        df = pd.DataFrame(data)
        x_field = config.get("x_axis")
        y_field = config.get("y_axis")
        value_field = config.get("y_axis")  # Use y_axis as value

        if not x_field or not y_field:
            return None

        # Pivot data for heatmap
        pivot_df = df.pivot(index=y_field, columns=x_field, values=value_field)

        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(pivot_df, annot=True, fmt='.1f', cmap='YlOrRd', ax=ax)
        ax.set_title(config.get("title", "Heatmap"))
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()

        return buffer

    def _create_data_table(self, results: list[dict[str, Any]]) -> Table:
        """Create data table from results."""
        if not results:
            return Table([["No data"]], colWidths=[6 * inch])

        # Get headers from first result
        headers = list(results[0].keys())
        data = [headers]

        # Add rows
        for row in results[:100]:  # Limit to 100 rows for PDF
            data.append([str(row.get(h, "")) for h in headers])

        # Create table
        table = Table(data, colWidths=[2 * inch] * len(headers))
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                ]
            )
        )

        return table


