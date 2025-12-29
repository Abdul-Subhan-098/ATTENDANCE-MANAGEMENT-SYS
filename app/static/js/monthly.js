/* ============================
   monthly.js - Optimized Version
   All JavaScript functionality for monthly.html
============================ */

// Configuration and Constants
const CONFIG = {
    DEBOUNCE_DELAY: 300,
    BATCH_SIZE: 100,
    ANIMATION_FRAME_DELAY: 16
};

// Global state management
const APP_STATE = {
    currentSort: { column: null, ascending: true },
    abortController: null,
    activeFilters: {
        employee: '',
        department: '',
        role: '',
        month: ''
    },
    tableRows: [],
    fileDropdown: null
};

// Cache DOM elements
const DOM = {};

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

/* ============================
   🎯 DOM CACHING & INITIALIZATION
============================ */
function cacheElements() {
    const elements = [
        'sidebar', 'mainContent', 'sidebarToggle',
        'employeeFilter', 'departmentFilter', 'roleFilter', 'monthFilter',
        'filterTags', 'filterCount', 'applyFilters', 'resetFilters',
        'agentSearch', 'summaryTable', 'tableContainer', 'noResultsMessage',
        'fileDropdown', 'deleteFileBtn', 'batchIdInput', 'dropdownSpinner',
        'excelFile', 'fileText', 'filterIndicator', 'tableBody',
        'shiftDropdown', 'compDropdown'
    ];

    elements.forEach(id => {
        DOM[id] = document.getElementById(id);
    });

    // Cache table elements
    if (DOM.summaryTable) {
        DOM.tbody = DOM.summaryTable.querySelector('tbody');
        DOM.thead = DOM.summaryTable.querySelector('thead');
    }

    // Cache all table rows
    if (DOM.tableBody) {
        APP_STATE.tableRows = Array.from(DOM.tableBody.querySelectorAll('.data-row'));
    }
}

function initializeSelect2() {
    if (window.$ && $.fn.select2) {
        $('#employeeFilter, #departmentFilter, #roleFilter, #monthFilter').select2({
            placeholder: "Select...",
            allowClear: true,
            width: '100%'
        });
    }
}

function initializeSidebar() {
    if (!DOM.sidebarToggle) return;

    DOM.sidebarToggle.addEventListener('click', function() {
        DOM.sidebar.classList.toggle('collapsed');
        DOM.mainContent.classList.toggle('expanded');
        
        const icon = DOM.sidebarToggle.querySelector('i');
        if (DOM.sidebar.classList.contains('collapsed')) {
            icon.classList.remove('fa-bars');
            icon.classList.add('fa-arrow-right');
        } else {
            icon.classList.remove('fa-arrow-right');
            icon.classList.add('fa-bars');
        }
    });
}

/* ============================
   🔍 FILTER FUNCTIONALITY
============================ */
function initializeFilters() {
    if (!DOM.applyFilters || !DOM.resetFilters) return;

    DOM.applyFilters.addEventListener('click', applyTableFilters);
    DOM.resetFilters.addEventListener('click', resetAllFilters);
    
    // Auto-apply filters when Select2 changes (optional)
    $('#employeeFilter, #departmentFilter, #roleFilter, #monthFilter').on('change', function() {
        // Uncomment for auto-apply on change:
        // applyTableFilters();
    });

    // Initialize with no filters
    applyTableFilters();
}

function applyTableFilters() {
    // Update active filters
    APP_STATE.activeFilters = {
        employee: DOM.employeeFilter?.value || '',
        department: DOM.departmentFilter?.value || '',
        role: DOM.roleFilter?.value || '',
        month: DOM.monthFilter?.value || ''
    };

    if (!APP_STATE.tableRows || APP_STATE.tableRows.length === 0) return;

    let visibleCount = 0;
    const searchTerm = DOM.agentSearch?.value.toLowerCase() || '';

    APP_STATE.tableRows.forEach(row => {
        let showRow = true;

        // Apply dropdown filters
        if (APP_STATE.activeFilters.employee && row.dataset.name !== APP_STATE.activeFilters.employee) {
            showRow = false;
        }
        
        if (APP_STATE.activeFilters.department && row.dataset.department !== APP_STATE.activeFilters.department) {
            showRow = false;
        }
        
        if (APP_STATE.activeFilters.role && row.dataset.role !== APP_STATE.activeFilters.role) {
            showRow = false;
        }
        
        if (APP_STATE.activeFilters.month) {
            const dateStr = row.dataset.month;
            if (dateStr) {
                const date = new Date(dateStr);
                const month = date.getMonth() + 1;
                if (month.toString() !== APP_STATE.activeFilters.month) {
                    showRow = false;
                }
            } else if (APP_STATE.activeFilters.month) {
                showRow = false;
            }
        }

        // Apply search filter
        if (searchTerm) {
            const name = row.querySelector('td:nth-child(2)')?.textContent.toLowerCase() || '';
            if (!name.includes(searchTerm)) {
                showRow = false;
            }
        }

        // Show/hide row
        row.style.display = showRow ? '' : 'none';
        if (showRow) visibleCount++;
    });

    // Update UI
    updateFilterCount(visibleCount);
    updateFilterTags();
}

