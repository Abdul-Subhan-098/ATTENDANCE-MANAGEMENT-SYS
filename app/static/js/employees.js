/* =====================================================================
   EMPLOYEES.JS - OPTIMIZED VERSION
   Complete JavaScript functionality for employees.html
   Includes: Employee Management, Company Off Days, Compensation, Leave Management
===================================================================== */

/* ============================
   CONFIGURATION & CONSTANTS
============================ */
const CONFIG = {
    DEBOUNCE_DELAY: 300,
    BATCH_SIZE: 100,
    ANIMATION_FRAME_DELAY: 16,
    MAX_DATE: new Date().toISOString().split('T')[0] // Today's date
};

/* ============================
   GLOBAL STATE MANAGEMENT
============================ */
const APP_STATE = {
    abortController: null,
    activeFilters: { department: '' },
    tableRows: [],
    currentPage: 1,
    itemsPerPage: 10,
    currentEmployeeId: null
};

/* ============================
   DOM ELEMENTS CACHE
============================ */
const DOM = {};

/* ============================
   PERFORMANCE UTILITIES
============================ */

// Debounce function for input events
const debounce = (fn, delay = CONFIG.DEBOUNCE_DELAY) => {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
};

// Throttle function for scroll/resize events
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

// Fast DOM element creation
const createElement = (html) => {
    const template = document.createElement('template');
    template.innerHTML = html.trim();
    return template.content.firstElementChild;
};

/* ============================
   DOM CACHING & INITIALIZATION
============================ */

// Cache all DOM elements
function cacheElements() {
    const elementIds = [
        // Main elements
        'sidebar', 'mainContent', 'sidebarToggle', 'deleteModal',

        // Tab elements
        'globalTableSection',

        // Filter elements
        'employeeSearch', 'departmentFilter', 'clearFilters',

        // Table elements
        'employeesTable', 'paginationControls',
        'showingCount', 'totalCount', 'pageInfo', 'prevPage', 'nextPage',

        // Delete Modal elements
        'deleteEmployeeName', 'cancelDelete', 'confirmDelete', 'modal-close',

        // Add Employee Tab
        'addEmployeeBtn', 'clearEmployeeForm', 'employeeId', 'employeeName',
        'employeeJoinDate', 'employeeEffectiveDate', 'employeeDepartment', 'employeeGender', 'employeeShift', 'employeeRole',

        // Company Off Days
        'companyOffDate', 'companyOffReason', 'addCompanyOffDay',
        'removeCompanyOffDate', 'removeCompanyOffDay', 'companyOffDaysList',

        // Compensation Tab
        'compensationEmployee', 'compensationType', 'violationDate',
        'compensationDate', 'eligibilityResult', 'checkEligibilityBtn',
        'applyCompensationBtn', 'removeCompensationBtn', 'clearCompensationForm',
        'compensationResult', 'refreshHistoryBtn', 'compensationHistoryList',

        // Leave Management Tab
        'leaveEmployeeName', 'leaveType', 'leaveStartDate', 'leaveEndDate',
        'leaveReason', 'previewLeaveBtn', 'applyLeaveBtn', 'removeLeaveBtn',
        'clearLeaveForm', 'leaveResult', 'leavePreview', 'refreshLeaveHistoryBtn',
        'leaveHistoryList',

        // Temporary Shifts Tab
        'tempShiftEmployee', 'tempShiftValue', 'tempShiftStartDate', 'tempShiftEndDate',
        'addTempShiftBtn', 'clearTempShiftBtn', 'refreshTempShiftsBtn', 'tempShiftsTableBody',

        // Export Tab
        'exportData', 'exportFormat', 'exportMonth', 'exportYear',

        // System Tab
        'resetSettings', 'clearData',

        // Update Employee Tab
        'name', 'update_emp_id', 'department', 'effective_date', 'shift', 'role', 'gender',

        'employeeId', 'employeeName', 'employeeJoinDate', 'employeeEffectiveDate', 'employeeDepartment', 'employeeGender', 'employeeShift', 'employeeRole'
    ];

    // Cache elements by ID
    elementIds.forEach(id => {
        DOM[id] = document.getElementById(id);
    });

    // Cache all table rows
    if (DOM.employeesTable) {
        const tbody = DOM.employeesTable.querySelector('tbody');
        if (tbody) {
            APP_STATE.tableRows = Array.from(tbody.querySelectorAll('tr:not(.empty-state)'));
        }
    }

    // Cache all tab buttons and contents
    DOM.tabBtns = document.querySelectorAll('.tab-btn');
    DOM.tabContents = document.querySelectorAll('.tab-content');

    // Cache action buttons
    const editButtons = document.querySelectorAll('.btn-edit');
    const deleteButtons = document.querySelectorAll('.btn-delete');

    editButtons.forEach(btn => {
        btn.addEventListener('click', handleEditEmployee);
    });

    deleteButtons.forEach(btn => {
        btn.addEventListener('click', handleDeleteEmployee);
    });
}

