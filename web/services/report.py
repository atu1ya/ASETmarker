"""
PDF report generation service.
"""
from io import BytesIO
from datetime import datetime
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm
from web.services.analysis import FullAnalysis, LearningAreaResult


class ReportService:
    """Generates branded PDF reports for students."""


    def generate_student_report(self, analysis: FullAnalysis) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        # Custom styles
        title_style = ParagraphStyle(
            'Title', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#3498DB'), alignment=1, spaceAfter=12
        )
        header_style = ParagraphStyle(
            'Header', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#2C3E50'), alignment=0, spaceAfter=8
        )
        # 1. Header
        student_name = analysis.summary.get('student_name', 'Unknown')
        writing_score = analysis.summary.get('writing_score', 0)
        reading_score = analysis.summary.get('reading_score', 0)
        reading_max = analysis.summary.get('reading_max', 0)
        qrar_score = analysis.summary.get('qrar_score', 0)
        qrar_max = analysis.summary.get('qrar_max', 0)
        elements.append(Paragraph("Student Performance Report", title_style))
        elements.append(Paragraph(f"Name: {student_name}", header_style))
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", header_style))
        elements.append(Spacer(1, 8))
        # 2. Score Summary Table
        total_score = reading_score + qrar_score + writing_score
        total_max = reading_max + qrar_max
        summary_data = [
            ["Subject", "Score", "Max"],
            ["Reading", str(reading_score), str(reading_max)],
            ["QR/AR", str(qrar_score), str(qrar_max)],
            ["Writing", str(writing_score), "-"],
            ["Total", str(total_score), str(total_max)],
        ]
        summary_table = Table(summary_data, hAlign='LEFT', colWidths=[60*mm, 30*mm, 30*mm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#2C3E50')),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))
        # 3. Reading Analysis Section
        reading_areas = analysis.subject_areas.get('Reading', [])
        elements.append(Paragraph("Reading Analysis", header_style))
        elements.append(self._area_table(reading_areas))
        elements.append(Spacer(1, 12))
        # 4. QR/AR Analysis Section
        qrar_areas = analysis.subject_areas.get('QR/AR', [])
        elements.append(Paragraph("QR/AR Analysis", header_style))
        elements.append(self._area_table(qrar_areas))
        doc.build(elements)
        return buffer.getvalue()
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        # Custom styles
        title_style = ParagraphStyle(
            'Title', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#3498DB'), alignment=1, spaceAfter=12
        )
        header_style = ParagraphStyle(
            'Header', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#2C3E50'), alignment=0, spaceAfter=8
        )
        table_header_style = ParagraphStyle(
            'TableHeader', parent=styles['Normal'], fontSize=12, textColor=colors.white, alignment=1, backColor=colors.HexColor('#3498DB'), spaceAfter=4
        )
        # 1. Header
        elements.append(Paragraph("Student Performance Report", title_style))
        elements.append(Paragraph(f"Name: {analysis.student_name}", header_style))
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", header_style))
        elements.append(Spacer(1, 8))
        # 2. Score Summary Table
        summary_data = [
            ["Subject", "Score", "Max"],
            ["Reading", str(analysis.reading_total_score), str(analysis.reading_max_score)],
            ["QR/AR", str(analysis.qrar_total_score), str(analysis.qrar_max_score)],
            ["Writing", str(analysis.writing_score), "-"],
            ["Total", str(analysis.reading_total_score + analysis.qrar_total_score + analysis.writing_score), str(analysis.reading_max_score + analysis.qrar_max_score)],
        ]
        summary_table = Table(summary_data, hAlign='LEFT', colWidths=[60*mm, 30*mm, 30*mm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#2C3E50')),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))
        # 3. Reading Analysis Section
        elements.append(Paragraph("Reading Analysis", header_style))
        elements.append(self._area_table(analysis.reading_analysis))
        elements.append(Spacer(1, 12))
        # 4. QR/AR Analysis Section
        elements.append(Paragraph("QR/AR Analysis", header_style))
        elements.append(self._area_table(analysis.qrar_analysis))
        doc.build(elements)
        return buffer.getvalue()

    def _area_table(self, area_results: list) -> Table:
        # Table columns: Area | % | Status
        data = [["Learning Area", "%", "Status"]]
        for area in area_results:
            percent = f"{area.percentage:.1f}%"
            status = area.status
            # Conditional color
            data.append([getattr(area, 'area', 'Unknown'), percent, status])
        table = Table(data, hAlign='LEFT', colWidths=[60*mm, 30*mm, 40*mm])
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#2C3E50')),
        ])
        # Conditional formatting for status column
        for i, area in enumerate(area_results, start=1):
            status = area.status
            if status == "Done well":
                style.add('TEXTCOLOR', (2,i), (2,i), colors.green)
            else:
                style.add('TEXTCOLOR', (2,i), (2,i), colors.HexColor('#E67E22'))
        table.setStyle(style)
        return table