function resetAllFilters() {
    // Reset dropdowns
    $('#employeeFilter, #departmentFilter, #roleFilter, #monthFilter').val('').trigger('change');
    
    // Reset search
    if (DOM.agentSearch) DOM.agentSearch.value = '';
    
    // Reset active filters
    APP_STATE.activeFilters = {
        employee: '',
        department: '',
        role: '',
        month: ''
    };

    applyTableFilters();
}

function updateFilterCount(visibleCount) {
    if (!DOM.filterCount) return;
    const totalRows = APP_STATE.tableRows.length;
    DOM.filterCount.textContent = `Showing ${visibleCount} of ${totalRows} employees`;
}

function updateFilterTags() {
    if (!DOM.filterTags) return;
    
    DOM.filterTags.innerHTML = '';
    
    for (const [key, value] of Object.entries(APP_STATE.activeFilters)) {
        if (value) {
            let label = '';
            let displayValue = value;
            
            switch(key) {
                case 'employee': label = 'Employee'; break;
                case 'department': label = 'Department'; break;
                case 'role': label = 'Role'; break;
                case 'month': 
                    label = 'Month';
                    displayValue = getMonthName(value);
                    break;
            }
            
            const tag = createElement(`
                <div class="filter-tag">
                    ${label}: ${displayValue} 
                    <i class="fas fa-times" data-filter="${key}"></i>
                </div>
            `);
            
            DOM.filterTags.appendChild(tag);
            
            // Add click event to remove filter
            tag.querySelector('.fa-times').addEventListener('click', function() {
                removeFilter(key);
            });
        }
    }
}

function removeFilter(filterKey) {
    APP_STATE.activeFilters[filterKey] = '';
    
    // Reset the corresponding dropdown
    if (filterKey === 'month') {
        $('#monthFilter').val('').trigger('change');
    } else {
        $(`#${filterKey}Filter`).val('').trigger('change');
    }
    
    applyTableFilters();
}

function getMonthName(monthNumber) {
    const months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return months[parseInt(monthNumber) - 1] || monthNumber;
}

/* ============================
   🔍 TABLE SEARCH
============================ */
function initializeTableSearch() {
    if (!DOM.agentSearch) return;

    const searchHandler = debounce(function() {
        if (APP_STATE.abortController) {
            APP_STATE.abortController.abort();
        }
        
        applyTableFilters(); // Re-apply all filters including search
    });

    DOM.agentSearch.addEventListener("input", searchHandler);
    
    // Add clear search functionality
    initClearSearch();
}

function initClearSearch() {
    if (!DOM.agentSearch) return;

    const searchBox = DOM.agentSearch.parentElement;
    if (!searchBox) return;

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

    searchBox.style.position = 'relative';
    searchBox.appendChild(clearButton);

    // Clear button functionality
    clearButton.addEventListener('click', () => {
        DOM.agentSearch.value = '';
        DOM.agentSearch.dispatchEvent(new Event('input'));
        DOM.agentSearch.focus();
    });

    // Show/hide clear button
    DOM.agentSearch.addEventListener('input', function() {
        clearButton.style.display = this.value ? 'block' : 'none';
        
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
   📊 TABLE SORTING
============================ */
function initializeTableSorting() {
    if (!DOM.summaryTable || !DOM.thead) return;

    const headers = DOM.thead.querySelectorAll('th');
    
    headers.forEach((header, index) => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', () => {
            sortTableByColumn(index);
        });
    });
    
    addSortStyles();
}