// Initialize date pickers
function initializeDatePickers() {
    const datePickers = document.querySelectorAll('.date-picker');

    datePickers.forEach(picker => {
        if (window.flatpickr) {
            flatpickr(picker, {
                dateFormat: "Y-m-d",
                allowInput: true,
                maxDate: CONFIG.MAX_DATE,
                defaultDate: picker.value || CONFIG.MAX_DATE
            });
        }
    });

    // Company off days date picker (no max date limit)
    if (DOM.companyOffDate && window.flatpickr) {
        flatpickr(DOM.companyOffDate, {
            dateFormat: "Y-m-d",
            allowInput: true,
            defaultDate: CONFIG.MAX_DATE
        });
    }

    // Compensation form date pickers
    if (window.flatpickr) {
        if (DOM.violationDate) {
            flatpickr(DOM.violationDate, {
                dateFormat: "Y-m-d",
                allowInput: true,
                maxDate: CONFIG.MAX_DATE
            });
        }

        if (DOM.compensationDate) {
            flatpickr(DOM.compensationDate, {
                dateFormat: "Y-m-d",
                allowInput: true,
                maxDate: CONFIG.MAX_DATE
            });
        }

        // Leave form date pickers
        if (DOM.leaveStartDate) {
            flatpickr(DOM.leaveStartDate, {
                dateFormat: "Y-m-d",
                allowInput: true,
                maxDate: CONFIG.MAX_DATE,
                defaultDate: CONFIG.MAX_DATE
            });
        }

        if (DOM.leaveEndDate) {
            flatpickr(DOM.leaveEndDate, {
                dateFormat: "Y-m-d",
                allowInput: true,
                maxDate: CONFIG.MAX_DATE,
                defaultDate: CONFIG.MAX_DATE
            });
        }

        // Add employee form date picker
        if (DOM.employeeJoinDate) {
            flatpickr(DOM.employeeJoinDate, {
                dateFormat: "Y-m-d",
                allowInput: true,
                maxDate: CONFIG.MAX_DATE,
                defaultDate: CONFIG.MAX_DATE
            });
        }

        // Joining date picker
        const joiningDatePicker = document.getElementById('joining_date');
        if (joiningDatePicker) {
            flatpickr(joiningDatePicker, {
                dateFormat: "Y-m-d",
                allowInput: true,
                maxDate: CONFIG.MAX_DATE,
                defaultDate: joiningDatePicker.value || CONFIG.MAX_DATE
            });
        }

        // Effective date picker
        const effectiveDatePicker = document.getElementById('effective_date');
        if (effectiveDatePicker) {
            flatpickr(effectiveDatePicker, {
                dateFormat: "Y-m-d",
                allowInput: true,
                maxDate: CONFIG.MAX_DATE,
                defaultDate: effectiveDatePicker.value || CONFIG.MAX_DATE
            });
        }

        // Temporary shift date pickers (allow future dates)
        if (DOM.tempShiftStartDate) {
            flatpickr(DOM.tempShiftStartDate, {
                dateFormat: "Y-m-d",
                allowInput: true,
                defaultDate: CONFIG.MAX_DATE
            });
        }

        if (DOM.tempShiftEndDate) {
            flatpickr(DOM.tempShiftEndDate, {
                dateFormat: "Y-m-d",
                allowInput: true,
                defaultDate: CONFIG.MAX_DATE
            });
        }
    }
}

// Initialize sidebar functionality
function initializeSidebar() {
    if (!DOM.sidebarToggle) return;

    DOM.sidebarToggle.addEventListener('click', function () {
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
   TAB SWITCHING FUNCTIONALITY
============================ */

// Initialize tab system
function initializeTabs() {
    if (!DOM.tabBtns.length || !DOM.tabContents.length) return;

    DOM.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all buttons and contents
            DOM.tabBtns.forEach(b => b.classList.remove('active'));
            DOM.tabContents.forEach(c => c.classList.remove('active'));

            // Add active class to clicked button
            btn.classList.add('active');

            // Show corresponding content
            const tabId = btn.getAttribute('data-tab');
            const tabContent = document.getElementById(tabId);

            if (tabContent) {
                tabContent.classList.add('active');
            }

            // Show/hide employee table based on active tab
            if (DOM.globalTableSection) {
                if (tabId === 'add-employee' || tabId === 'update-employee') {
                    DOM.globalTableSection.style.display = 'block';
                } else {
                    DOM.globalTableSection.style.display = 'none';
                }
            }
        });
    });

    // Initialize - hide table for non-employee tabs
    const activeTab = document.querySelector('.tab-btn.active');
    const activeTabId = activeTab ? activeTab.getAttribute('data-tab') : 'add-employee';

    if (DOM.globalTableSection) {
        if (activeTabId === 'add-employee' || activeTabId === 'update-employee') {
            DOM.globalTableSection.style.display = 'block';
        } else {
            DOM.globalTableSection.style.display = 'none';
        }
    }
}

/* ============================
   EMPLOYEE TABLE FUNCTIONALITY
============================ */

// Initialize table filters
function initializeTableFilters() {
    if (!DOM.employeeSearch || !DOM.departmentFilter) return;

    const searchHandler = debounce(function () {
        applyEmployeeFilters();
    });

    DOM.employeeSearch.addEventListener('input', searchHandler);
    DOM.departmentFilter.addEventListener('change', searchHandler);

    if (DOM.clearFilters) {
        DOM.clearFilters.addEventListener('click', resetEmployeeFilters);
    }
}

// Apply filters to employee table
function applyEmployeeFilters() {
    if (!APP_STATE.tableRows || APP_STATE.tableRows.length === 0) return;

    const searchTerm = DOM.employeeSearch.value.toLowerCase();
    const departmentFilter = DOM.departmentFilter.value;

    let visibleCount = 0;

    APP_STATE.tableRows.forEach(row => {
        let showRow = true;
        const name = row.cells[1]?.textContent.toLowerCase() || '';
        const department = row.dataset.department || '';

        // Apply search filter
        if (searchTerm && !name.includes(searchTerm)) {
            showRow = false;
        }

        // Apply department filter
        if (departmentFilter && department !== departmentFilter) {
            showRow = false;
        }

        // Show/hide row
        row.style.display = showRow ? '' : 'none';
        if (showRow) visibleCount++;
    });

    // Update pagination
    APP_STATE.currentPage = 1;
    updatePagination(visibleCount);
}

// Reset all filters
function resetEmployeeFilters() {
    if (DOM.employeeSearch) DOM.employeeSearch.value = '';
    if (DOM.departmentFilter) DOM.departmentFilter.value = '';

    applyEmployeeFilters();
}

// Initialize pagination
function initializePagination() {
    if (!DOM.prevPage || !DOM.nextPage || !DOM.pageInfo) return;

    DOM.prevPage.addEventListener('click', goToPreviousPage);
    DOM.nextPage.addEventListener('click', goToNextPage);

    // Initial pagination update
    updatePagination(APP_STATE.tableRows.length);
}

// Go to previous page
function goToPreviousPage() {
    if (APP_STATE.currentPage > 1) {
        APP_STATE.currentPage--;
        updateTableDisplay();
        updatePaginationButtons();
    }
}

// Go to next page
function goToNextPage() {
    const visibleRows = APP_STATE.tableRows.filter(r => r.style.display !== 'none');
    const totalPages = Math.ceil(visibleRows.length / APP_STATE.itemsPerPage);

    if (APP_STATE.currentPage < totalPages) {
        APP_STATE.currentPage++;
        updateTableDisplay();
        updatePaginationButtons();
    }
}

