ASET Marking System - Milestone 5: Web Frontend Completion
Context
We have completed M4 (Web Routes & API), which exposed the core marking logic via Flask endpoints (e.g., /mark/single/process, /batch/process). Now we must implement Milestone 5 (M5): The client-side logic and UI polish.

Goal
Implement the polished "Presentation Layer" that allows staff to interact with the backend asynchronously, ensuring the UI remains responsive during long processing tasks (like batch marking).

Constraints
Language: Vanilla JavaScript (ES6+) for client-side logic. No heavy frameworks (React/Vue).

Styling: Standard CSS3 with CSS Variables for branding.

Async: Use the fetch API for form submissions to prevent page reloads during processing.

Feedback: Must show a loading spinner during processing and "Flash" toast messages for success/errors.

Branding Colors: Primary: #3498DB (Blue), Success: #27AE60 (Green), Error: #E74C3C (Red).

Reference: API Interaction Contract (from M4)
Assume the backend routes configured in M4 behave as follows. You will write the JS to interact with them.

1. Single Marking Endpoint

URL: /mark/single/process

Method: POST (Multipart Form Data)

Inputs: student_name, writing_score, reading_sheet (File), qrar_sheet (File)

Response (Success): Binary Stream (ZIP file containing Report + Scans).

Response (Error): JSON {"detail": "Error description"}.

2. Batch Marking Endpoint

URL: /batch/process

Method: POST (Multipart Form Data)

Inputs: manifest (JSON File), sheets_zip (ZIP File).

Response: Binary Stream (ZIP file).

Detailed File Specifications
1. web/static/css/style.css
Responsibilities:

Spinner: Define a CSS animation (@keyframes spin) for a loading indicator.

Utilities: Classes for .hidden (display: none) and .disabled (opacity: 0.5, pointer-events: none).

Flash Messages: Styling for toast notifications that appear at the top-right (.flash, .flash-success, .flash-error).

Image Previews: Style for thumbnail images (.image-preview) that appear when a user selects a file.

2. web/static/js/app.js
Responsibilities: This is the core logic file. It must check the DOM for specific forms and attach event listeners.

class FlashManager:

show(message, type): Injects a div into the DOM with the message and auto-removes it after 5 seconds.

class FileInputHandler:

Listens to change events on <input type="file">.

If the file is an image, use FileReader to read it as a DataURL and set the src of the corresponding <img> preview element.

class FormHandler:

handleSubmit(event): Prevents default submission.

Loading State: Disables the submit button and injects the spinner HTML.

Fetch: Sends FormData to the action URL.

Response Handling:

If Content-Type is JSON (Error): Parse and show via FlashManager.

If Content-Type is Blob/File (Success): Create a temporary <a> tag with URL.createObjectURL(blob) to trigger the browser download, then reset the form.

Implementation Skeleton:

JavaScript

class FlashManager {
    show(message, type = 'info') {
        // Logic to append alert div to #flash-container
    }
}

class FormHandler {
    constructor(formId, options = {}) {
        this.form = document.getElementById(formId);
        if(this.form) {
            this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        // 1. Show Spinner
        // 2. fetch(action, { method: 'POST', body: new FormData(this.form) })
        // 3. Check response header (Blob vs JSON)
        // 4. Trigger download or show error
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Initialize handlers
    new FormHandler('marking-form');
    new FormHandler('batch-form');
});
3. web/templates/single.html & web/templates/batch.html (Modifications)
Responsibilities: You need to provide the updated HTML for the form sections to support the JS logic.

Add id="marking-form" and id="batch-form" to the forms.

Add data-preview="preview-img-id" attributes to file inputs so the JS knows which image tag to update.

Add a hidden "Results" section (id="results-section") that is toggled visible by the JS upon success.

Task: Generate the full code for:
web/static/css/style.css (Additions for spinner/flash/previews)

web/static/js/app.js (Complete logic)

web/templates/single.html (Updated form & result section)

web/templates/batch.html (Updated form & result section)

Ensure the JavaScript creates a smooth "App-like" feel where the page does not reload during marking, and downloads start automatically.