function sortTableByColumn(columnIndex) {
    if (!DOM.tbody || !APP_STATE.tableRows) return;

    // Determine sort direction
    const isAscending = APP_STATE.currentSort.column !== columnIndex ? true : !APP_STATE.currentSort.ascending;
    APP_STATE.currentSort = { column: columnIndex, ascending: isAscending };

    // Add visual feedback
    updateSortIndicators(columnIndex, isAscending);

    // Sort rows
    const sortedRows = sortRows(APP_STATE.tableRows, columnIndex, isAscending);
    
    // Update DOM
    updateTableRows(sortedRows);
}

function sortRows(rows, columnIndex, isAscending) {
    return [...rows].sort((a, b) => {
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
    
    DOM.tbody.innerHTML = '';
    DOM.tbody.appendChild(fragment);
    
    // Update cached rows
    APP_STATE.tableRows = sortedRows;
}

function updateSortIndicators(columnIndex, isAscending) {
    const headers = DOM.thead.querySelectorAll('th');
    headers.forEach((header, index) => {
        header.classList.remove('sort-asc', 'sort-desc');
        if (index === columnIndex) {
            header.classList.add(isAscending ? 'sort-asc' : 'sort-desc');
        }
    });
}

function addSortStyles() {
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
}

/* ============================
   📁 FILE MANAGEMENT
============================ */
function initializeFileManagement() {
    if (!DOM.fileDropdown) return;

    // Load files on page load
    loadUploadedFiles();
    
    // Enable/disable delete button based on selection
    DOM.fileDropdown.addEventListener('change', function() {
        const hasSelection = this.value !== '';
        if (DOM.deleteFileBtn) {
            DOM.deleteFileBtn.disabled = !hasSelection;
        }
        if (DOM.batchIdInput) {
            DOM.batchIdInput.value = this.value;
        }
    });

    // Reload files when dropdown is focused
    DOM.fileDropdown.addEventListener('focus', function() {
        if (this.options.length <= 1 || (this.options.length === 2 && this.options[1].disabled)) {
            loadUploadedFiles();
        }
    });

    // Initialize file upload display
    if (DOM.excelFile) {
        DOM.excelFile.addEventListener('change', function(e) {
            const fileName = e.target.files[0] ? e.target.files[0].name : 'Choose File';
            if (DOM.fileText) {
                DOM.fileText.textContent = fileName;
            }
        });
    }
}

async function loadUploadedFiles() {
    if (!DOM.fileDropdown || !DOM.dropdownSpinner) return;

    try {
        // Show loading state
        DOM.dropdownSpinner.style.display = 'inline-block';
        DOM.fileDropdown.innerHTML = '<option value="">-- Loading files... --</option>';
        DOM.fileDropdown.disabled = true;

        const response = await fetch('/api/uploaded_files', {
            method: 'GET',
            credentials: 'include'
        });
        
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

        populateFileDropdown(data.files || []);

    } catch (error) {
        console.error('Error loading files:', error);
        
        let errorMessage = 'Failed to load file list';
        if (error.message.includes('HTML')) {
            errorMessage = 'Authentication required. Please refresh the page.';
        } else if (error.message.includes('Network')) {
            errorMessage = 'Network error. Please check your connection.';
        } else {
            errorMessage = error.message;
        }
        
        showNotification(errorMessage, 'error');
        populateFileDropdown([]);
    } finally {
        DOM.dropdownSpinner.style.display = 'none';
        DOM.fileDropdown.disabled = false;
    }
}

function populateFileDropdown(files) {
    if (!DOM.fileDropdown) return;

    // Clear all options
    DOM.fileDropdown.innerHTML = '';

    if (!files || files.length === 0) {
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = '-- No files uploaded yet --';
        emptyOption.disabled = true;
        DOM.fileDropdown.appendChild(emptyOption);
        
        updateDeleteButtonState(false);
        return;
    }

    // Add default option
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '-- Select a file to delete --';
    DOM.fileDropdown.appendChild(defaultOption);

    // Add file options
    files.forEach(file => {
        const option = document.createElement('option');
        option.value = file.batch_id;
        
        const displayText = `${file.filename} (${file.upload_date}) - ${file.record_count} records`;
        option.textContent = displayText.length > 80 ? displayText.substring(0, 77) + '...' : displayText;
        
        option.title = `Filename: ${file.filename}\nUploaded: ${file.upload_date}\nRecords: ${file.record_count}`;
        DOM.fileDropdown.appendChild(option);
    });

    updateDeleteButtonState(false);
}

function updateDeleteButtonState(enabled) {
    if (DOM.deleteFileBtn) {
        DOM.deleteFileBtn.disabled = !enabled;
    }
}

function confirmDeleteFile() {
    const dropdown = DOM.fileDropdown;
    const selectedOption = dropdown.options[dropdown.selectedIndex];
    
    if (!selectedOption || selectedOption.value === '') {
        showNotification('Please select a file first', 'error');
        return false;
    }
    
    const filename = selectedOption.textContent.split(' (')[0];
    
    return confirm(`⚠️ DELETE CONFIRMATION\n\nFile: "${filename}"\n\nThis will:\n• Remove this file's data from database\n• Remove this file from UI\n• Keep all other files safe\n\nContinue?`);
}

/* ============================
   📋 DATA EXPORT
============================ */
function initializeDataExport() {
    const exportBtn = document.getElementById('exportBtn');
    if (!exportBtn || !DOM.summaryTable) return;

    exportBtn.addEventListener('click', exportTableToCSV);
}

function exportTableToCSV() {
    if (!APP_STATE.tableRows || APP_STATE.tableRows.length === 0) {
        showNotification('No data to export', 'error');
        return;
    }

    const visibleRows = APP_STATE.tableRows.filter(row => row.style.display !== 'none');
    
    if (visibleRows.length === 0) {
        showNotification('No visible data to export', 'error');
        return;
    }

    const headers = Array.from(DOM.thead.querySelectorAll('th'))
        .map(th => `"${th.textContent.trim()}"`)
        .join(',');

    const csvData = visibleRows.map(row => {
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
    
    showNotification('Data exported successfully', 'success');
}

/* ============================
   🔔 NOTIFICATION SYSTEM
============================ */
function showNotification(message, type = 'success') {
    // Remove existing notifications
    const existingNotif = document.querySelector('.custom-notification');
    if (existingNotif) existingNotif.remove();

    const notif = createElement(`
        <div class="custom-notification ${type}" style="
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${type === 'success' ? '#10b981' : '#ef4444'};
            color: white;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 9999;
            transform: translateX(100%);
            opacity: 0;
            transition: all 0.3s ease;
        ">
            <i class="fas fa-${type === 'success' ? 'check' : 'exclamation'}-circle"></i>
            <span>${message}</span>
        </div>
    `);

    document.body.appendChild(notif);

    // Animate in
    setTimeout(() => notif.style.cssText = notif.style.cssText.replace('translateX(100%)', 'translateX(0)').replace('opacity: 0', 'opacity: 1'), 100);

    // Remove after delay
    setTimeout(() => {
        notif.style.transform = 'translateX(100%)';
        notif.style.opacity = '0';
        setTimeout(() => notif.remove(), 300);
    }, 5000);
}

/* ============================
   ⌨️ KEYBOARD SHORTCUTS
============================ */
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + F to focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f' && DOM.agentSearch) {
            e.preventDefault();
            DOM.agentSearch.focus();
        }
        
        // Ctrl/Cmd + R to reset filters
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            resetAllFilters();
        }
        
        // Escape to clear search
        if (e.key === 'Escape' && DOM.agentSearch && DOM.agentSearch.value) {
            DOM.agentSearch.value = '';
            DOM.agentSearch.dispatchEvent(new Event('input'));
        }
    });
}

/* ============================
   🚀 MAIN INITIALIZATION
============================ */
function initializeMonthlyJS() {
    console.log('Initializing Monthly Attendance System...');
    
    // Cache DOM elements
    cacheElements();
    
    // Initialize libraries
    initializeSelect2();
    
    // Initialize UI components
    initializeSidebar();
    initializeFilters();
    initializeTableSearch();
    initializeTableSorting();
    initializeFileManagement();
    initializeDataExport();
    initializeKeyboardShortcuts();
    
    // Apply initial filters
    if (APP_STATE.tableRows.length > 0) {
        applyTableFilters();
    }
    
    console.log('Monthly Attendance System initialized successfully');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeMonthlyJS);
} else {
    initializeMonthlyJS();
}

// Export functions for debugging if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeMonthlyJS,
        applyTableFilters,
        resetAllFilters,
        loadUploadedFiles,
        exportTableToCSV
    };
}