// Update pagination display
function updatePagination(totalItems) {
    const totalPages = Math.ceil(totalItems / APP_STATE.itemsPerPage);

    if (DOM.showingCount) {
        const startIndex = (APP_STATE.currentPage - 1) * APP_STATE.itemsPerPage + 1;
        const endIndex = Math.min(APP_STATE.currentPage * APP_STATE.itemsPerPage, totalItems);
        DOM.showingCount.textContent = endIndex > 0 ? `${startIndex}-${endIndex}` : '0';
    }

    if (DOM.totalCount) {
        DOM.totalCount.textContent = totalItems;
    }

    if (DOM.pageInfo) {
        DOM.pageInfo.textContent = `Page ${APP_STATE.currentPage} of ${totalPages}`;
    }

    updateTableDisplay();
    updatePaginationButtons();
}

// Update table display for current page
function updateTableDisplay() {
    const visibleRows = APP_STATE.tableRows.filter(row => row.style.display !== 'none');
    const startIndex = (APP_STATE.currentPage - 1) * APP_STATE.itemsPerPage;
    const endIndex = startIndex + APP_STATE.itemsPerPage;

    // Hide all rows first
    APP_STATE.tableRows.forEach(row => {
        if (row.style.display !== 'none') {
            row.style.display = 'none';
        }
    });

    // Show only rows for current page
    visibleRows.slice(startIndex, endIndex).forEach(row => {
        row.style.display = '';
    });
}

// Update pagination button states
function updatePaginationButtons() {
    const visibleRows = APP_STATE.tableRows.filter(row => row.style.display !== 'none');
    const totalPages = Math.ceil(visibleRows.length / APP_STATE.itemsPerPage);

    if (DOM.prevPage) {
        DOM.prevPage.disabled = APP_STATE.currentPage <= 1;
    }

    if (DOM.nextPage) {
        DOM.nextPage.disabled = APP_STATE.currentPage >= totalPages;
    }
}

/* ============================
   EMPLOYEE CRUD OPERATIONS
============================ */
// ===========================================================
//               TEMPORARY SHIFT MANAGEMENT
// ===========================================================

/**
 * Loads all temporary shifts and populates the table
 */
async function loadTemporaryShifts() {
    if (!DOM.tempShiftsTableBody) return;

    try {
        const response = await fetch('/api/temporary_shift/list/all');
        const data = await response.json();

        if (data.success) {
            DOM.tempShiftsTableBody.innerHTML = '';

            if (data.shifts.length === 0) {
                DOM.tempShiftsTableBody.innerHTML = `
                    <tr class="empty-state">
                        <td colspan="5">
                            <i class="fas fa-calendar-times"></i>
                            <p>No temporary shifts found</p>
                        </td>
                    </tr>
                `;
                return;
            }

            data.shifts.forEach(shift => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${shift.emp_id}</td>
                    <td>${shift.shift}</td>
                    <td>${shift.start_date}</td>
                    <td>${shift.end_date}</td>
                    <td>
                        <button class="btn-icon btn-delete" onclick="deleteTempShift(${shift.id})" title="Delete">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                `;
                DOM.tempShiftsTableBody.appendChild(tr);
            });
        }
    } catch (error) {
        console.error('Error loading temporary shifts:', error);
        showAlert('error', 'Failed to load temporary shifts');
    }
}

/**
 * Handles adding a new temporary shift
 */
async function handleAddTempShift() {
    const empNameOrId = DOM.tempShiftEmployee.value.trim();
    const shift = DOM.tempShiftValue.value;
    const startDate = DOM.tempShiftStartDate.value;
    const endDate = DOM.tempShiftEndDate.value;

    if (!empNameOrId || !shift || !startDate || !endDate) {
        showAlert('warning', 'Please fill in all required fields');
        return;
    }

    // Try to get emp_id from the employee suggestions if it's a name
    // For now, we assume the user might have typed an ID or a Name.
    // Let's try to resolve it.
    let empId = empNameOrId;

    // Check if it's a name (heuristic: contains space or more than 5 chars but not all numeric)
    // Actually, it's better to just send it to backend and let it handle ID lookup or validation.
    // However, the backend expects emp_id.

    // We can try to find the emp_id from the global state if available
    const employee = APP_STATE.tableRows.find(row => {
        const cells = row.querySelectorAll('td');
        return cells[1].textContent === empNameOrId || cells[0].textContent === empNameOrId;
    });

    if (employee) {
        empId = employee.querySelectorAll('td')[0].textContent;
    }

    try {
        const response = await fetch('/api/temporary_shift/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                emp_id: empId,
                shift: shift,
                start_date: startDate,
                end_date: endDate
            })
        });

        const data = await response.json();

        if (data.success) {
            showAlert('success', 'Temporary shift added successfully');
            clearTempShiftForm();
            loadTemporaryShifts();
        } else {
            showAlert('error', data.message || 'Failed to add temporary shift');
        }
    } catch (error) {
        console.error('Error adding temporary shift:', error);
        showAlert('error', 'An error occurred while adding the shift');
    }
}

/**
 * Deletes a temporary shift
 */
async function deleteTempShift(id) {
    if (!confirm('Are you sure you want to delete this temporary shift?')) return;

    try {
        const response = await fetch(`/api/temporary_shift/delete/${id}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showAlert('success', 'Temporary shift deleted successfully');
            loadTemporaryShifts();
        } else {
            showAlert('error', data.message || 'Failed to delete temporary shift');
        }
    } catch (error) {
        console.error('Error deleting temporary shift:', error);
        showAlert('error', 'An error occurred while deleting the shift');
    }
}

/**
 * Clears the temporary shift form
 */
function clearTempShiftForm() {
    DOM.tempShiftEmployee.value = '';
    DOM.tempShiftValue.value = '';
    DOM.tempShiftStartDate.value = '';
    DOM.tempShiftEndDate.value = '';

    // Clear date pickers if they have a clear method, otherwise manual
    if (DOM.tempShiftStartDate._flatpickr) DOM.tempShiftStartDate._flatpickr.clear();
    if (DOM.tempShiftEndDate._flatpickr) DOM.tempShiftEndDate._flatpickr.clear();
}

// Initialize employee operations
function initializeEmployeeOperations() {
    if (DOM.clearEmployeeForm) {
        DOM.clearEmployeeForm.addEventListener('click', clearEmployeeForm);
    }

    // Initialize delete modal
    initializeDeleteModal();

    // Searchable name field in Update Employee
    if (DOM.name) {
        DOM.name.addEventListener('input', handleNameSelection);
    }

    // Searchable name field in Add Employee
    if (DOM.employeeName) {
        DOM.employeeName.addEventListener('input', handleNewEmployeeSelection);
    }

    // Temporary Shifts Tab
    if (DOM.addTempShiftBtn) {
        DOM.addTempShiftBtn.addEventListener('click', handleAddTempShift);
    }
    if (DOM.clearTempShiftBtn) {
        DOM.clearTempShiftBtn.addEventListener('click', clearTempShiftForm);
    }
    if (DOM.refreshTempShiftsBtn) {
        DOM.refreshTempShiftsBtn.addEventListener('click', loadTemporaryShifts);
    }

    // Auto-load shifts when tab is clicked
    if (DOM.tabBtns) {
        DOM.tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.getAttribute('data-tab') === 'temporary-shifts') {
                    loadTemporaryShifts();
                }
            });
        });
    }
}

