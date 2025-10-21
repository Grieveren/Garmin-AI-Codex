/**
 * Reusable Modal System
 * Provides custom modals to replace browser confirm() and prompt() dialogs
 */

class Modal {
    constructor() {
        this.modalContainer = null;
        this.resolveCallback = null;
    }

    /**
     * Show confirmation dialog (replaces confirm())
     * @param {string} message - Confirmation message
     * @param {object} options - Optional configuration {title, confirmText, cancelText, variant}
     * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
     */
    confirm(message, options = {}) {
        const {
            title = 'Confirm',
            confirmText = 'Confirm',
            cancelText = 'Cancel',
            variant = 'warning' // 'warning', 'danger', 'info'
        } = options;

        return new Promise((resolve) => {
            this.resolveCallback = resolve;

            // Create modal structure
            const modal = this.createModalStructure();
            modal.classList.add(`modal-${variant}`);

            // Header
            const header = document.createElement('div');
            header.className = 'modal-header';

            const titleEl = document.createElement('h3');
            titleEl.className = 'modal-title';
            titleEl.textContent = title;
            header.appendChild(titleEl);

            // Body
            const body = document.createElement('div');
            body.className = 'modal-body';

            const messageEl = document.createElement('p');
            messageEl.className = 'modal-message';
            messageEl.textContent = message;
            body.appendChild(messageEl);

            // Footer
            const footer = document.createElement('div');
            footer.className = 'modal-footer';

            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn btn-secondary';
            cancelBtn.textContent = cancelText;
            cancelBtn.addEventListener('click', () => {
                this.close(false);
            });

            const confirmBtn = document.createElement('button');
            confirmBtn.className = `btn btn-${variant === 'danger' ? 'danger' : 'primary'}`;
            confirmBtn.textContent = confirmText;
            confirmBtn.addEventListener('click', () => {
                this.close(true);
            });

            footer.appendChild(cancelBtn);
            footer.appendChild(confirmBtn);

            // Assemble modal
            const content = modal.querySelector('.modal-content');
            content.appendChild(header);
            content.appendChild(body);
            content.appendChild(footer);

            // Show modal
            this.show(modal);

            // Focus confirm button
            confirmBtn.focus();

            // ESC to cancel
            this.addEscapeHandler(false);
        });
    }

    /**
     * Show form dialog (replaces prompt())
     * @param {string} message - Form message/description
     * @param {Array} fields - Array of field configurations
     * @param {object} options - Optional configuration {title, submitText, cancelText}
     * @returns {Promise<object|null>} - Resolves to field values object or null if cancelled
     */
    form(message, fields, options = {}) {
        const {
            title = 'Input Required',
            submitText = 'Submit',
            cancelText = 'Cancel'
        } = options;

        return new Promise((resolve) => {
            this.resolveCallback = resolve;

            // Create modal structure
            const modal = this.createModalStructure();

            // Header
            const header = document.createElement('div');
            header.className = 'modal-header';

            const titleEl = document.createElement('h3');
            titleEl.className = 'modal-title';
            titleEl.textContent = title;
            header.appendChild(titleEl);

            // Body
            const body = document.createElement('div');
            body.className = 'modal-body';

            if (message) {
                const messageEl = document.createElement('p');
                messageEl.className = 'modal-message';
                messageEl.textContent = message;
                body.appendChild(messageEl);
            }

            // Create form
            const form = document.createElement('form');
            form.className = 'modal-form';

            const fieldElements = {};

            fields.forEach(field => {
                const fieldGroup = document.createElement('div');
                fieldGroup.className = 'form-group';

                const label = document.createElement('label');
                label.className = 'form-label';
                label.textContent = field.label;
                label.setAttribute('for', `modal-field-${field.name}`);

                let input;
                if (field.type === 'textarea') {
                    input = document.createElement('textarea');
                    input.rows = field.rows || 3;
                } else {
                    input = document.createElement('input');
                    input.type = field.type || 'text';
                }

                input.className = 'form-control';
                input.id = `modal-field-${field.name}`;
                input.name = field.name;
                input.placeholder = field.placeholder || '';

                if (field.required) {
                    input.required = true;
                    label.textContent += ' *';
                }

                if (field.value !== undefined) {
                    input.value = field.value;
                }

                if (field.min !== undefined) input.min = field.min;
                if (field.max !== undefined) input.max = field.max;
                if (field.step !== undefined) input.step = field.step;

                fieldElements[field.name] = input;

                fieldGroup.appendChild(label);
                fieldGroup.appendChild(input);
                form.appendChild(fieldGroup);
            });

            body.appendChild(form);

            // Footer
            const footer = document.createElement('div');
            footer.className = 'modal-footer';

            const cancelBtn = document.createElement('button');
            cancelBtn.type = 'button';
            cancelBtn.className = 'btn btn-secondary';
            cancelBtn.textContent = cancelText;
            cancelBtn.addEventListener('click', () => {
                this.close(null);
            });

            const submitBtn = document.createElement('button');
            submitBtn.type = 'button';
            submitBtn.className = 'btn btn-primary';
            submitBtn.textContent = submitText;
            submitBtn.addEventListener('click', () => {
                // Validate form
                if (form.checkValidity()) {
                    // Collect values
                    const values = {};
                    fields.forEach(field => {
                        values[field.name] = fieldElements[field.name].value;
                    });
                    this.close(values);
                } else {
                    form.reportValidity();
                }
            });

            footer.appendChild(cancelBtn);
            footer.appendChild(submitBtn);

            // Handle form submit (Enter key)
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                submitBtn.click();
            });

            // Assemble modal
            const content = modal.querySelector('.modal-content');
            content.appendChild(header);
            content.appendChild(body);
            content.appendChild(footer);

            // Show modal
            this.show(modal);

            // Focus first input
            const firstInput = form.querySelector('input, textarea');
            if (firstInput) firstInput.focus();

            // ESC to cancel
            this.addEscapeHandler(null);
        });
    }

    /**
     * Create base modal structure
     */
    createModalStructure() {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';

        const modal = document.createElement('div');
        modal.className = 'modal';

        const content = document.createElement('div');
        content.className = 'modal-content';

        modal.appendChild(content);
        overlay.appendChild(modal);

        // Click overlay to close
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.close(this.resolveCallback ? null : false);
            }
        });

        return overlay;
    }

    /**
     * Show modal
     */
    show(modal) {
        document.body.appendChild(modal);
        this.modalContainer = modal;

        // Prevent body scroll
        document.body.style.overflow = 'hidden';

        // Animate in
        requestAnimationFrame(() => {
            modal.classList.add('active');
        });
    }

    /**
     * Close modal with result
     */
    close(result) {
        if (!this.modalContainer) return;

        // Animate out
        this.modalContainer.classList.remove('active');

        setTimeout(() => {
            if (this.modalContainer) {
                this.modalContainer.remove();
                this.modalContainer = null;
            }

            // Restore body scroll
            document.body.style.overflow = '';

            // Resolve promise
            if (this.resolveCallback) {
                this.resolveCallback(result);
                this.resolveCallback = null;
            }
        }, 200); // Match CSS transition duration
    }

    /**
     * Add ESC key handler
     */
    addEscapeHandler(cancelValue) {
        const handler = (e) => {
            if (e.key === 'Escape') {
                this.close(cancelValue);
                document.removeEventListener('keydown', handler);
            }
        };
        document.addEventListener('keydown', handler);
    }
}

// Global modal instance
window.modalDialog = new Modal();
