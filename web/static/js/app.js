/**
 * ASET Marking System - Main JavaScript
 */

class FlashManager {
    constructor() {
        this.container = document.getElementById('flash-container');
        this.autoHideDelay = 5000;
    }

    show(message, type = 'info') {
        const flash = document.createElement('div');
        flash.className = `flash flash-${type}`;
        flash.innerHTML = `
            <span>${message}</span>
            <button class="flash-close" type="button">×</button>
        `;

        if (this.container) {
            this.container.appendChild(flash);
            const closeBtn = flash.querySelector('.flash-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => flash.remove());
            }

            setTimeout(() => {
                flash.style.animation = 'slideIn 0.3s ease reverse';
                setTimeout(() => flash.remove(), 300);
            }, this.autoHideDelay);
        }
    }

    success(message) {
        this.show(message, 'success');
    }

    error(message) {
        this.show(message, 'error');
    }

    warning(message) {
        this.show(message, 'warning');
    }

    info(message) {
        this.show(message, 'info');
    }
}

const flash = new FlashManager();

class FileInputHandler {
    constructor(inputElement, previewElement = null) {
        this.input = inputElement;
        this.preview = previewElement;
        this.wrapper = inputElement.closest('.file-input-wrapper');

        if (this.input) {
            this.input.addEventListener('change', (event) => this.handleChange(event));
        }
    }

    handleChange(event) {
        const file = event.target.files[0];
        if (!file) {
            return;
        }

        if (this.wrapper) {
            let nameEl = this.wrapper.querySelector('.file-name');
            if (!nameEl) {
                nameEl = document.createElement('div');
                nameEl.className = 'file-name';
                this.wrapper.appendChild(nameEl);
            }
            nameEl.textContent = file.name;
        }

        if (this.preview && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (loadEvent) => {
                this.preview.src = loadEvent.target.result;
                this.preview.classList.add('show');
            };
            reader.readAsDataURL(file);
        }
    }
}

class FormHandler {
    constructor(formElement, options = {}) {
        this.form = formElement;
        this.submitBtn = formElement.querySelector('[type="submit"]');
        this.options = {
            onSuccess: options.onSuccess || (() => {}),
            onError: options.onError || ((err) => flash.error(err)),
            resetOnSuccess: options.resetOnSuccess !== false,
            downloadResponse: options.downloadResponse || false,
        };

        this.form.addEventListener('submit', (event) => this.handleSubmit(event));
    }

    setLoading(loading) {
        if (!this.submitBtn) {
            return;
        }

        if (loading) {
            this.submitBtn.disabled = true;
            this.originalText = this.submitBtn.innerHTML;
            this.submitBtn.innerHTML = '<span class="spinner"></span> Processing...';
        } else {
            this.submitBtn.disabled = false;
            if (this.originalText) {
                this.submitBtn.innerHTML = this.originalText;
            }
        }
    }

    async handleSubmit(event) {
        event.preventDefault();
        this.setLoading(true);

        try {
            const formData = new FormData(this.form);
            const response = await fetch(this.form.action, {
                method: 'POST',
                body: formData,
            });

            if (this.options.downloadResponse) {
                await this.handleDownloadResponse(response);
            } else {
                await this.handleJsonResponse(response);
            }
        } catch (error) {
            this.options.onError(error.message || 'Unexpected error');
        } finally {
            this.setLoading(false);
        }
    }

    async handleDownloadResponse(response) {
        if (!response.ok) {
            let errorDetail = 'Processing failed';
            try {
                const errorPayload = await response.json();
                errorDetail = errorPayload.detail || errorDetail;
            } catch (parseErr) {
                console.warn('Failed to parse error payload', parseErr);
            }
            throw new Error(errorDetail);
        }

        const blob = await response.blob();
        let filename = 'download.zip';
        const contentDisposition = response.headers.get('Content-Disposition');
        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?([^";]+)"?/i);
            if (match) {
                filename = match[1];
            }
        }

        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(url);

        this.options.onSuccess(response);
        if (this.options.resetOnSuccess) {
            this.form.reset();
        }
    }

