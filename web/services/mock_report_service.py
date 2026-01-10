"""Mock report generation service."""
import csv
import io
from difflib import get_close_matches
from typing import List, Dict, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart


class MockReportService:
    """Service for generating mock performance reports from CSV data."""
    
    def _find_best_column_match(self, headers: List[str], target_keywords: List[str], prefer_standardised: bool = False) -> Optional[str]:
        """
        Find the best matching column header using fuzzy matching.
        
        Args:
            headers: List of actual CSV column headers
            target_keywords: Keywords to search for (in priority order)
            prefer_standardised: If True, prioritize columns containing "standardised"
        
        Returns:
            The best matching column name, or None if no match found
        """
        # If we prefer standardised scores, filter headers first
        if prefer_standardised:
            standardised_headers = [h for h in headers if 'standardised' in h.lower() or 'standardized' in h.lower()]
            if standardised_headers:
                headers = standardised_headers
        
        # Try exact substring matching first
        for keyword in target_keywords:
            for header in headers:
                if keyword.lower() in header.lower():
                    # Avoid matching raw scores when looking for standardised
                    if prefer_standardised and ('(/35)' in header or '(/50)' in header or '(/20)' in header):
                        continue
                    return header
        
        # Fall back to fuzzy matching
        for keyword in target_keywords:
            matches = get_close_matches(keyword.lower(), [h.lower() for h in headers], n=1, cutoff=0.6)
            if matches:
                # Find the original header (case-preserved)
                for header in headers:
                    if header.lower() == matches[0]:
                        return header
        
        return None
    
    def parse_csv(self, csv_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Parse CSV file and extract student data using smart column matching.
        Prioritizes "Standardised" scores over raw scores.
        """
        students = []
        csv_text = csv_bytes.decode('utf-8-sig')  # Handle BOM if present
        reader = csv.DictReader(io.StringIO(csv_text))
        
        # Get headers
        headers = reader.fieldnames or []
        if not headers:
            return students
        
        # Define target columns with keywords (in priority order)
        column_mapping = {
            'name': self._find_best_column_match(headers, ['Student Name', 'Name', 'student']),
            'reading': self._find_best_column_match(headers, ['Standardised Reading', 'Reading'], prefer_standardised=True),
            'writing': self._find_best_column_match(headers, ['Standardised Writing', 'Writing'], prefer_standardised=True),
            'qr': self._find_best_column_match(headers, ['Standardised QR', 'QR Score', 'Quantitative Reasoning'], prefer_standardised=True),
            'ar': self._find_best_column_match(headers, ['Standardised AR', 'AR Score', 'Abstract Reasoning'], prefer_standardised=True),
            'total': self._find_best_column_match(headers, ['Total Standard Score', 'Total Score', 'Total Standardised', 'Overall Score'], prefer_standardised=True),
        }
        
        # Validate that we found at least name column
        if not column_mapping['name']:
            raise ValueError("Could not find 'Student Name' column in CSV. Please ensure the CSV has a student name column.")
        
        # Parse rows
        for row in reader:
            try:
                name = row.get(column_mapping['name'], '').strip()
                
                # Skip empty names or junk rows (date headers, etc.)
                if not name:
                    continue
                
                # Skip date/time header rows
                if any(day in name.lower() for day in ['mon ', 'tue ', 'wed ', 'thu ', 'fri ', 'sat ', 'sun ']):
                    continue
                
                student = {
                    'name': name,
                    'reading': self._parse_score(row.get(column_mapping['reading'], '0') if column_mapping['reading'] else '0'),
                    'writing': self._parse_score(row.get(column_mapping['writing'], '0') if column_mapping['writing'] else '0'),
                    'qr': self._parse_score(row.get(column_mapping['qr'], '0') if column_mapping['qr'] else '0'),
                    'ar': self._parse_score(row.get(column_mapping['ar'], '0') if column_mapping['ar'] else '0'),
                    'total': self._parse_score(row.get(column_mapping['total'], '0') if column_mapping['total'] else '0'),
                }
                
                # Only add students with valid scores (at least one non-zero score)
                if any(student[key] > 0 for key in ['reading', 'writing', 'qr', 'ar', 'total']):
                    students.append(student)
            except Exception as e:
                # Skip rows with parsing errors
                continue
        
        return students
    
    def _parse_score(self, value: str) -> float:
        """Parse score from string, handling various formats."""
        try:
            # Remove any non-numeric characters except decimal point
            cleaned = ''.join(c for c in str(value) if c.isdigit() or c == '.')
            return float(cleaned) if cleaned else 0.0
        except:
            return 0.0
    
    def generate_pdf_report(self, student: Dict[str, Any]) -> bytes:
        """
        Generate a PDF performance report for a student.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=30,
            alignment=1,  # Center
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#34495E'),
            spaceAfter=12,
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=10,
        )
        
        # Title
        story.append(Paragraph("ASET Performance Report", title_style))
        story.append(Paragraph(f"<b>Student:</b> {student['name']}", heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Student's Exam Results Section
        story.append(Paragraph("<b>Student's Exam Results</b>", heading_style))
        
        # Scores table
        score_data = [
            ['Component', 'Score', 'Max Score'],
            ['Reading Comprehension', f"{student['reading']}", '35'],
            ['Writing', f"{student['writing']}", '20'],
            ['Quantitative Reasoning', f"{student['qr']}", '35'],
            ['Abstract Reasoning', f"{student['ar']}", '35'],
            ['Total Standard Score', f"{student['total']}", '125'],
        ]
        
        score_table = Table(score_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F8F5')),
        ]))
        
        story.append(score_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Performance Chart
        story.append(Paragraph("<b>Performance Overview</b>", heading_style))
        drawing = self._create_bar_chart(student)
        story.append(drawing)
        story.append(Spacer(1, 0.3*inch))
        
        # Analysis Section
        story.append(Paragraph("<b>Performance Analysis</b>", heading_style))
        
        # Calculate percentages
        reading_pct = (student['reading'] / 35) * 100
        writing_pct = (student['writing'] / 20) * 100
        qr_pct = (student['qr'] / 35) * 100
        ar_pct = (student['ar'] / 35) * 100
        
        analysis_text = f"""
        Your overall performance shows a total standard score of <b>{student['total']}</b> out of 125.<br/><br/>
        
        <b>Strengths:</b><br/>
        """
        
        strengths = []
        if reading_pct >= 70: strengths.append(f"Reading Comprehension ({reading_pct:.0f}%)")
        if writing_pct >= 70: strengths.append(f"Writing ({writing_pct:.0f}%)")
        if qr_pct >= 70: strengths.append(f"Quantitative Reasoning ({qr_pct:.0f}%)")
        if ar_pct >= 70: strengths.append(f"Abstract Reasoning ({ar_pct:.0f}%)")
        
        if strengths:
            analysis_text += "• " + "<br/>• ".join(strengths) + "<br/><br/>"
        else:
            analysis_text += "Continue working on all areas to improve your performance.<br/><br/>"
        
        analysis_text += "<b>Areas for Improvement:</b><br/>"
        
        improvements = []
        if reading_pct < 70: improvements.append(f"Reading Comprehension - Focus on comprehension strategies")
        if writing_pct < 70: improvements.append(f"Writing - Practice structured essay writing")
        if qr_pct < 70: improvements.append(f"Quantitative Reasoning - Review mathematical concepts")
        if ar_pct < 70: improvements.append(f"Abstract Reasoning - Practice pattern recognition")
        
        if improvements:
            analysis_text += "• " + "<br/>• ".join(improvements)
        else:
            analysis_text += "Maintain your excellent performance across all sections."
        
        story.append(Paragraph(analysis_text, body_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Next Steps Section
        story.append(Paragraph("<b>Next Steps</b>", heading_style))
        
        next_steps = """
        <b>1. Review Your Mistakes:</b> Carefully analyze the questions you got wrong. Understand why the correct answer is right.<br/><br/>
        <b>2. Practice Regularly:</b> Consistent practice is key to improvement. Set aside time each day for focused study.<br/><br/>
        <b>3. Seek Help When Needed:</b> Don't hesitate to ask teachers or tutors for clarification on difficult topics.<br/><br/>
        <b>4. Take Practice Tests:</b> Simulate exam conditions with timed practice tests to build stamina and confidence.<br/><br/>
        <b>5. Stay Positive:</b> Maintain a growth mindset. Every mistake is an opportunity to learn and improve.
        """
        
        story.append(Paragraph(next_steps, body_style))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_bar_chart(self, student: Dict[str, Any]) -> Drawing:
        """Create a bar chart showing student performance."""
        drawing = Drawing(400, 200)
        chart = VerticalBarChart()
        chart.x = 50
        chart.y = 50
        chart.height = 125
        chart.width = 300
        
        # Data: [student scores], [max scores]
        chart.data = [
            [student['reading'], student['writing'], student['qr'], student['ar']],
            [35, 20, 35, 35]
        ]
        
        chart.categoryAxis.categoryNames = ['Reading', 'Writing', 'QR', 'AR']
        chart.categoryAxis.labels.boxAnchor = 'ne'
        chart.categoryAxis.labels.dx = -8
        chart.categoryAxis.labels.dy = -2
        chart.categoryAxis.labels.angle = 30
        
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 40
        chart.valueAxis.valueStep = 10
        
        chart.bars[0].fillColor = colors.HexColor('#3498DB')
        chart.bars[1].fillColor = colors.HexColor('#95A5A6')
        
        drawing.add(chart)
        
        # Legend
        from reportlab.graphics.shapes import String, Rect
        legend_y = 180
        drawing.add(Rect(220, legend_y, 15, 10, fillColor=colors.HexColor('#3498DB'), strokeColor=None))
        drawing.add(String(240, legend_y+2, 'Your Score', fontSize=9))
        drawing.add(Rect(220, legend_y-15, 15, 10, fillColor=colors.HexColor('#95A5A6'), strokeColor=None))
        drawing.add(String(240, legend_y-13, 'Max Score', fontSize=9))
        
        return drawing
    
    def generate_email_template(self, student: Dict[str, Any]) -> str:
        """
        Generate a personalized email template for the student.
        """
        email = f"""Subject: Your ASET Mock Exam Performance Report

Dear {student['name']},

Thank you for taking the ASET Mock Examination. We are pleased to share your performance report.

Your Results:
---------------
Reading Comprehension: {student['reading']}/35
Writing: {student['writing']}/20
Quantitative Reasoning: {student['qr']}/35
Abstract Reasoning: {student['ar']}/35
Total Standard Score: {student['total']}/125

We have attached a detailed performance report PDF that includes:
• A comprehensive breakdown of your scores in each section
• Performance analysis highlighting your strengths and areas for improvement
• A visual chart comparing your performance across different components
• Personalized recommendations for your preparation

Next Steps:
-----------
1. Review the attached PDF report carefully
2. Focus on the "Areas for Improvement" section
3. Practice regularly with targeted exercises
4. Reach out to your tutors if you need clarification on any topics

Remember, this mock exam is a learning opportunity. Use the feedback to guide your preparation and improve your performance for the actual ASET examination.

If you have any questions about your results or need additional support, please don't hesitate to contact us.

Best wishes for your continued preparation!

Warm regards,
Everest Tutoring Team

---
This is an automated email. The attached report has been generated based on your mock exam performance.
"""
        return email
