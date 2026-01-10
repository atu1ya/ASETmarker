"""Mock report generation service."""
import csv
import io
import os
from difflib import get_close_matches
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    PageBreak, Image, ListFlowable, ListItem
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Try to register Calibri font
try:
    pdfmetrics.registerFont(TTFont('Calibri', 'calibri.ttf'))
    pdfmetrics.registerFont(TTFont('Calibri-Bold', 'calibrib.ttf'))
    DEFAULT_FONT = 'Calibri'
    BOLD_FONT = 'Calibri-Bold'
except:
    DEFAULT_FONT = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'


# School minimum scores table (hardcoded)
SCHOOL_MINIMUM_SCORES = {
    'Perth Modern School': 244.34,
    'Willetton SHS': 235.98,
    'Shenton SHS': 231.55,
    'Rossmoyne SHS': 227.00,
    'Harrisdale SHS': 226.57,
    'Kelmscott SHS': 209.5,
}

# GATE Preparation Journey scores
GATE_JOURNEY_STAGES = [
    ('T3 Y4', 155),
    ('T4 Y4', 170),
    ('Hol MC/T1 Y5', 190),
    ('T2 Y5', 200),
    ('T3 Y5', 210),
    ('T4 Y5', 220),
    ('Hol MC', 230),
    ('Mock 1', 240),
    ('Mock 2', 250),
    ('Real Exam', 250),
]

# Reading Comprehension concepts mapping
READING_CONCEPTS = {
    'Understanding main ideas': ['1', '2', '6', '21', '26', '35'],
    'Inference and deduction': ['3', '5', '16', '17', '18', '22', '28', '34'],
    'Identifying key details': ['4', '7', '8', '9', '10', '11', '12', '15', '19', '20', '23', '24', '27', '29'],
    'Vocabulary context clues': ['14', '25', '31'],
    "Author's purpose and tone": ['13', '26'],
    'Cause and effect relationships': ['21', '22', '24'],
    'Understanding tone and attitude': ['16', '18', '32', '34'],
    'Figurative / Literary devices': ['30', '33'],
}

# QR Concepts mapping
QR_CONCEPTS = {
    'Fractions / Decimals': ['7', '28', '30', '31', '34', '35'],
    'Time': ['28'],
    'Algebra': ['6', '18', '21', '22'],
    'Geometry': ['1', '2', '3', '4', '5', '33'],
    'Graph / Data Interpretation': ['8', '9', '10', '12', '13', '32'],
    'Multiplication / Division': ['14', '15', '16', '17', '29'],
    'Area / Perimeter': ['3', '5'],
    'Ratios / Unit Conversions': ['19', '20', '22'],
    'Probability': ['26'],
    'Patterns / Sequences': ['23', '24', '25', '35'],
    'Percentages': ['11', '27'],
}