// Handle new employee selection from datalist and auto-fill
function handleNewEmployeeSelection() {
    const name = DOM.employeeName.value.trim();
    const options = document.getElementById('potential-employee-datalist').options;

    // Check if the typed value exists in our datalist
    let found = false;
    for (let i = 0; i < options.length; i++) {
        if (options[i].value === name) {
            found = true;
            break;
        }
    }

    if (found) {
        // Fetch potential employee details
        fetch(`/api/potential_employee/details/${encodeURIComponent(name)}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (DOM.employeeId) DOM.employeeId.value = data.employee.emp_id;
                    if (DOM.employeeJoinDate) DOM.employeeJoinDate.value = data.employee.joining_date;
                    if (DOM.employeeEffectiveDate) DOM.employeeEffectiveDate.value = data.employee.joining_date;

                    // Refresh date pickers if flatpickr is used
                    if (window.flatpickr) {
                        if (DOM.employeeJoinDate && DOM.employeeJoinDate._flatpickr) {
                            DOM.employeeJoinDate._flatpickr.setDate(data.employee.joining_date);
                        }
                        if (DOM.employeeEffectiveDate && DOM.employeeEffectiveDate._flatpickr) {
                            DOM.employeeEffectiveDate._flatpickr.setDate(data.employee.joining_date);
                        }
                    }

                    showNotification(`Detected ID and Joining Date for ${name}`, 'info');
                }
            })
            .catch(error => {
                console.error('Error fetching potential employee details:', error);
            });
    }
}

// Handle name selection from datalist and auto-fill
function handleNameSelection() {
    const name = DOM.name.value.trim();
    const options = document.getElementById('employee-datalist').options;

    // Check if the typed value exists in our datalist
    let found = false;
    for (let i = 0; i < options.length; i++) {
        if (options[i].value === name) {
            found = true;
            break;
        }
    }

    if (found) {
        // Fetch employee details from API
        fetch(`/api/employee/details/${encodeURIComponent(name)}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    fillUpdateForm(data.employee);
                    showNotification(`Employee details loaded for ${name}`, 'info');
                }
            })
            .catch(error => {
                console.error('Error fetching employee details:', error);
            });
    }
}

// Fill the update form with employee data
function fillUpdateForm(details) {
    if (DOM.update_emp_id) DOM.update_emp_id.value = details.emp_id || '';
    if (DOM.department) DOM.department.value = details.department || '';
    if (DOM.effective_date) DOM.effective_date.value = details.last_updated_date || details.joining_date;
    if (DOM.shift) DOM.shift.value = details.shift;
    if (DOM.role) DOM.role.value = details.role;
    if (DOM.gender) DOM.gender.value = details.gender;

    // Date pickers refresh
    if (window.flatpickr) {
        if (DOM.effective_date && DOM.effective_date._flatpickr) {
            DOM.effective_date._flatpickr.setDate(details.last_updated_date || details.joining_date);
        }
    }
}


// Clear employee form
function clearEmployeeForm() {
    if (DOM.employeeId) DOM.employeeId.value = '';
    if (DOM.employeeName) DOM.employeeName.value = '';
    if (DOM.employeeJoinDate) DOM.employeeJoinDate.value = '';
    if (DOM.employeeDepartment) DOM.employeeDepartment.value = '';
    if (DOM.employeeShift) DOM.employeeShift.value = '';
    if (DOM.employeeRole) DOM.employeeRole.value = '';
}

// Handle edit employee
function handleEditEmployee(event) {
    const button = event.currentTarget;
    const employeeId = button.getAttribute('data-id');
    const employeeName = button.getAttribute('data-name');

    // Switch to update employee tab
    const updateTabBtn = document.querySelector('.tab-btn[data-tab="update-employee"]');
    if (updateTabBtn) {
        updateTabBtn.click();
    }

    // Find employee select/input
    if (DOM.name) {
        DOM.name.value = employeeName;
        // Trigger the input event to load data
        DOM.name.dispatchEvent(new Event('input'));
    }

    showNotification(`Editing employee: ${employeeName}`, 'info');
}

// Handle delete employee
function handleDeleteEmployee(event) {
    const button = event.currentTarget;
    const employeeId = button.getAttribute('data-id');
    const employeeName = button.getAttribute('data-name');

    APP_STATE.currentEmployeeId = employeeId;

    if (DOM.deleteEmployeeName) {
        DOM.deleteEmployeeName.textContent = employeeName;
    }

    if (DOM.deleteModal) {
        DOM.deleteModal.style.display = 'flex';
    }
}

// Initialize delete modal
function initializeDeleteModal() {
    if (!DOM.deleteModal) return;

    // Close modal when clicking X or cancel
    const closeModal = () => {
        DOM.deleteModal.style.display = 'none';
        APP_STATE.currentEmployeeId = null;
    };

    if (DOM['modal-close']) {
        DOM['modal-close'].addEventListener('click', closeModal);
    }

    if (DOM.cancelDelete) {
        DOM.cancelDelete.addEventListener('click', closeModal);
    }

    // Confirm delete
    if (DOM.confirmDelete) {
        DOM.confirmDelete.addEventListener('click', confirmDeleteEmployee);
    }

    // Close modal when clicking outside
    DOM.deleteModal.addEventListener('click', (event) => {
        if (event.target === DOM.deleteModal) {
            closeModal();
        }
    });
}

