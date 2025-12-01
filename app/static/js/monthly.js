// Configuration and Constants
const CONFIG = {
    DEBOUNCE_DELAY: 300,
    BATCH_SIZE: 100,
    ANIMATION_FRAME_DELAY: 16
};

// Cache DOM elements
const elements = {};
const state = {
    currentSort: { column: null, ascending: true },
    abortController: null
};

/* ============================
   🚀 PERFORMANCE UTILITIES
============================ */
const debounce = (fn, delay = CONFIG.DEBOUNCE_DELAY) => {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
};

const throttle = (fn, delay = CONFIG.ANIMATION_FRAME_DELAY) => {
    let lastCall = 0;
    return (...args) => {
        const now = Date.now();
        if (now - lastCall >= delay) {
            lastCall = now;
            fn(...args);
        }
    };
};

// Fast DOM creation
const createElement = (html) => {
    const template = document.createElement('template');
    template.innerHTML = html.trim();
    return template.content.firstElementChild;
};

// Cache DOM elements with single query
const cacheElements = () => {
    const ids = [
        'shiftDropdown', 'compDropdown', 'agentSearch', 
        'summaryTable', 'tableContainer', 'noResultsMessage'
    ];
    
    ids.forEach(id => {
        elements[id] = document.getElementById(id);
    });
    
    // Cache table elements
    if (elements.summaryTable) {
        elements.tbody = elements.summaryTable.querySelector('tbody');
        elements.thead = elements.summaryTable.querySelector('thead');
    }
};

/* ============================
   🔍 SEARCHABLE DROPDOWN (OPTIMIZED)
============================ */
function initSearchableDropdown(id) {
    const dropdown = elements[id];
    if (!dropdown) return;

    const input = dropdown.querySelector(".search-input");
    const hidden = dropdown.querySelector("input[type='hidden']");
    const list = dropdown.querySelector(".dropdown-list");
    
    if (!input || !hidden || !list) return;

    // Cache list items
    const listItems = Array.from(list.querySelectorAll("li"));
    let visibleItems = listItems;

    const filterItems = throttle(() => {
        const filter = input.value.toLowerCase();
        visibleItems = [];
        
        listItems.forEach(li => {
            const visible = li.textContent.toLowerCase().includes(filter);
            li.style.display = visible ? "block" : "none";
            if (visible) visibleItems.push(li);
        });

        list.style.display = visibleItems.length > 0 ? "block" : "none";
    });

    input.addEventListener("input", filterItems);

    // Use event delegation for list items
    list.addEventListener("click", (e) => {
        const li = e.target.closest('li');
        if (li) {
            input.value = li.textContent;
            hidden.value = li.dataset.value;
            list.style.display = "none";
        }
    });

    input.addEventListener("focus", () => {
        list.style.display = "block";
        listItems.forEach(li => li.style.display = "block");
        visibleItems = listItems;
    });

    document.addEventListener("click", (e) => {
        if (!dropdown.contains(e.target)) {
            list.style.display = "none";
        }
    });
}

/* ============================
   🔍 TABLE SEARCH (HEAVILY OPTIMIZED)
============================ */
function initTableSearch() {
    if (!elements.agentSearch || !elements.summaryTable || !elements.tbody) return;

    const searchHandler = debounce(function() {
        const searchTerm = this.value.toLowerCase().trim();
        
        // Cancel previous search if any
        if (state.abortController) {
            state.abortController.abort();
        }
        
        performTableSearch(searchTerm);
    });

    elements.agentSearch.addEventListener("input", searchHandler);
}

