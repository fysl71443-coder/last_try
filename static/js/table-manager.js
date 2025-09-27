(function(){
  function qs(sel, root){ return (root||document).querySelector(sel); }
  function qsa(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }

  let layout = { sections: [] };
  let sectionCounter = 0;
  let rowCounter = 0;

  function generateId(prefix) {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  function createSectionElement(section) {
    const sectionDiv = document.createElement('div');
    sectionDiv.className = 'card mb-3';
    sectionDiv.setAttribute('data-section-id', section.id);
    
    sectionDiv.innerHTML = `
      <div class="card-header d-flex justify-content-between align-items-center">
        <div class="d-flex align-items-center">
          <input class="form-control form-control-sm me-2" value="${section.name}" style="width: 200px;" data-section-name>
          <button class="btn btn-sm btn-outline-primary" data-add-row>Add Row</button>
        </div>
        <button class="btn btn-sm btn-outline-danger" data-remove-section>Remove</button>
      </div>
      <div class="card-body" data-rows></div>
    `;
    
    return sectionDiv;
  }

  function createRowElement(row) {
    const rowDiv = document.createElement('div');
    rowDiv.className = 'row mb-2';
    rowDiv.setAttribute('data-row-id', row.id);
    
    rowDiv.innerHTML = `
      <div class="col-12">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <span class="text-muted">Row ${row.id}</span>
          <button class="btn btn-sm btn-outline-danger" data-remove-row>Remove Row</button>
        </div>
        <div class="row g-2" data-tables></div>
        <div class="mt-2">
          <button class="btn btn-sm btn-outline-success" data-add-table>Add Table</button>
        </div>
      </div>
    `;
    
    return rowDiv;
  }

  function createTableElement(table) {
    const tableDiv = document.createElement('div');
    tableDiv.className = 'col-auto';
    tableDiv.setAttribute('data-table-id', table.id);
    tableDiv.setAttribute('draggable', 'true');
    
    tableDiv.innerHTML = `
      <div class="card" style="width: 80px; height: 60px;">
        <div class="card-body d-flex align-items-center justify-content-center p-1">
          <input class="form-control form-control-sm text-center" value="${table.number}" 
                 style="width: 50px; height: 30px; font-size: 12px;" data-table-number>
        </div>
        <div class="card-footer p-1 text-center">
          <button class="btn btn-sm btn-outline-danger" style="font-size: 10px; padding: 2px 4px;" data-remove-table>×</button>
        </div>
      </div>
    `;
    
    return tableDiv;
  }

  function renderLayout() {
    const sectionsContainer = qs('#sections');
    if (!sectionsContainer) return;
    
    sectionsContainer.innerHTML = '';
    
    layout.sections.forEach(section => {
      const sectionEl = createSectionElement(section);
      const rowsContainer = sectionEl.querySelector('[data-rows]');
      
      section.rows.forEach(row => {
        const rowEl = createRowElement(row);
        const tablesContainer = rowEl.querySelector('[data-tables]');
        
        row.tables.forEach(table => {
          const tableEl = createTableElement(table);
          tablesContainer.appendChild(tableEl);
        });
        
        rowsContainer.appendChild(rowEl);
      });
      
      sectionsContainer.appendChild(sectionEl);
    });
    
    attachEventListeners();
  }

  function attachEventListeners() {
    // Add section
    qs('#addSectionBtn')?.addEventListener('click', () => {
      const name = qs('#newSectionName')?.value?.trim();
      if (!name) return;
      
      const section = {
        id: generateId('section'),
        name,
        rows: []
      };
      
      layout.sections.push(section);
      qs('#newSectionName').value = '';
      renderLayout();
    });

    // Remove section
    qsa('[data-remove-section]').forEach(btn => {
      btn.addEventListener('click', () => {
        const sectionEl = btn.closest('[data-section-id]');
        const sectionId = sectionEl.getAttribute('data-section-id');
        layout.sections = layout.sections.filter(s => s.id !== sectionId);
        renderLayout();
      });
    });

    // Add row
    qsa('[data-add-row]').forEach(btn => {
      btn.addEventListener('click', () => {
        const sectionEl = btn.closest('[data-section-id]');
        const sectionId = sectionEl.getAttribute('data-section-id');
        const section = layout.sections.find(s => s.id === sectionId);
        
        const row = {
          id: generateId('row'),
          tables: []
        };
        
        section.rows.push(row);
        renderLayout();
      });
    });

    // Remove row
    qsa('[data-remove-row]').forEach(btn => {
      btn.addEventListener('click', () => {
        const rowEl = btn.closest('[data-row-id]');
        const rowId = rowEl.getAttribute('data-row-id');
        const sectionEl = rowEl.closest('[data-section-id]');
        const sectionId = sectionEl.getAttribute('data-section-id');
        const section = layout.sections.find(s => s.id === sectionId);
        
        section.rows = section.rows.filter(r => r.id !== rowId);
        renderLayout();
      });
    });

    // Add table
    qsa('[data-add-table]').forEach(btn => {
      btn.addEventListener('click', () => {
        const rowEl = btn.closest('[data-row-id]');
        const rowId = rowEl.getAttribute('data-row-id');
        const sectionEl = rowEl.closest('[data-section-id]');
        const sectionId = sectionEl.getAttribute('data-section-id');
        const section = layout.sections.find(s => s.id === sectionId);
        const row = section.rows.find(r => r.id === rowId);
        
        const table = {
          id: generateId('table'),
          number: '',
          seats: null
        };
        
        row.tables.push(table);
        renderLayout();
      });
    });

    // Remove table
    qsa('[data-remove-table]').forEach(btn => {
      btn.addEventListener('click', () => {
        const tableEl = btn.closest('[data-table-id]');
        const tableId = tableEl.getAttribute('data-table-id');
        const rowEl = tableEl.closest('[data-row-id]');
        const rowId = rowEl.getAttribute('data-row-id');
        const sectionEl = rowEl.closest('[data-section-id]');
        const sectionId = sectionEl.getAttribute('data-section-id');
        const section = layout.sections.find(s => s.id === sectionId);
        const row = section.rows.find(r => r.id === rowId);
        
        row.tables = row.tables.filter(t => t.id !== tableId);
        renderLayout();
      });
    });

    // Update section name
    qsa('[data-section-name]').forEach(input => {
      input.addEventListener('blur', () => {
        const sectionEl = input.closest('[data-section-id]');
        const sectionId = sectionEl.getAttribute('data-section-id');
        const section = layout.sections.find(s => s.id === sectionId);
        section.name = input.value;
      });
    });

    // Update table number
    qsa('[data-table-number]').forEach(input => {
      input.addEventListener('blur', () => {
        const tableEl = input.closest('[data-table-id]');
        const tableId = tableEl.getAttribute('data-table-id');
        const rowEl = tableEl.closest('[data-row-id]');
        const rowId = rowEl.getAttribute('data-row-id');
        const sectionEl = rowEl.closest('[data-section-id]');
        const sectionId = sectionEl.getAttribute('data-section-id');
        const section = layout.sections.find(s => s.id === sectionId);
        const row = section.rows.find(r => r.id === rowId);
        const table = row.tables.find(t => t.id === tableId);
        
        table.number = input.value;
      });
    });

    // Drag and drop
    qsa('[data-table-id]').forEach(tableEl => {
      tableEl.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', tableEl.getAttribute('data-table-id'));
      });
    });

    qsa('[data-tables]').forEach(container => {
      container.addEventListener('dragover', (e) => {
        e.preventDefault();
      });
      
      container.addEventListener('drop', (e) => {
        e.preventDefault();
        const tableId = e.dataTransfer.getData('text/plain');
        const tableEl = qs(`[data-table-id="${tableId}"]`);
        if (tableEl) {
          container.appendChild(tableEl);
          
          // Update layout data
          const newRowEl = tableEl.closest('[data-row-id]');
          const newRowId = newRowEl.getAttribute('data-row-id');
          const newSectionEl = newRowEl.closest('[data-section-id]');
          const newSectionId = newSectionEl.getAttribute('data-section-id');
          
          // Find and move table in layout
          let tableData = null;
          let oldSection = null;
          let oldRow = null;
          
          layout.sections.forEach(section => {
            section.rows.forEach(row => {
              const tableIndex = row.tables.findIndex(t => t.id === tableId);
              if (tableIndex !== -1) {
                tableData = row.tables[tableIndex];
                oldSection = section;
                oldRow = row;
                row.tables.splice(tableIndex, 1);
              }
            });
          });
          
          if (tableData && oldSection && oldRow) {
            const newSection = layout.sections.find(s => s.id === newSectionId);
            const newRow = newSection.rows.find(r => r.id === newRowId);
            newRow.tables.push(tableData);
          }
        }
      });
    });
  }

  async function loadLayout() {
    try {
      const root = qs('#manager-root');
      if (!root) return;
      
      const branch = root.getAttribute('data-branch');
      if (!branch) return;
      
      const response = await fetch(`/api/table-layout/${branch}`, {
        credentials: 'same-origin'
      });
      
      if (response.ok) {
        const data = await response.json();
        layout = data || { sections: [] };
        renderLayout();
      } else {
        console.error('Failed to load layout:', response.status, response.statusText);
        if (response.status === 401 || response.status === 403) {
          console.warn('Authentication required for table layout');
        }
        // Still render with empty layout to allow user to work
        layout = { sections: [] };
        renderLayout();
      }
    } catch (e) {
      console.error('Failed to load layout:', e);
      // Still render with empty layout to allow user to work
      layout = { sections: [] };
      renderLayout();
    }
  }

  async function saveLayout() {
    try {
      const root = qs('#manager-root');
      if (!root) {
        console.error('Manager root element not found');
        return;
      }
      const branch = root.getAttribute('data-branch');
      if (!branch) {
        console.error('Branch attribute not found');
        return;
      }
      
      console.log('Saving layout for branch:', branch);

      const payload = {
        sections: (layout.sections || []).map(section => ({
          id: section.id,
          name: section.name || '',
          rows: (section.rows || []).map(row => ({
            id: row.id,
            tables: (row.tables || []).map(table => ({
              id: table.id,
              number: table.number || '',
              seats: table.seats || null
            }))
          }))
        }))
      };

      // Get CSRF token if available
      const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
      console.log('CSRF token found:', !!csrfToken);
      
      const response = await fetch(`/api/table-layout/${branch}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken && { 'X-CSRFToken': csrfToken })
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload)
      });
      
      console.log('Response status:', response.status, response.statusText);
      
      if (response.ok) {
        alert('Layout saved successfully!');
      } else {
        // Provide more specific error information
        if (response.status === 401 || response.status === 403) {
          alert('Authentication required. Please log in again.');
        } else if (response.status >= 400 && response.status < 500) {
          alert(`Failed to save layout: Client error (${response.status})`);
        } else if (response.status >= 500) {
          alert(`Failed to save layout: Server error (${response.status})`);
        } else {
          alert(`Failed to save layout: ${response.status} ${response.statusText}`);
        }
      }
    } catch (e) {
      console.error('Failed to save layout:', e);
      alert('Failed to save layout: Network error or server unavailable');
    }
  }

  // Initialize
  window.addEventListener('DOMContentLoaded', () => {
    loadLayout();
    
    qs('#saveLayoutBtn')?.addEventListener('click', saveLayout);
  });
})();