// Confirm delete employee
function confirmDeleteEmployee() {
    if (!APP_STATE.currentEmployeeId) return;

    // Show loading state
    const originalText = DOM.confirmDelete.innerHTML;
    DOM.confirmDelete.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deleting...';
    DOM.confirmDelete.disabled = true;

    // Simulate API call
    setTimeout(() => {
        showNotification('Employee deleted successfully', 'success');

        // Close modal
        DOM.deleteModal.style.display = 'none';
        APP_STATE.currentEmployeeId = null;

        // Restore button state
        DOM.confirmDelete.innerHTML = originalText;
        DOM.confirmDelete.disabled = false;

        // Refresh employee list
        setTimeout(() => {
            window.location.reload();
        }, 500);
    }, 1000);
}

/* ============================
   COMPANY OFF DAYS FUNCTIONALITY
============================ */

// Initialize company off days
function initializeCompanyOffDays() {
    if (!DOM.addCompanyOffDay || !DOM.removeCompanyOffDay) return;

    DOM.addCompanyOffDay.addEventListener('click', addCompanyOffDay);
    DOM.removeCompanyOffDay.addEventListener('click', removeCompanyOffDay);

    // Load existing company off days
    loadCompanyOffDays();

    // Populate remove dropdown
    populateRemoveCompanyOffDropdown();
}

// Add company off day
function addCompanyOffDay() {
    const date = DOM.companyOffDate?.value;
    const reason = DOM.companyOffReason?.value.trim() || 'Company Holiday';

    if (!date) {
        showNotification('Please select a date', 'error');
        return;
    }

    // Show loading state
    const originalText = DOM.addCompanyOffDay.innerHTML;
    DOM.addCompanyOffDay.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    DOM.addCompanyOffDay.disabled = true;

    // API call to add company off day
    fetch('/company_day_off', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'add',
            date: date,
            reason: reason
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');

                // Clear form
                if (DOM.companyOffDate) DOM.companyOffDate.value = '';
                if (DOM.companyOffReason) DOM.companyOffReason.value = '';

                // Reload company off days
                loadCompanyOffDays();
                populateRemoveCompanyOffDropdown();
            } else {
                showNotification(data.message, 'error');
            }
        })
        .catch(error => {
            showNotification('Failed to add company off day', 'error');
            console.error('Error:', error);
        })
        .finally(() => {
            // Restore button state
            DOM.addCompanyOffDay.innerHTML = originalText;
            DOM.addCompanyOffDay.disabled = false;
        });
}

// Remove company off day
function removeCompanyOffDay() {
    const date = DOM.removeCompanyOffDate?.value;

    if (!date) {
        showNotification('Please select a date to remove', 'error');
        return;
    }

    if (!confirm(`Are you sure you want to remove company off day on ${date}?`)) {
        return;
    }

    // Show loading state
    const originalText = DOM.removeCompanyOffDay.innerHTML;
    DOM.removeCompanyOffDay.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing...';
    DOM.removeCompanyOffDay.disabled = true;

    // API call to remove company off day
    fetch('/company_day_off', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'remove',
            date: date
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');

                // Reload company off days
                loadCompanyOffDays();
                populateRemoveCompanyOffDropdown();

                // Reset dropdown
                if (DOM.removeCompanyOffDate) DOM.removeCompanyOffDate.value = '';
            } else {
                showNotification(data.message, 'error');
            }
        })
        .catch(error => {
            showNotification('Failed to remove company off day', 'error');
            console.error('Error:', error);
        })
        .finally(() => {
            // Restore button state
            DOM.removeCompanyOffDay.innerHTML = originalText;
            DOM.removeCompanyOffDay.disabled = false;
        });
}

// Load company off days
function loadCompanyOffDays() {
    if (!DOM.companyOffDaysList) return;

    fetch('/api/company_off_days')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.off_days.length > 0) {
                let html = '';
                data.off_days.forEach(day => {
                    html += `
                        <div class="company-off-day-item">
                            <div class="company-off-day-date">
                                <i class="fas fa-calendar-day"></i>
                                ${day.date}
                            </div>
                            <div class="company-off-day-reason">
                                ${day.reason}
                            </div>
                            <div class="company-off-day-created">
                                <small>Added: ${day.created_at}</small>
                            </div>
                        </div>
                    `;
                });
                DOM.companyOffDaysList.innerHTML = html;
            } else {
                DOM.companyOffDaysList.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-calendar-times"></i>
                        <p>No company days off scheduled</p>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading company off days:', error);
            DOM.companyOffDaysList.innerHTML = `
                <div class="empty-state error">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>Failed to load company off days</p>
                </div>
            `;
        });
}

// Populate remove company off dropdown
function populateRemoveCompanyOffDropdown() {
    if (!DOM.removeCompanyOffDate) return;

    fetch('/api/company_off_days')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.off_days.length > 0) {
                let options = '<option value="">Select date to remove</option>';
                data.off_days.forEach(day => {
                    options += `<option value="${day.date}">${day.date} - ${day.reason}</option>`;
                });
                DOM.removeCompanyOffDate.innerHTML = options;
            } else {
                DOM.removeCompanyOffDate.innerHTML = '<option value="">No company days off available</option>';
            }
        })
        .catch(error => {
            console.error('Error loading company off days for dropdown:', error);
            DOM.removeCompanyOffDate.innerHTML = '<option value="">Error loading dates</option>';
        });
}

/* ============================
   COMPENSATION FUNCTIONALITY
============================ */

// Initialize compensation
function initializeCompensation() {
    if (!DOM.checkEligibilityBtn || !DOM.applyCompensationBtn) return;

    DOM.checkEligibilityBtn.addEventListener('click', checkCompensationEligibility);
    DOM.applyCompensationBtn.addEventListener('click', applyCompensation);
    DOM.removeCompensationBtn.addEventListener('click', removeCompensation);

    if (DOM.clearCompensationForm) {
        DOM.clearCompensationForm.addEventListener('click', clearCompensationForm);
    }

    if (DOM.refreshHistoryBtn) {
        DOM.refreshHistoryBtn.addEventListener('click', loadCompensationHistory);
    }

    // Load compensation history on initialization
    loadCompensationHistory();
}