function performTableSearch(searchTerm) {
    if (!elements.tbody) return;

    const rows = elements.tbody.getElementsByTagName('tr');
    const rowArray = Array.from(rows);
    
    if (searchTerm === '') {
        // Fast path: show all rows
        rowArray.forEach(row => row.style.display = '');
        showNoResultsMessage(false);
        return;
    }

    // Use requestAnimationFrame for smooth UI updates
    state.abortController = new AbortController();
    
    let visibleCount = 0;
    let processed = 0;
    
    const processBatch = throttle(() => {
        const batchSize = CONFIG.BATCH_SIZE;
        const end = Math.min(processed + batchSize, rowArray.length);
        
        for (let i = processed; i < end; i++) {
            if (state.abortController.signal.aborted) return;
            
            const row = rowArray[i];
            const nameCell = row.cells[1];
            const name = nameCell.textContent.toLowerCase();
            
            if (name.includes(searchTerm)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        }
        
        processed = end;
        
        if (processed < rowArray.length && !state.abortController.signal.aborted) {
            requestAnimationFrame(processBatch);
        } else {
            showNoResultsMessage(visibleCount === 0 && searchTerm !== '');
            state.abortController = null;
        }
    });

    requestAnimationFrame(processBatch);
}

/* ============================
   📊 TABLE SORTING (OPTIMIZED)
============================ */
function initTableSorting() {
    if (!elements.summaryTable || !elements.thead) return;

    const headers = elements.thead.querySelectorAll('th');
    const headerArray = Array.from(headers);
    
    headers.forEach((header, index) => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', () => {
            sortTableByColumn(index);
        });
    });
}

function sortTableByColumn(columnIndex) {
    if (!elements.tbody) return;

    const rows = Array.from(elements.tbody.querySelectorAll('tr'));
    if (rows.length === 0) return;

    // Determine sort direction
    const isAscending = state.currentSort.column !== columnIndex ? true : !state.currentSort.ascending;
    state.currentSort = { column: columnIndex, ascending: isAscending };

    // Add visual feedback
    updateSortIndicators(columnIndex, isAscending);

    // Sort rows efficiently
    const sortedRows = sortRows(rows, columnIndex, isAscending);
    
    // Batch DOM updates
    updateTableRows(sortedRows);
}

function sortRows(rows, columnIndex, isAscending) {
    return rows.sort((a, b) => {
        const aText = a.cells[columnIndex]?.textContent?.trim() || '';
        const bText = b.cells[columnIndex]?.textContent?.trim() || '';
        
        // Numeric sorting for potential numeric columns
        const aNum = parseFloat(aText.replace(/[^\d.-]/g, ''));
        const bNum = parseFloat(bText.replace(/[^\d.-]/g, ''));
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAscending ? aNum - bNum : bNum - aNum;
        }
        
        // Text sorting
        return isAscending 
            ? aText.localeCompare(bText, undefined, { numeric: true, sensitivity: 'base' })
            : bText.localeCompare(aText, undefined, { numeric: true, sensitivity: 'base' });
    });
}

function updateTableRows(sortedRows) {
    const fragment = document.createDocumentFragment();
    sortedRows.forEach(row => fragment.appendChild(row));
    
    elements.tbody.innerHTML = '';
    elements.tbody.appendChild(fragment);
}

function updateSortIndicators(columnIndex, isAscending) {
    const headers = elements.thead.querySelectorAll('th');
    headers.forEach((header, index) => {
        header.classList.remove('sort-asc', 'sort-desc');
        if (index === columnIndex) {
            header.classList.add(isAscending ? 'sort-asc' : 'sort-desc');
        }
    });
}

/* ============================
   🧹 NO RESULTS MESSAGE
============================ */
function showNoResultsMessage(show) {
    let messageDiv = elements.noResultsMessage;
    
    if (show) {
        if (!messageDiv) {
            messageDiv = createElement(`
                <div id="noResultsMessage" style="
                    text-align: center;
                    padding: 20px;
                    color: #666;
                    font-style: italic;
                    background: #f8f9fa;
                    border-radius: 8px;
                    margin: 10px 0;
                ">
                    No employees found matching your search.
                </div>
            `);
            elements.noResultsMessage = messageDiv;
            
            if (elements.tableContainer) {
                elements.tableContainer.appendChild(messageDiv);
            }
        }
    } else if (messageDiv) {
        messageDiv.remove();
        elements.noResultsMessage = null;
    }
}