class MockReportService:
    """Service for generating mock performance reports from CSV data."""
    
    def __init__(self, concept_mapping: Optional[Dict] = None):
        """
        Initialize the service with optional concept mapping.
        
        Args:
            concept_mapping: Dictionary mapping subjects to concepts and question IDs.
                           If None, will use default hardcoded concepts.
        """
        self.concept_mapping = concept_mapping
        self.threshold = 0.51  # 51% threshold for "Done Well"
        
        # Get image paths
        self.base_path = Path(__file__).parent.parent
        self.images_path = self.base_path / 'static' / 'images'
    
    def _find_best_column_match(self, headers: List[str], target_keywords: List[str], prefer_standardised: bool = False) -> Optional[str]:
        """Find the best matching column header using fuzzy matching."""
        if prefer_standardised:
            standardised_headers = [h for h in headers if 'standardised' in h.lower() or 'standardized' in h.lower()]
            if standardised_headers:
                headers = standardised_headers
        
        for keyword in target_keywords:
            for header in headers:
                if keyword.lower() in header.lower():
                    if prefer_standardised and ('(/35)' in header or '(/50)' in header or '(/20)' in header):
                        continue
                    return header
        
        for keyword in target_keywords:
            matches = get_close_matches(keyword.lower(), [h.lower() for h in headers], n=1, cutoff=0.6)
            if matches:
                for header in headers:
                    if header.lower() == matches[0]:
                        return header
        
        return None
    
    def parse_csv(self, csv_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse CSV file and extract student data."""
        students = []
        csv_text = csv_bytes.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(csv_text))
        
        headers = reader.fieldnames or []
        if not headers or len(headers) < 2:
            raise ValueError("CSV must have at least 2 columns.")
        
        total_score_column = headers[-2]
        
        column_mapping = {
            'name': self._find_best_column_match(headers, ['Student Name', 'Name', 'student']),
            'reading': self._find_best_column_match(headers, ['Standardised Reading', 'Reading'], prefer_standardised=True),
            'writing': self._find_best_column_match(headers, ['Standardised Writing', 'Writing'], prefer_standardised=True),
            'qr': self._find_best_column_match(headers, ['Standardised QR', 'QR Score', 'Quantitative Reasoning'], prefer_standardised=True),
            'ar': self._find_best_column_match(headers, ['Standardised AR', 'AR Score', 'Abstract Reasoning'], prefer_standardised=True),
        }
        
        if not column_mapping['name']:
            raise ValueError("Could not find 'Student Name' column in CSV.")
        
        for row in reader:
            try:
                name = str(row.get(column_mapping['name'], '')).strip().title()
                if not name:
                    continue
                if any(day in name.lower() for day in ['mon ', 'tue ', 'wed ', 'thu ', 'fri ', 'sat ', 'sun ']):
                    continue
                
                student = {
                    'name': name,
                    'reading': self._parse_score(row.get(column_mapping['reading'], '0') if column_mapping['reading'] else '0'),
                    'writing': self._parse_score(row.get(column_mapping['writing'], '0') if column_mapping['writing'] else '0'),
                    'qr': self._parse_score(row.get(column_mapping['qr'], '0') if column_mapping['qr'] else '0'),
                    'ar': self._parse_score(row.get(column_mapping['ar'], '0') if column_mapping['ar'] else '0'),
                    'total': self._parse_score(row.get(total_score_column, '0')),
                }
                
                if any(student[key] > 0 for key in ['reading', 'writing', 'qr', 'ar', 'total']):
                    students.append(student)
            except Exception:
                continue
        
        return students
    
    def _parse_score(self, value: str) -> float:
        """Parse score from string."""
        try:
            cleaned = ''.join(c for c in str(value) if c.isdigit() or c == '.')
            return float(cleaned) if cleaned else 0.0
        except:
            return 0.0
    
    def _get_styles(self) -> Dict[str, ParagraphStyle]:
        """Get all paragraph styles for the PDF."""
        styles = getSampleStyleSheet()
        
        return {
            'title': ParagraphStyle(
                'Title',
                parent=styles['Normal'],
                fontName=DEFAULT_FONT,
                fontSize=14,
                leading=18,
                spaceAfter=6,
            ),
            'heading': ParagraphStyle(
                'Heading',
                parent=styles['Normal'],
                fontName=BOLD_FONT,
                fontSize=11,
                leading=14,
                spaceAfter=6,
                underline=True,
                textColor=colors.HexColor('#000000'),
            ),
            'body': ParagraphStyle(
                'Body',
                parent=styles['Normal'],
                fontName=DEFAULT_FONT,
                fontSize=10,
                leading=14,
                alignment=TA_JUSTIFY,
                spaceAfter=6,
            ),
            'body_bold': ParagraphStyle(
                'BodyBold',
                parent=styles['Normal'],
                fontName=BOLD_FONT,
                fontSize=10,
                leading=14,
                spaceAfter=6,
            ),
            'bullet': ParagraphStyle(
                'Bullet',
                parent=styles['Normal'],
                fontName=DEFAULT_FONT,
                fontSize=10,
                leading=14,
                leftIndent=20,
                spaceAfter=4,
            ),
            'small': ParagraphStyle(
                'Small',
                parent=styles['Normal'],
                fontName=DEFAULT_FONT,
                fontSize=9,
                leading=12,
                textColor=colors.HexColor('#666666'),
            ),
            'highlight': ParagraphStyle(
                'Highlight',
                parent=styles['Normal'],
                fontName=BOLD_FONT,
                fontSize=10,
                leading=14,
                backColor=colors.yellow,
            ),
        }
    
    def _add_header(self, canvas, doc):
        """Add header with logo to each page."""
        canvas.saveState()
        
        # Try to add header image
        header_path = self.images_path / 'header.png'
        if header_path.exists():
            canvas.drawImage(str(header_path), 
                           doc.width + doc.leftMargin - 2*inch, 
                           doc.height + doc.topMargin - 0.3*inch,
                           width=2*inch, height=0.6*inch,
                           preserveAspectRatio=True)
        else:
            # Fallback: Draw text logo
            canvas.setFont(BOLD_FONT, 16)
            canvas.setFillColor(colors.HexColor('#00A0E3'))
            canvas.drawRightString(doc.width + doc.leftMargin, 
                                  doc.height + doc.topMargin, 
                                  "everest tutoring")
        
        canvas.restoreState()
    
    def generate_pdf_report(self, student: Dict[str, Any]) -> bytes:
        """Generate a multi-page PDF performance report matching the Word template."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            topMargin=1*inch,
            bottomMargin=0.75*inch,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch
        )
        
        story = []
        styles = self._get_styles()
        
        # === PAGE 1 ===
        story.extend(self._build_page1(student, styles))  # Fixed: use extend() not append()
        story.append(PageBreak())
        
        # === PAGE 2 ===
        story.extend(self._build_page2(student, styles))
        story.append(PageBreak())
        
        # === PAGE 3 ===
        story.extend(self._build_page3(student, styles))
        story.append(PageBreak())
        
        # === PAGE 4 ===
        story.extend(self._build_page4(student, styles))
        story.append(PageBreak())
        
        # === PAGE 5 ===
        story.extend(self._build_page5(styles))
        story.append(PageBreak())
        
        # === PAGE 6 ===
        story.extend(self._build_page6(styles))
        
        # === SANITIZE STORY ===
        # Flatten any nested lists and validate all items are proper Flowables
        clean_story = []
        for i, item in enumerate(story):
            if isinstance(item, list):
                # Log warning and flatten
                print(f"WARNING: Story item {i} is a list (length {len(item)}), flattening...")
                clean_story.extend(item)
            else:
                clean_story.append(item)
        
        # Validation: Check for any remaining non-Flowable objects
        from reportlab.platypus.flowables import Flowable
        for i, item in enumerate(clean_story):
            if not isinstance(item, Flowable):
                print(f"ERROR: Story item {i} is not a Flowable: {type(item)} - {repr(item)[:100]}")
        
        # Build with header on each page
        doc.build(clean_story, onFirstPage=self._add_header, onLaterPages=self._add_header)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _build_page1(self, student: Dict[str, Any], styles: Dict) -> List:
        """Build page 1 content."""
        elements = []
        
        # Title
        elements.append(Paragraph(f"<u>ASET Performance Report for {student['name']}</u>", styles['title']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Dear Parents/Students
        elements.append(Paragraph("<b>Dear Parents/Students</b>", styles['body_bold']))
        elements.append(Spacer(1, 0.15*inch))
        
        # Intro paragraph
        intro_text = """It's important to remember that this report reflects the results of the MOCK Academic 
Selective Entrance Test (ASET), which is an <b><u>early opportunity</u></b> to assess your child's current 
abilities in preparation for the real ASET exam. This test was designed to highlight areas 
where your child excels and areas that may need improvement, and it's not uncommon for 
students to score lower in their first few attempts (with practice, they'll improve!).<br/>
<b>For Year 5 students, this is a key part of preparation before the real ASET exam in Term 1 
next year. For Year 4 students, this provides an early start and a chance to build strong 
foundations ahead of time.</b>"""
        elements.append(Paragraph(intro_text, styles['body']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Please keep in mind
        elements.append(Paragraph("<b>Please keep in mind the following:</b>", styles['body_bold']))
        elements.append(Spacer(1, 0.1*inch))
        
        bullet_points = [
            "The purpose of this mock exam is to help identify areas that need attention, not to provide a final assessment of your child's abilities. There is still plenty of time to prepare for the real exam, and improvement is possible with focused practice and guidance.",
            "Scores will improve: some students may not perform as well as they hoped in this exam, but this is expected. The scores provided in this report give a snapshot of where your child is today, not where they will be after continued study and preparation. <b><u>We will help prepare your child to be at the level they need to be to succeed in this exam.</u></b>",
            "Constructive feedback: The report includes detailed feedback on each section, which is meant to guide future preparation. Use this as an opportunity to tailor your child's study habits and focus on specific areas of growth.",
            "A stepping stone: This mock exam is a valuable learning experience, not a definitive statement about your child's potential. With consistent effort and the right strategies, there is ample opportunity for improvement over the coming months.",
        ]
        
        for point in bullet_points:
            elements.append(Paragraph(f"- {point}", styles['bullet']))
            elements.append(Spacer(1, 0.08*inch))
        
        elements.append(Spacer(1, 0.2*inch))
        
        # GATE Preparation Journey
        elements.append(Paragraph("<b><u>GATE Preparation Journey – Target Scores for Year 4 and 5 Students</u></b>", styles['body_bold']))
        elements.append(Spacer(1, 0.15*inch))
        
        # Journey table
        journey_data = [
            ['Stage'] + [stage[0] for stage in GATE_JOURNEY_STAGES],
            ['Score'] + [str(stage[1]) if stage[1] != 250 or i < len(GATE_JOURNEY_STAGES)-1 else '~250' 
                        for i, stage in enumerate(GATE_JOURNEY_STAGES)],
        ]
        
        journey_table = Table(journey_data, colWidths=[0.5*inch] + [0.55*inch]*len(GATE_JOURNEY_STAGES))
        journey_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E0E0')),
        ]))
        elements.append(journey_table)
        elements.append(Spacer(1, 0.1*inch))
        
        elements.append(Paragraph(
            "These scores are indicative only. Many students start below these benchmarks. Steady progress, not perfection, is the goal.",
            styles['small']
        ))
        
        return elements
    
    def _build_page2(self, student: Dict[str, Any], styles: Dict) -> List:
        """Build page 2 content - scores and school comparison."""
        elements = []
        
        # Intro text
        intro = """This report contains your child's results in the Mock Academic Selective Entrance Test 
(ASET), including:"""
        elements.append(Paragraph(intro, styles['body']))
        
        elements.append(Paragraph("● Your child's standard score in each of the four tests", styles['bullet']))
        elements.append(Paragraph("● Your child's Total Standard Score (TSS) which is the <u>sum total</u> of the four individual standard scores.", styles['bullet']))
        elements.append(Spacer(1, 0.1*inch))
        
        elements.append(Paragraph("<b>Please note this is a Performance Report only, not an offer of placement.</b>", styles['body_bold']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Scores table
        score_data = [
            ['', 'Your child\'s score', 'Minimum Score 2025\n(all of WA)', 'Maximum Score 2025\n(all of WA)'],
            ['Reading Comprehension', f"{student['reading']:.2f}" if student['reading'] else '', '22.93', '91.69'],
            ['Communicating Ideas in\nWriting', f"{student['writing']:.2f}" if student['writing'] else '', '0', '76.86'],
            ['Quantitative Reasoning', f"{student['qr']:.2f}" if student['qr'] else '', '28.23', '95.11'],
            ['Abstract Reasoning', f"{student['ar']:.2f}" if student['ar'] else '', '23.04', '86.11'],
            ['Total Standard Score', f"{student['total']:.2f}" if student['total'] else '', '', ''],
        ]
        
        score_table = Table(score_data, colWidths=[2*inch, 1.3*inch, 1.5*inch, 1.5*inch])
        score_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00A0E3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#00A0E3')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(score_table)
        elements.append(Spacer(1, 0.25*inch))
        
        # School minimum scores
        elements.append(Paragraph(
            "To get an idea of what level your child is at right now, here are some of the MINIMUM entrance scores in 2024 for some of the popular GATE schools.",
            styles['body']
        ))
        elements.append(Spacer(1, 0.1*inch))
        
        school_data = [[school, f"{score:.2f}" if isinstance(score, float) else str(score)] 
                      for school, score in SCHOOL_MINIMUM_SCORES.items()]
        
        school_table = Table(school_data, colWidths=[2.5*inch, 1.5*inch])
        school_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#E8E8E8')),  # Highlight Harrisdale
        ]))
        elements.append(school_table)
        elements.append(Spacer(1, 0.1*inch))
        
        elements.append(Paragraph(
            "<i>Note: These are 2025 entrance scores for Year 7 GATE programs. Year 4 students still have over a year to build up to this level!</i>",
            styles['small']
        ))
        elements.append(Spacer(1, 0.25*inch))
        
        # Reading Comprehension section header
        elements.append(Paragraph("<b><u>Reading Comprehension</u></b>", styles['heading']))
        elements.append(Spacer(1, 0.1*inch))
        
        elements.append(Paragraph("<b>Tips and Tricks to boost your score:</b>", styles['body_bold']))
        
        reading_tips = [
            "<b>Expand Your Vocabulary:</b> A strong vocabulary helps with understanding complex texts. <u>Read widely and learn new words regularly.</u>",
            "<b>Try different approaches</b> -> Try skimming text first then going to questions and locating answers. Then try reading the question first and looking for the answer within. See what works for <b>YOU</b>",
            "<b>Context Clues:</b> If you're unsure about a word or phrase, use clues from the surrounding text to infer its meaning.",
            "<b>Look for Keywords:</b> Match keywords or phrases in the questions to the corresponding parts of the passage. This can guide you to the right answer.",
            "<b>Eliminate Wrong Answers:</b> Use the process of elimination to narrow down your choices for some questions. Cross out options that are clearly incorrect.",
            "Guess if you're stuck in the exam (some chance of getting a question right is better than 0 chance)",
        ]
        
        for tip in reading_tips:
            elements.append(Paragraph(f"● {tip}", styles['bullet']))
        
        return elements
    
    def _build_page3(self, student: Dict[str, Any], styles: Dict) -> List:
        """Build page 3 - Reading concepts table and Writing section."""
        elements = []
        
        # Reading Concepts Table
        reading_table_data = [['Concept Tested', 'Question Numbers', 'Done Well', 'Room for Improvement']]
        
        for concept, questions in READING_CONCEPTS.items():
            reading_table_data.append([concept, ', '.join(questions), '', ''])
        
        reading_table = Table(reading_table_data, colWidths=[2*inch, 1.8*inch, 0.9*inch, 1.3*inch])
        reading_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00A0E3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(reading_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Writing Section
        elements.append(Paragraph("<b><u>Communicating Ideas in Writing</u></b>", styles['heading']))
        elements.append(Paragraph(
            "Please refer to the writing marking key for specific feedback about your child's writing.",
            styles['body']
        ))
        
        return elements
    
    def _build_page4(self, student: Dict[str, Any], styles: Dict) -> List:
        """Build page 4 - QR concepts and AR tips."""
        elements = []
        
        # QR Section
        elements.append(Paragraph("<b><u>Quantitative Reasoning:</u></b>", styles['heading']))
        elements.append(Spacer(1, 0.1*inch))
        
        qr_table_data = [['Concept Tested', 'Question Numbers', 'Done Well', 'Room for Improvement']]
        
        for concept, questions in QR_CONCEPTS.items():
            qr_table_data.append([concept, ', '.join(questions), '', ''])
        
        qr_table = Table(qr_table_data, colWidths=[2*inch, 1.8*inch, 0.9*inch, 1.3*inch])
        qr_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00A0E3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(qr_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # AR Section
        elements.append(Paragraph("<b><u>Abstract Reasoning:</u></b>", styles['heading']))
        elements.append(Spacer(1, 0.1*inch))
        
        elements.append(Paragraph("<b>Tips and Tricks to boost your score:</b>", styles['body_bold']))
        
        ar_tips = [
            "Having a checklist/mnemonic to work through to find patterns quickly and effectively e.g. SCANS",
            "   o Shape: Identify the shapes in the pattern. Note any changes or repetitions.",
            "   o Colour: Observe the <u>colors</u> used. Look for any patterns in <u>color</u> changes or sequences.",
            "   o Arrangement: Check the arrangement of shapes or objects. Notice if they are arranged in a specific order or pattern.",
            "   o Number: Count the number of shapes or objects. Determine if there's a pattern in their numbers.",
            "   o Symmetry: Look for symmetry in the pattern. See if there are mirrored or symmetrical elements.",
            "Practice Visualizing Patterns: Regularly practice identifying patterns (ie making sure homework and weekly booklets are done and done properly)",
            "Focus on accuracy first then focus on speed -> Make sure you can get questions right untimed before worrying about speeding up",
            "Keep track of patterns you weren't able to figure out by yourself -> Write them down and look through them regularly to keep familiar with these patterns",
            "Guess if you're stuck in the exam (1/4 chance of getting a question right is better than 0 chance)",
        ]
        
        for tip in ar_tips:
            if tip.startswith("   o"):
                elements.append(Paragraph(tip, styles['bullet']))
            else:
                elements.append(Paragraph(f"● {tip}", styles['bullet']))
        
        return elements
    
    def _build_page5(self, styles: Dict) -> List:
        """Build page 5 - Progress and Common Mistakes."""
        elements = []
        
        elements.append(Paragraph("<b>Students are Making Good Progress!</b>", styles['heading']))
        elements.append(Spacer(1, 0.1*inch))
        
        progress_text = """Despite this being the first mock exam, we are already seeing notable progress in several key areas:"""
        elements.append(Paragraph(progress_text, styles['body']))
        
        progress_points = [
            "<b>Application of Strategies:</b> Students who applied the strategies we've taught, such as using context clues in reading comprehension or pattern recognition in abstract reasoning, performed noticeably better.",
            "<b>Effort and Engagement:</b> It's clear that students are putting in the effort, and that determination will only lead to more improvements in the months ahead.",
        ]
        
        for point in progress_points:
            elements.append(Paragraph(f"● {point}", styles['bullet']))
        
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(
            "We encourage everyone to keep up this momentum, as it's laying the foundation for even greater success in future mock exams!",
            styles['body']
        ))
        elements.append(Spacer(1, 0.2*inch))
        
        # Common Mistakes
        elements.append(Paragraph("<b>Common Mistakes</b>", styles['heading']))
        elements.append(Paragraph(
            "There were certain areas that students made errors in that we noticed, they are highlighted below:",
            styles['body']
        ))
        elements.append(Spacer(1, 0.1*inch))
        
        mistakes = [
            "<b>Leaving Questions Blank:</b> Students are leaving a lot of marks on the table by not attempting <u>all</u> of the questions. Even if they don't have enough time to <u>actually</u> attempt each question, as soon as they hear that there is 1 minute left, they should guess the questions they didn't finish, so they at least have a 25% chance of getting it right.",
            "<b>Spending too long on Questions:</b> Students usually have 1 minute or less per question type, they should keep a mental clock on their head so when they are spending too long on a question, they should either guess it or make a note of it to come back to it later and move on. They do not have enough time to thoroughly finish every question. <u>It is clear that students need more practice under timed conditions so that they develop the mental timing.</u>",
        ]
        
        for mistake in mistakes:
            elements.append(Paragraph(f"● {mistake}", styles['bullet']))
            elements.append(Spacer(1, 0.08*inch))
        
        return elements
    
    def _build_page6(self, styles: Dict) -> List:
        """Build page 6 - Closing and next steps."""
        elements = []
        
        closing_text = """This was a <b><u>mock</u></b> exam, and there is still of time before the real ASET: under 3 months for 
Year 5s, and 14 months for Year 4s. Even if your child didn't score as hoped, it's not too late. 
With the right guidance and effort, they can absolutely work towards <u>gaining entry into</u> top 
GATE schools."""
        elements.append(Paragraph(closing_text, styles['body']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Highlighted call to action
        cta_text = """<b>Our GATE classes will resume in <font backColor="yellow">January for the GATE HOLIDAY MASTERCLASS</font> during the 
week of <font backColor="yellow">19th - 25th Jan & 27th Jan - Feb 1st</font>. We also have weekly classes from 
Term 1 2026 from the week of Feb 2nd - Feb 8th. If you'd like your child to continue, 
please let us know at your earliest convenience so we can confirm their place. We're 
looking forward to supporting them next year.</b>"""
        elements.append(Paragraph(cta_text, styles['body']))
        
        return elements
    
    def _create_bar_chart(self, student: Dict[str, Any]) -> Drawing:
        """Create a bar chart showing student performance vs max scores."""
        drawing = Drawing(450, 220)
        chart = VerticalBarChart()
        chart.x = 60
        chart.y = 40
        chart.height = 150
        chart.width = 350
        
        chart.data = [
            [student['reading'], student['writing'], student['qr'], student['ar']],
            [35, 20, 35, 35]
        ]
        
        chart.categoryAxis.categoryNames = ['Reading', 'Writing', 'QR', 'AR']
        chart.categoryAxis.labels.fontName = DEFAULT_FONT
        chart.categoryAxis.labels.fontSize = 9
        
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 40
        chart.valueAxis.valueStep = 10
        chart.valueAxis.labels.fontName = DEFAULT_FONT
        chart.valueAxis.labels.fontSize = 9
        
        chart.bars[0].fillColor = colors.HexColor('#3498DB')
        chart.bars[1].fillColor = colors.HexColor('#95A5A6')
        
        chart.barWidth = 20
        chart.groupSpacing = 15
        
        drawing.add(chart)
        
        # Legend
        legend_y = 200
        drawing.add(Rect(280, legend_y, 15, 10, fillColor=colors.HexColor('#3498DB'), strokeColor=None))
        drawing.add(String(300, legend_y+2, 'Your Score', fontName=DEFAULT_FONT, fontSize=9))
        drawing.add(Rect(280, legend_y-15, 15, 10, fillColor=colors.HexColor('#95A5A6'), strokeColor=None))
        drawing.add(String(300, legend_y-13, 'Max Score', fontName=DEFAULT_FONT, fontSize=9))
        
        return drawing