// Check compensation eligibility
function checkCompensationEligibility() {
    const employeeName = DOM.compensationEmployee?.value.trim();
    const compensationType = DOM.compensationType?.value;
    const violationDate = DOM.violationDate?.value;
    const compensationDate = DOM.compensationDate?.value;

    if (!employeeName || !compensationType || !violationDate || !compensationDate) {
        showNotification('Please fill all required fields', 'error');
        return;
    }

    // Show loading state
    const originalText = DOM.checkEligibilityBtn.innerHTML;
    DOM.checkEligibilityBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
    DOM.checkEligibilityBtn.disabled = true;

    // API call to check eligibility
    fetch('/check_compensation_eligibility', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            employee_name: employeeName,
            violation_date: violationDate,
            compensation_date: compensationDate,
            compensation_type: compensationType
        })
    })
        .then(response => response.json())
        .then(data => {
            if (DOM.eligibilityResult) {
                DOM.eligibilityResult.textContent = data.message;
                DOM.eligibilityResult.className = 'eligibility-result ' + (data.eligible ? 'eligible' : 'not-eligible');
                DOM.eligibilityResult.style.display = 'block';
            }
        })
        .catch(error => {
            showNotification('Failed to check eligibility', 'error');
            console.error('Error:', error);
        })
        .finally(() => {
            // Restore button state
            DOM.checkEligibilityBtn.innerHTML = originalText;
            DOM.checkEligibilityBtn.disabled = false;
        });
}

// Apply compensation
function applyCompensation() {
    const employeeName = DOM.compensationEmployee?.value.trim();
    const compensationType = DOM.compensationType?.value;
    const violationDate = DOM.violationDate?.value;
    const compensationDate = DOM.compensationDate?.value;

    if (!employeeName || !compensationType || !violationDate || !compensationDate) {
        showNotification('Please fill all required fields', 'error');
        return;
    }

    // Show loading state
    const originalText = DOM.applyCompensationBtn.innerHTML;
    DOM.applyCompensationBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
    DOM.applyCompensationBtn.disabled = true;

    // API call to apply compensation
    fetch('/apply_compensation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            employee_name: employeeName,
            violation_date: violationDate,
            compensation_date: compensationDate,
            compensation_type: compensationType
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                clearCompensationForm();
                loadCompensationHistory();
            } else {
                showNotification(data.message, 'error');
            }
        })
        .catch(error => {
            showNotification('Failed to apply compensation', 'error');
            console.error('Error:', error);
        })
        .finally(() => {
            // Restore button state
            DOM.applyCompensationBtn.innerHTML = originalText;
            DOM.applyCompensationBtn.disabled = false;
        });
}

// Remove compensation
function removeCompensation() {
    const employeeName = DOM.compensationEmployee?.value.trim();
    const violationDate = DOM.violationDate?.value;

    if (!employeeName || !violationDate) {
        showNotification('Please fill employee name and violation date', 'error');
        return;
    }

    if (!confirm(`Are you sure you want to remove compensation for ${employeeName} on ${violationDate}?`)) {
        return;
    }

    // Show loading state
    const originalText = DOM.removeCompensationBtn.innerHTML;
    DOM.removeCompensationBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing...';
    DOM.removeCompensationBtn.disabled = true;

    // API call to remove compensation
    fetch('/remove_compensation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            employee_name: employeeName,
            violation_date: violationDate
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                clearCompensationForm();
                loadCompensationHistory();
            } else {
                showNotification(data.message, 'error');
            }
        })
        .catch(error => {
            showNotification('Failed to remove compensation', 'error');
            console.error('Error:', error);
        })
        .finally(() => {
            // Restore button state
            DOM.removeCompensationBtn.innerHTML = originalText;
            DOM.removeCompensationBtn.disabled = false;
        });
}

// Clear compensation form
function clearCompensationForm() {
    if (DOM.compensationEmployee) DOM.compensationEmployee.value = '';
    if (DOM.compensationType) DOM.compensationType.value = '';
    if (DOM.violationDate) DOM.violationDate.value = '';
    if (DOM.compensationDate) DOM.compensationDate.value = '';
    if (DOM.eligibilityResult) DOM.eligibilityResult.style.display = 'none';
    if (DOM.compensationResult) DOM.compensationResult.style.display = 'none';
}