/* ============================
   🎯 CLEAR SEARCH FUNCTIONALITY
============================ */
function initClearSearch() {
    if (!elements.agentSearch) return;

    // Create clear button
    const clearButton = createElement(`
        <button type="button" class="search-clear-btn" style="
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
            color: #999;
            display: none;
            width: 20px;
            height: 20px;
            line-height: 1;
            border-radius: 50%;
            transition: all 0.2s ease;
        ">&times;</button>
    `);

    const searchBox = elements.agentSearch.parentElement;
    if (!searchBox) return;

    searchBox.style.position = 'relative';
    searchBox.appendChild(clearButton);

    // Clear button functionality
    clearButton.addEventListener('click', () => {
        elements.agentSearch.value = '';
        elements.agentSearch.dispatchEvent(new Event('input'));
        elements.agentSearch.focus();
    });

    // Show/hide clear button
    elements.agentSearch.addEventListener('input', function() {
        clearButton.style.display = this.value ? 'block' : 'none';
        
        // Add hover effect
        if (this.value) {
            clearButton.style.background = '#f0f0f0';
            clearButton.addEventListener('mouseenter', () => {
                clearButton.style.background = '#e0e0e0';
                clearButton.style.color = '#666';
            });
            clearButton.addEventListener('mouseleave', () => {
                clearButton.style.background = '#f0f0f0';
                clearButton.style.color = '#999';
            });
        }
    });
}

/* ============================
   📋 DATA EXPORT (OPTIONAL ENHANCEMENT)
============================ */
function initDataExport() {
    const exportBtn = document.getElementById('exportBtn');
    if (!exportBtn || !elements.summaryTable) return;

    exportBtn.addEventListener('click', () => {
        const rows = elements.tbody ? Array.from(elements.tbody.querySelectorAll('tr')) : [];
        const visibleRows = rows.filter(row => row.style.display !== 'none');
        
        if (visibleRows.length === 0) {
            alert('No data to export');
            return;
        }

        exportToCSV(visibleRows);
    });
}

