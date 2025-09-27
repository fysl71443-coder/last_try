/**
 * Modal System - Replace browser alerts/confirms/prompts with styled modals
 */
(function() {
  'use strict';

  // Create modal container if it doesn't exist
  function ensureModalContainer() {
    let container = document.getElementById('modal-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'modal-container';
      document.body.appendChild(container);
    }
    return container;
  }

  // Generate unique modal ID
  function generateModalId() {
    return 'modal-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
  }

  // Create modal HTML
  function createModal(id, title, body, buttons, size = '') {
    const sizeClass = size ? `modal-${size}` : '';
    return `
      <div class="modal fade" id="${id}" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog ${sizeClass}">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">${title}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              ${body}
            </div>
            <div class="modal-footer">
              ${buttons}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Show modal and return promise
  function showModal(modalHtml) {
    const container = ensureModalContainer();
    container.insertAdjacentHTML('beforeend', modalHtml);
    
    const modalElement = container.lastElementChild;
    const modal = new bootstrap.Modal(modalElement);
    
    return new Promise((resolve) => {
      modalElement.addEventListener('hidden.bs.modal', () => {
        modalElement.remove();
      });
      
      // Handle button clicks
      modalElement.addEventListener('click', (e) => {
        if (e.target.hasAttribute('data-result')) {
          const result = e.target.getAttribute('data-result');
          modal.hide();
          resolve(result);
        }
      });
      
      modal.show();
      // If requested to keep confirmation behind a print window, re-focus the print window after showing
      setTimeout(function(){
        try{
          if (window.KEEP_CONFIRM_BEHIND && window.__PRINT_WINDOW && !window.__PRINT_WINDOW.closed) {
            window.__PRINT_WINDOW.focus();
          }
        }catch(_e){}
      }, 50);
      setTimeout(function(){
        try{
          if (window.KEEP_CONFIRM_BEHIND && window.__PRINT_WINDOW && !window.__PRINT_WINDOW.closed) {
            window.__PRINT_WINDOW.focus();
          }
        }catch(_e){}
      }, 250);
    });
  }

  // Custom Alert
  window.showAlert = function(message, title = 'تنبيه / Alert') {
    const id = generateModalId();
    const buttons = `
      <button type="button" class="btn btn-primary" data-result="ok" data-bs-dismiss="modal">
        موافق / OK
      </button>
    `;
    const modalHtml = createModal(id, title, `<p>${message}</p>`, buttons);
    return showModal(modalHtml);
  };

  // Custom Confirm
  window.showConfirm = function(message, title = 'تأكيد / Confirm') {
    const id = generateModalId();
    const buttons = `
      <button type="button" class="btn btn-secondary" data-result="false" data-bs-dismiss="modal">
        إلغاء / Cancel
      </button>
      <button type="button" class="btn btn-primary" data-result="true" data-bs-dismiss="modal">
        موافق / OK
      </button>
    `;
    const modalHtml = createModal(id, title, `<p>${message}</p>`, buttons);
    return showModal(modalHtml).then(result => result === 'true');
  };

  // Custom Confirm with custom buttons (non-blocking friendly)
  window.showConfirmChoice = function(message, okText = 'OK', cancelText = 'Cancel', title = 'تأكيد / Confirm') {
    const id = generateModalId();
    const buttons = `
      <button type="button" class="btn btn-secondary" data-result="false" data-bs-dismiss="modal">${cancelText}</button>
      <button type="button" class="btn btn-primary" data-result="true" data-bs-dismiss="modal">${okText}</button>
    `;
    const modalHtml = createModal(id, title, `<p>${message}</p>`, buttons);
    return showModal(modalHtml).then(result => result === 'true');
  };

  // Custom Prompt
  window.showPrompt = function(message, defaultValue = '', title = 'إدخال / Input') {
    const id = generateModalId();
    const inputId = `input-${id}`;
    const body = `
      <p>${message}</p>
      <input type="text" class="form-control" id="${inputId}" value="${defaultValue}" placeholder="أدخل القيمة / Enter value">
    `;
    
    return showPromptModal(body, title, inputId);
  };

  // Password Prompt (shows dots)
  window.showPasswordPrompt = function(message, title = 'كلمة السر / Password') {
    const id = generateModalId();
    const inputId = `input-${id}`;
    const body = `
      <p>${message}</p>
      <input type="password" class="form-control" id="${inputId}" placeholder="أدخل كلمة السر / Enter password">
    `;
    
    return showPromptModal(body, title, inputId);
  };

  // Common prompt modal logic
  function showPromptModal(body, title, inputId) {
    const id = generateModalId();
    const buttons = `
      <button type="button" class="btn btn-secondary" data-result="null" data-bs-dismiss="modal">
        إلغاء / Cancel
      </button>
      <button type="button" class="btn btn-primary" data-result="submit" data-bs-dismiss="modal">
        موافق / OK
      </button>
    `;
    const modalHtml = createModal(id, title, body, buttons);
    
    const container = ensureModalContainer();
    container.insertAdjacentHTML('beforeend', modalHtml);
    
    const modalElement = container.lastElementChild;
    const modal = new bootstrap.Modal(modalElement);
    const input = modalElement.querySelector(`#${inputId}`);
    
    return new Promise((resolve) => {
      modalElement.addEventListener('hidden.bs.modal', () => {
        modalElement.remove();
      });
      
      modalElement.addEventListener('shown.bs.modal', () => {
        input.focus();
        input.select();
      });
      
      // Handle Enter key
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          modal.hide();
          resolve(input.value);
        }
      });
      
      modalElement.addEventListener('click', (e) => {
        if (e.target.hasAttribute('data-result')) {
          const result = e.target.getAttribute('data-result');
          modal.hide();
          if (result === 'submit') {
            resolve(input.value);
          } else {
            resolve(null);
          }
        }
      });
      
      modal.show();
    });
  }

  // Custom form modal
  window.showFormModal = function(title, fields, submitText = 'حفظ / Save') {
    const id = generateModalId();
    
    let formFields = '';
    fields.forEach(field => {
      const fieldId = `field-${field.name}-${id}`;
      formFields += `
        <div class="mb-3">
          <label for="${fieldId}" class="form-label">${field.label}</label>
          <input type="${field.type || 'text'}" 
                 class="form-control" 
                 id="${fieldId}" 
                 name="${field.name}"
                 value="${field.value || ''}" 
                 placeholder="${field.placeholder || ''}"
                 ${field.required ? 'required' : ''}>
        </div>
      `;
    });
    
    const body = `<form id="form-${id}">${formFields}</form>`;
    const buttons = `
      <button type="button" class="btn btn-secondary" data-result="cancel" data-bs-dismiss="modal">
        إلغاء / Cancel
      </button>
      <button type="button" class="btn btn-primary" data-result="submit">
        ${submitText}
      </button>
    `;
    
    const modalHtml = createModal(id, title, body, buttons, 'lg');
    
    const container = ensureModalContainer();
    container.insertAdjacentHTML('beforeend', modalHtml);
    
    const modalElement = container.lastElementChild;
    const modal = new bootstrap.Modal(modalElement);
    const form = modalElement.querySelector(`#form-${id}`);
    
    return new Promise((resolve) => {
      modalElement.addEventListener('hidden.bs.modal', () => {
        modalElement.remove();
      });
      
      modalElement.addEventListener('click', (e) => {
        if (e.target.hasAttribute('data-result')) {
          const result = e.target.getAttribute('data-result');
          
          if (result === 'submit') {
            const formData = new FormData(form);
            const data = {};
            for (let [key, value] of formData.entries()) {
              data[key] = value;
            }
            modal.hide();
            resolve(data);
          } else {
            modal.hide();
            resolve(null);
          }
        }
      });
      
      modal.show();
    });
  };

  // Override native functions (optional)
  window.customAlert = window.alert;
  window.customConfirm = window.confirm;
  window.customPrompt = window.prompt;
  
  // PDF/Print viewer modal
  window.showPrintModal = function(url, title = 'طباعة / Print') {
    const id = generateModalId();
    const body = `
      <div class="text-center mb-3">
        <iframe src="${url}" style="width: 100%; height: 500px; border: none;" title="Print Preview"></iframe>
      </div>
      <div class="text-center">
        <a href="${url}" target="_blank" class="btn btn-outline-primary me-2">
          🔗 فتح في نافذة جديدة / Open in New Window
        </a>
        <button type="button" class="btn btn-primary" onclick="window.print()">
          🖨️ طباعة / Print
        </button>
      </div>
    `;
    const buttons = `
      <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
        إغلاق / Close
      </button>
    `;
    const modalHtml = createModal(id, title, body, buttons, 'xl');

    const container = ensureModalContainer();
    container.insertAdjacentHTML('beforeend', modalHtml);

    const modalElement = container.lastElementChild;
    const modal = new bootstrap.Modal(modalElement);

    modalElement.addEventListener('hidden.bs.modal', () => {
      modalElement.remove();
    });

    modal.show();
  };

  // Override window.open for print URLs (allow bypass via DISABLE_PRINT_MODAL flag)
  const originalWindowOpen = window.open;
  window.open = function(url, target, features) {
    const isPrintUrl = url && (url.includes('/print') || url.includes('.pdf') || url.includes('receipt'));
    const disablePrintModal = !!window.DISABLE_PRINT_MODAL;
    if (isPrintUrl && !disablePrintModal) {
      showPrintModal(url);
      return null;
    }
    return originalWindowOpen.call(this, url, target, features);
  };

  // Expose helper to toggle print modal behavior if needed
  window.enablePrintModal = function(enable){ window.DISABLE_PRINT_MODAL = !enable; };

  // Uncomment to replace native functions globally
  // window.alert = window.showAlert;
  // window.confirm = window.showConfirm;
  // window.prompt = window.showPrompt;

})();