    async handleJsonResponse(response) {
        const payload = await response.json();
        if (response.ok) {
            this.options.onSuccess(payload);
            if (this.options.resetOnSuccess) {
                this.form.reset();
            }
        } else {
            throw new Error(payload.detail || 'Request failed');
        }
    }
}

function updateConfigStatus(summary) {
    const statusEl = document.getElementById('config-status');
    if (!statusEl) {
        return;
    }

    statusEl.className = 'config-status configured';
    const subjects = Array.isArray(summary.subjects_mapped) ? summary.subjects_mapped.join(', ') : 'N/A';
    statusEl.innerHTML = `
        <span class="config-status-icon">✓</span>
        <div>
            <strong>Configuration Loaded</strong>
            <div class="text-muted">
                Reading: ${summary.reading_questions} questions ·
                QR/AR: ${summary.qrar_questions} questions ·
                Subjects: ${subjects}
            </div>
        </div>
    `;
}

function enableMarkingModes() {
    document.querySelectorAll('.mode-card.disabled').forEach((card) => {
        card.classList.remove('disabled');
    });
}

function initConfigurationForm() {
    const form = document.getElementById('config-form');
    if (!form) {
        return;
    }

    new FormHandler(form, {
        onSuccess: (data) => {
            flash.success('Configuration loaded successfully!');
            if (data && data.summary) {
                updateConfigStatus(data.summary);
                enableMarkingModes();
            }
        },
        onError: (err) => {
            flash.error(`Configuration error: ${err}`);
        },
        resetOnSuccess: false,
    });
}

function initSingleMarkingForm() {
    const form = document.getElementById('marking-form');
    if (!form) {
        return;
    }

    document.querySelectorAll('.file-input-wrapper input[type="file"]').forEach((input) => {
        const previewId = input.dataset.preview;
        const preview = previewId ? document.getElementById(previewId) : null;
        new FileInputHandler(input, preview);
    });

    new FormHandler(form, {
        downloadResponse: true,
        onSuccess: () => {
            flash.success('Marking complete! Download started.');
            const formContainer = document.getElementById('marking-form-container');
            const resultsSection = document.getElementById('results-section');
            if (formContainer && resultsSection) {
                formContainer.classList.add('hidden');
                resultsSection.classList.remove('hidden');
            }
        },
        onError: (err) => {
            flash.error(`Marking failed: ${err}`);
        },
    });
}

function initBatchForm() {
    const form = document.getElementById('batch-form');
    if (!form) {
        return;
    }

    document.querySelectorAll('.file-input-wrapper input[type="file"]').forEach((input) => {
        new FileInputHandler(input);
    });

    new FormHandler(form, {
        downloadResponse: true,
        onSuccess: () => {
            flash.success('Batch processing complete! Download started.');
            const formContainer = document.getElementById('batch-form-container');
            const resultsSection = document.getElementById('results-section');
            if (formContainer && resultsSection) {
                formContainer.classList.add('hidden');
                resultsSection.classList.remove('hidden');
            }
        },
        onError: (err) => {
            flash.error(`Batch processing failed: ${err}`);
        },
    });
}

function resetAndShowForm(formContainerId, resultsSectionId) {
    const formContainer = document.getElementById(formContainerId);
    const resultsSection = document.getElementById(resultsSectionId);

    if (formContainer && resultsSection) {
        const form = formContainer.querySelector('form');
        if (form) {
            form.reset();
        }

        formContainer.classList.remove('hidden');
        resultsSection.classList.add('hidden');
    }

    document.querySelectorAll('.image-preview').forEach((preview) => {
        preview.classList.remove('show');
        preview.src = '';
    });

    document.querySelectorAll('.file-name').forEach((label) => label.remove());
}

window.resetAndShowForm = resetAndShowForm;

document.addEventListener('DOMContentLoaded', () => {
    initConfigurationForm();
    initSingleMarkingForm();
    initBatchForm();

    document.querySelectorAll('.file-input-wrapper input[type="file"]').forEach((input) => {
        if (!input._handler) {
            input._handler = new FileInputHandler(input);
        }
    });
});