// Load compensation history
function loadCompensationHistory() {
    if (!DOM.compensationHistoryList) return;

    // Show loading state
    const originalText = DOM.refreshHistoryBtn?.innerHTML;
    if (DOM.refreshHistoryBtn) {
        DOM.refreshHistoryBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        DOM.refreshHistoryBtn.disabled = true;
    }

    fetch('/api/compensation_history')
        .then(response => response.json())
        .then(data => {
            if (data.history && data.history.length > 0) {
                let html = '';
                data.history.forEach(item => {
                    html += `
                        <div class="compensation-history-item">
                            <div class="history-item-header">
                                <span class="employee-name">${item.employee_name}</span>
                                <span class="history-date">${item.date}</span>
                            </div>
                            <div class="history-item-content">
                                <span class="compensation-type ${item.compensation_type.toLowerCase().replace(' ', '-')}">
                                    ${item.compensation_type}
                                </span>
                                <span class="details">Violation: ${item.violation_date} | Compensation: ${item.compensation_date}</span>
                            </div>
                        </div>
                    `;
                });
                DOM.compensationHistoryList.innerHTML = html;
            } else {
                DOM.compensationHistoryList.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-history"></i>
                        <p>No compensation history found</p>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading compensation history:', error);
            DOM.compensationHistoryList.innerHTML = `
                <div class="empty-state error">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>Failed to load compensation history</p>
                </div>
            `;
        })
        .finally(() => {
            // Restore button state
            if (DOM.refreshHistoryBtn) {
                DOM.refreshHistoryBtn.innerHTML = originalText;
                DOM.refreshHistoryBtn.disabled = false;
            }
        });
}

/* ============================
   LEAVE MANAGEMENT FUNCTIONALITY
============================ */

// Leave Management Module
const LeaveManagement = (() => {
    // Cache DOM elements
    const DOM = {
        leaveEmployeeName: document.getElementById('leaveEmployeeName'),
        leaveType: document.getElementById('leaveType'),
        leaveStartDate: document.getElementById('leaveStartDate'),
        leaveEndDate: document.getElementById('leaveEndDate'),
        leaveReason: document.getElementById('leaveReason'),
        previewLeaveBtn: document.getElementById('previewLeaveBtn'),
        applyLeaveBtn: document.getElementById('applyLeaveBtn'),
        removeLeaveBtn: document.getElementById('removeLeaveBtn'),
        clearLeaveForm: document.getElementById('clearLeaveForm'),
        leavePreview: document.getElementById('leavePreview'),
        leaveResult: document.getElementById('leaveResult'),
        leaveTableBody: document.getElementById('leaveTableBody'),
        refreshLeaveHistoryBtn: document.getElementById('refreshLeaveHistoryBtn')
    };

    // Notification helper
    function showNotification(message, type = 'success') {
        if (!DOM.leaveResult) return;
        DOM.leaveResult.textContent = message;
        DOM.leaveResult.className = `result-message ${type}`;
        DOM.leaveResult.style.display = 'block';
        setTimeout(() => DOM.leaveResult.style.display = 'none', 3000);
    }

    // Preview Leave
    function previewLeave() {
        const employeeName = DOM.leaveEmployeeName?.value;
        const leaveType = DOM.leaveType?.value;
        const startDate = DOM.leaveStartDate?.value;
        const endDate = DOM.leaveEndDate?.value;
        const reason = DOM.leaveReason?.value;

        if (!employeeName || !leaveType || !startDate || !endDate) {
            showNotification('Please fill all required fields', 'error');
            return;
        }

        if (new Date(startDate) > new Date(endDate)) {
            showNotification('Start date cannot be later than end date', 'error');
            return;
        }

        const totalDays = Math.ceil((new Date(endDate) - new Date(startDate)) / (1000 * 3600 * 24)) + 1;

        if (DOM.leavePreview) {
            document.getElementById('previewEmployeeName').textContent = employeeName;
            document.getElementById('previewLeaveType').textContent = leaveType;
            document.getElementById('previewDateRange').textContent = `${startDate} to ${endDate}`;
            document.getElementById('previewTotalDays').textContent = `${totalDays} day(s)`;
            document.getElementById('previewReason').textContent = reason || 'No reason provided';
            DOM.leavePreview.classList.add('show');
        }
    }

    // Apply Leave
    async function applyLeave() {
        const employeeName = DOM.leaveEmployeeName?.value;
        const leaveType = DOM.leaveType?.value;
        const startDate = DOM.leaveStartDate?.value;
        const endDate = DOM.leaveEndDate?.value;
        const reason = DOM.leaveReason?.value;

        if (!employeeName || !leaveType || !startDate || !endDate) {
            showNotification('Please fill all required fields', 'error');
            return;
        }

        const totalDays = Math.ceil((new Date(endDate) - new Date(startDate)) / (1000 * 3600 * 24)) + 1;

        const originalText = DOM.applyLeaveBtn.innerHTML;
        DOM.applyLeaveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
        DOM.applyLeaveBtn.disabled = true;

        try {
            const res = await fetch("/api/apply_leave", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    employee_name: employeeName,
                    start_date: startDate,
                    end_date: endDate,
                    leave_type: leaveType,
                    reason: reason
                })
            });

            const result = await res.json();
            if (result.success) {
                showNotification(result.message || "Leave applied successfully", 'success');
                clearLeaveForm();
                loadLeaveHistory();
            } else {
                showNotification(result.message || "Failed to apply leave", 'error');
            }
        } catch (err) {
            console.error(err);
            showNotification("Error applying leave", 'error');
        } finally {
            DOM.applyLeaveBtn.innerHTML = originalText;
            DOM.applyLeaveBtn.disabled = false;
        }
    }

    // Remove Leave
    async function removeLeave(employeeName, startDate, endDate) {
        if (!employeeName || !startDate || !endDate) {
            showNotification('Missing employee name or date range', 'error');
            return;
        }

        const originalText = DOM.removeLeaveBtn?.innerHTML;
        if (DOM.removeLeaveBtn) {
            DOM.removeLeaveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing...';
            DOM.removeLeaveBtn.disabled = true;
        }

        try {
            const res = await fetch("/api/remove_leave", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    employee_name: employeeName,
                    start_date: startDate,
                    end_date: endDate
                })
            });

            const result = await res.json();
            if (result.success) {
                showNotification(result.message || "Leave removed successfully", 'success');
                clearLeaveForm();
                loadLeaveHistory();
            } else {
                showNotification(result.message || "Failed to remove leave", 'error');
            }
        } catch (err) {
            console.error(err);
            showNotification("Error removing leave", 'error');
        } finally {
            if (DOM.removeLeaveBtn) {
                DOM.removeLeaveBtn.innerHTML = originalText;
                DOM.removeLeaveBtn.disabled = false;
            }
        }
    }

    // Clear Form
    function clearLeaveForm() {
        if (DOM.leaveEmployeeName) DOM.leaveEmployeeName.value = '';
        if (DOM.leaveType) DOM.leaveType.value = '';
        if (DOM.leaveStartDate) DOM.leaveStartDate.value = '';
        if (DOM.leaveEndDate) DOM.leaveEndDate.value = '';
        if (DOM.leaveReason) DOM.leaveReason.value = '';
        if (DOM.leavePreview) DOM.leavePreview.classList.remove('show');
    }

    // Load Leave History
    async function loadLeaveHistory() {
        if (!DOM.leaveTableBody) return;

        const originalText = DOM.refreshLeaveHistoryBtn?.innerHTML;
        if (DOM.refreshLeaveHistoryBtn) {
            DOM.refreshLeaveHistoryBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            DOM.refreshLeaveHistoryBtn.disabled = true;
        }

        try {
            const res = await fetch("/api/get_leave_history");
            if (!res.ok) throw new Error("Failed to fetch leave history");

            const data = await res.json();

            if (!data.length) {
                DOM.leaveTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center;">No leave applications found</td></tr>`;
                return;
            }

            let rowsHtml = '';
            data.forEach(leave => {
                rowsHtml += `
                    <tr>
                        <td>${leave.employee_name}</td>
                        <td>${leave.leave_type}</td>
                        <td>${leave.start_date}</td>
                        <td>${leave.end_date}</td>
                        <td>${leave.total_days}</td>
                        <td>${leave.reason || '-'}</td>
                        <td>
                            <button class="btn btn-sm btn-danger remove-btn" 
                                data-employee="${leave.employee_name}" 
                                data-start="${leave.start_date}" 
                                data-end="${leave.end_date}">
                                Remove
                            </button>
                        </td>
                    </tr>
                `;
            });

            DOM.leaveTableBody.innerHTML = rowsHtml;

            // Attach remove event listeners dynamically
            DOM.leaveTableBody.querySelectorAll('.remove-btn').forEach(btn => {
                btn.addEventListener('click', e => {
                    const emp = btn.getAttribute('data-employee');
                    const start = btn.getAttribute('data-start');
                    const end = btn.getAttribute('data-end');
                    removeLeave(emp, start, end);
                });
            });

        } catch (err) {
            console.error(err);
            DOM.leaveTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center;">Error loading leave history</td></tr>`;
        } finally {
            if (DOM.refreshLeaveHistoryBtn) {
                DOM.refreshLeaveHistoryBtn.innerHTML = originalText;
                DOM.refreshLeaveHistoryBtn.disabled = false;
            }
        }
    }

    // Initialize
    function init() {
        if (!DOM.previewLeaveBtn || !DOM.applyLeaveBtn) return;

        DOM.previewLeaveBtn.addEventListener('click', previewLeave);
        DOM.applyLeaveBtn.addEventListener('click', applyLeave);
        DOM.clearLeaveForm?.addEventListener('click', clearLeaveForm);
        DOM.refreshLeaveHistoryBtn?.addEventListener('click', loadLeaveHistory);

        loadLeaveHistory();
    }

    return { init };
})();