function exportToCSV(rows) {
    const headers = Array.from(elements.thead.querySelectorAll('th'))
        .map(th => `"${th.textContent.trim()}"`)
        .join(',');

    const csvData = rows.map(row => {
        return Array.from(row.cells)
            .map(cell => `"${cell.textContent.trim()}"`)
            .join(',');
    }).join('\n');

    const csv = `${headers}\n${csvData}`;
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `monthly-report-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/* ============================
   🚀 INITIALIZATION
============================ */
function initializeMonthlyJS() {
    // Cache all elements first
    cacheElements();
    
    // Initialize components
    initSearchableDropdown("shiftDropdown");
    initTableSearch();
    initFileManagement();
    initTableSorting();
    initClearSearch();
    initDataExport();
    
    // Clear initial search
    if (elements.agentSearch) {
        elements.agentSearch.value = '';
    }
    showNoResultsMessage(false);
    
    // Add keyboard shortcut
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'f' && elements.agentSearch) {
            e.preventDefault();
            elements.agentSearch.focus();
        }
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeMonthlyJS);
} else {
    initializeMonthlyJS();
}

// Add CSS for sort indicators
const addSortStyles = () => {
    if (!document.getElementById('monthly-sort-styles')) {
        const styles = createElement(`
            <style id="monthly-sort-styles">
                .sort-asc::after { content: " ▲"; font-size: 12px; }
                .sort-desc::after { content: " ▼"; font-size: 12px; }
                th { position: relative; }
                th:hover { background-color: #f8f9fa; }
            </style>
        `);
        document.head.appendChild(styles);
    }
};
/* ============================
   📁 FILE MANAGEMENT FUNCTIONS
============================ */
function initFileManagement() {
    console.log('Initializing file management...');
    
    const fileDropdown = document.getElementById('fileDropdown');
    const deleteFileBtn = document.getElementById('deleteFileBtn');
    const batchIdInput = document.getElementById('batchIdInput');

    if (!fileDropdown) {
        console.error('File dropdown element not found');
        return;
    }

    // Load files immediately on page load
    loadUploadedFiles();
    
    // Enable/disable delete button based on selection
    fileDropdown.addEventListener('change', function() {
        const hasSelection = this.value !== '';
        if (deleteFileBtn) {
            deleteFileBtn.disabled = !hasSelection;
        }
        if (batchIdInput) {
            batchIdInput.value = this.value;
        }
        console.log('Selected batch:', this.value);
    });

    // Reload files when dropdown is focused
    fileDropdown.addEventListener('focus', function() {
        if (this.options.length <= 1 || (this.options.length === 2 && this.options[1].disabled)) {
            loadUploadedFiles();
        }
    });
}

async function loadUploadedFiles() {
    const fileDropdown = document.getElementById('fileDropdown');
    const dropdownSpinner = document.getElementById('dropdownSpinner');
    
    if (!fileDropdown) {
        console.error('File dropdown not found');
        return;
    }

    try {
        console.log('Loading uploaded files from API...');
        
        // Show loading state
        if (dropdownSpinner) {
            dropdownSpinner.style.display = 'inline-block';
        }
        
        fileDropdown.innerHTML = '<option value="">-- Loading files... --</option>';
        fileDropdown.disabled = true;

        // IMPORTANT: Add credentials include for session cookies
        const response = await fetch('/api/uploaded_files', {
            method: 'GET',
            credentials: 'include'  // Session cookies include karne ke liye
        });
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Non-JSON response:', text.substring(0, 200));
            throw new Error('Server returned HTML instead of JSON. Check authentication.');
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }

        console.log('Files API response:', data);
        populateFileDropdown(data.files || []);

    } catch (error) {
        console.error('Error loading files:', error);
        
        // Show appropriate error message
        let errorMessage = 'Failed to load file list';
        if (error.message.includes('HTML')) {
            errorMessage = 'Authentication required. Please refresh the page.';
        } else if (error.message.includes('Network')) {
            errorMessage = 'Network error. Please check your connection.';
        } else {
            errorMessage = error.message;
        }
        
        showNotification(errorMessage, 'error');
        populateFileDropdown([]); // Show empty state
    } finally {
        if (dropdownSpinner) {
            dropdownSpinner.style.display = 'none';
        }
        fileDropdown.disabled = false;
    }
}

function populateFileDropdown(files) {
    const fileDropdown = document.getElementById('fileDropdown');
    
    if (!fileDropdown) return;

    console.log('Populating dropdown with:', files);

    // Clear all options
    fileDropdown.innerHTML = '';

    if (!files || files.length === 0) {
        // Add empty state option
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = '-- No files uploaded yet --';
        emptyOption.disabled = true;
        fileDropdown.appendChild(emptyOption);
        
        updateDeleteButtonState(false);
        return;
    }

    // Add default option
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '-- Select a file to delete --';
    fileDropdown.appendChild(defaultOption);

    // Add file options
    files.forEach(file => {
        const option = document.createElement('option');
        option.value = file.batch_id;
        
        // Create display text
        const displayText = `${file.filename} (${file.upload_date}) - ${file.record_count} records`;
        option.textContent = displayText.length > 80 ? displayText.substring(0, 77) + '...' : displayText;
        
        option.title = `Filename: ${file.filename}\nUploaded: ${file.upload_date}\nRecords: ${file.record_count}`;
        fileDropdown.appendChild(option);
    });

    updateDeleteButtonState(false);
}

function updateDeleteButtonState(enabled) {
    const deleteFileBtn = document.getElementById('deleteFileBtn');
    const deleteBtnText = document.getElementById('deleteBtnText');
    
    if (deleteFileBtn) {
        deleteFileBtn.disabled = !enabled;
    }
    if (deleteBtnText) {
        deleteBtnText.textContent = enabled ? 'Delete Selected File' : 'Select File First';
    }
}

// Enhanced notification function for file management
function showNotification(message, type = 'success') {
    // Remove existing notifications
    const existingNotif = document.querySelector('.custom-notification');
    if (existingNotif) existingNotif.remove();

    const notif = document.createElement('div');
    notif.className = `custom-notification ${type}`;
    notif.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check' : 'exclamation'}-circle"></i>
        <span>${message}</span>
    `;

    document.body.appendChild(notif);

    // Animate in
    setTimeout(() => notif.classList.add('show'), 100);

    // Remove after delay
    setTimeout(() => {
        notif.classList.remove('show');
        setTimeout(() => notif.remove(), 300);
    }, 5000);
}

function confirmDeleteFile() {
    const dropdown = document.getElementById('fileDropdown');
    const selectedOption = dropdown.options[dropdown.selectedIndex];
    
    if (!selectedOption || selectedOption.value === '') {
        showNotification('Please select a file first', 'error');
        return false;
    }
    
    const filename = selectedOption.textContent.split(' (')[0];
    
    return confirm(`⚠️ DELETE CONFIRMATION\n\nFile: "${filename}"\n\nThis will:\n• Remove this file's data from database\n• Remove this file from UI\n• Keep all other files safe\n\nContinue?`);
}

addSortStyles();