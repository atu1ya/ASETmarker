ASET Marking System - Milestone 4: Web Backend Integration
Context
We have completed M2 (Core Marking Services) and M3 (PDF Generation). We now have functional services for marking, analysis, reporting, and annotation. We are currently in Milestone 4 (M4).

Goal: Update the FastAPI routes (marking.py and batch.py) to replace the current stubs with real logic. These routes must orchestrate the entire marking pipeline using the services and return a downloadable ZIP file containing the results.

Constraints:

In-Memory Only: Do not save files to disk. Use io.BytesIO and zipfile.ZipFile for all file handling.

Error Handling: Return clear HTTPException (400) if files are invalid or configuration is missing.

Dependencies: Use the existing dependency require_configuration to ensure answer keys are loaded.

Reference: Service Interfaces
Assume the following services are imported and available in web.services.

Python

# web/services/marker.py
class MarkingService:
    def process_single_subject(self, request: MarkingRequest) -> SubjectResult: ...

# web/services/analysis.py
class AnalysisService:
    def compile_full_analysis(self, student_name, writing_score, reading_result, qrar_result, concept_map) -> FullAnalysis: ...

# web/services/report.py
class ReportService:
    def generate_student_report(self, analysis: FullAnalysis) -> bytes: ...

# web/services/annotator.py
class AnnotatorService:
    def annotate_sheet(self, result: SubjectResult) -> bytes: ...
Detailed File Specifications
1. web/routes/marking.py
Task: Implement the POST /mark/single/process endpoint.

Logic Flow:

Inputs: student_name (str), writing_score (int), reading_sheet (UploadFile), qrar_sheet (UploadFile).

Validation: Ensure config (answer keys) is present via Depends(require_configuration).

Read Files: await file.read() for both images.

Marking:

Instantiate MarkingService.

Call process_single_subject for Reading (use config.reading_answers and config/aset_reading_template.json).

Call process_single_subject for QR/AR (use config.qrar_answers and config/aset_qrar_template.json).

Analysis:

Instantiate AnalysisService.

Call compile_full_analysis with the results and config.concept_mapping.

Artifact Generation:

Use ReportService to generate the PDF report bytes.

Use AnnotatorService to generate annotated PDF bytes for both sheets.

Create a JSON string/bytes for the raw results data (serialize FullAnalysis).

ZIP Packaging:

Create an in-memory ZIP file (io.BytesIO).

Add files:

[Student]_Report.pdf

[Student]_Reading_Marked.pdf

[Student]_QRAR_Marked.pdf

[Student]_results.json

Response: Return a StreamingResponse with the ZIP bytes (media_type application/zip).

2. web/routes/batch.py
Task: Implement the POST /batch/process endpoint.

Logic Flow:

Inputs: manifest (UploadFile JSON), sheets_zip (UploadFile ZIP).

Manifest Parsing: Decode the manifest JSON. Expected structure:

JSON

{ "students": [ { "name": "John", "writing_score": 50, "reading_file": "r.png", "qrar_file": "q.png" } ] }
ZIP Handling:

Read the uploaded sheets_zip into memory zipfile.ZipFile.

Create a new output in-memory ZIP for the results.

Processing Loop:

Iterate through each student in the manifest.

Extract: Read the specific PNG bytes for that student from the input ZIP. Handle KeyError if file missing.

Pipeline: Run the exact same Marking -> Analysis -> Report -> Annotation pipeline as the Single route.

Archive: Write the resulting PDFs/JSON into the output ZIP, placing them inside a folder named Student_Name/.

Response: Return StreamingResponse with the final batch ZIP.

Generate the complete code for:

web/routes/marking.py

web/routes/batch.py

Note: Ensure you import dataclasses.asdict and json to serialize the results for the JSON output file. Use pathlib to reference the template paths (e.g. Path("config/aset_reading_template.json")).