/* ============================
   EXPORT FUNCTIONALITY
============================ */

// Initialize export
function initializeExport() {
    if (!DOM.exportData) return;

    DOM.exportData.addEventListener('click', exportData);
}

// Export data
function exportData() {
    const format = DOM.exportFormat?.value || 'csv';
    const month = DOM.exportMonth?.value;
    const year = DOM.exportYear?.value || new Date().getFullYear().toString();

    // Show loading state
    const originalText = DOM.exportData.innerHTML;
    DOM.exportData.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exporting...';
    DOM.exportData.disabled = true;

    // Simulate export process
    setTimeout(() => {
        showNotification(`Data exported as ${format.toUpperCase()} for ${getMonthName(month)} ${year}`, 'success');

        // Restore button state
        DOM.exportData.innerHTML = originalText;
        DOM.exportData.disabled = false;
    }, 1500);
}

// Get month name from number
function getMonthName(monthNumber) {
    const months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return months[parseInt(monthNumber) - 1] || 'All Months';
}

/* ============================
   SYSTEM FUNCTIONALITY
============================ */

// Initialize system actions
function initializeSystemActions() {
    if (!DOM.resetSettings || !DOM.clearData) return;

    DOM.resetSettings.addEventListener('click', resetSystemSettings);
    DOM.clearData.addEventListener('click', clearAllData);
}

// Reset system settings
function resetSystemSettings() {
    if (!confirm('Are you sure you want to reset all settings to default values?')) {
        return;
    }

    // Show loading state
    const originalText = DOM.resetSettings.innerHTML;
    DOM.resetSettings.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Resetting...';
    DOM.resetSettings.disabled = true;

    // Simulate reset process
    setTimeout(() => {
        showNotification('All settings have been reset to default values', 'success');

        // Restore button state
        DOM.resetSettings.innerHTML = originalText;
        DOM.resetSettings.disabled = false;
    }, 1000);
}

// Clear all data
function clearAllData() {
    if (!confirm('WARNING: This will permanently delete all attendance and employee data. This action cannot be undone. Are you absolutely sure?')) {
        return;
    }

    // Show loading state
    const originalText = DOM.clearData.innerHTML;
    DOM.clearData.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Clearing...';
    DOM.clearData.disabled = true;

    // Simulate clear process
    setTimeout(() => {
        showNotification('All data has been permanently deleted', 'success');

        // Restore button state
        DOM.clearData.innerHTML = originalText;
        DOM.clearData.disabled = false;
    }, 2000);
}

/* ============================
   NOTIFICATION SYSTEM
============================ */

// Show notification
function showNotification(message, type = 'success') {
    // Remove existing notifications
    const existingNotif = document.querySelector('.custom-notification');
    if (existingNotif) existingNotif.remove();

    const notif = createElement(`
        <div class="custom-notification ${type}">
            <i class="fas fa-${type === 'success' ? 'check' : 'exclamation'}-circle"></i>
            <span>${message}</span>
        </div>
    `);

    document.body.appendChild(notif);

    // Animate in
    setTimeout(() => notif.classList.add('show'), 100);

    // Remove after delay
    setTimeout(() => {
        notif.classList.remove('show');
        setTimeout(() => notif.remove(), 300);
    }, 5000);
}

/* ============================
   MAIN INITIALIZATION
============================ */

// Main initialization function
function initializeEmployeesJS() {
    console.log('Initializing Employee Management System...');

    try {
        // Cache DOM elements
        cacheElements();

        // Initialize UI components
        initializeDatePickers();
        initializeSidebar();
        initializeTabs();
        initializeTableFilters();
        initializePagination();

        // Initialize feature modules
        initializeEmployeeOperations();
        initializeCompanyOffDays();
        initializeCompensation();
        initializeExport();
        initializeSystemActions();

        // Initialize Leave Management
        LeaveManagement.init();

        // Apply initial filters
        if (APP_STATE.tableRows.length > 0) {
            applyEmployeeFilters();
        }

        console.log('Employee Management System initialized successfully');
    } catch (error) {
        console.error('Error initializing Employee Management System:', error);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeEmployeesJS);
} else {
    initializeEmployeesJS();
}

// Export for debugging if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeEmployeesJS,
        applyEmployeeFilters,
        resetEmployeeFilters,
        handleEditEmployee,
        handleDeleteEmployee,
        deleteTempShift
    };
}