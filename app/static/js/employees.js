// =======================================
// EMPLOYEE MANAGEMENT JS 
// =======================================

// Global State for Settings
const settingsState = {
    currentTheme: localStorage.getItem('theme') || 'light',
    compensationData: {
        records: [],
        pendingLate: 0,
        pendingAbsent: 0,
        totalCompensated: 0
    },
    selectedEmployees: []
};

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 Employee Management System Started");
    initializeEmployeeSystem();
    initializeSettingsSystem();
    initializeCompensationSystem();
});

// Employee Management Functions
function initializeEmployeeSystem() {
    const employeeRows = document.querySelectorAll(".employee-row");
    const nameInput = document.getElementById("name");
    const phoneInput = document.getElementById("phone");
    const cnicInput = document.getElementById("cnic");
    const joiningDateInput = document.getElementById("joining_date");
    const statusInput = document.getElementById("status");
    const submitBtn = document.getElementById("submit-btn");

    employeeRows.forEach(row => {
        row.addEventListener("click", () => {
            const name = row.dataset.name;
            const phone = row.dataset.phone;
            const cnic = row.dataset.cnic;
            const joiningDate = row.dataset.joining;
            const status = row.dataset.status;

            nameInput.value = name;
            phoneInput.value = phone;
            cnicInput.value = cnic;
            joiningDateInput.value = joiningDate;
            statusInput.value = status;

            submitBtn.innerHTML = `<i class="fas fa-save"></i> Update Employee`;
            submitBtn.style.background = "linear-gradient(135deg, #48bb78, #38a169)";
        });
    });


    const resetBtn = document.getElementById("reset-btn");
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            submitBtn.innerHTML = `<i class="fas fa-plus"></i> Add Employee`;
            submitBtn.style.background = "linear-gradient(135deg, #667eea, #764ba2)";
        });
    }

    const rows = document.querySelectorAll("table tbody tr");
    rows.forEach((row, index) => {
        row.style.opacity = "0";
        row.style.transform = "translateY(10px)";
        setTimeout(() => {
            row.style.transition = "0.3s ease";
            row.style.opacity = "1";
            row.style.transform = "translateY(0)";
        }, 80 * index);
    });
}


function initializeSettingsSystem() {
    initializeThemeSystem();
    initializeSettingsTabs();
    loadSelectedEmployees();
}


function initializeThemeSystem() {
    document.documentElement.setAttribute('data-theme', settingsState.currentTheme);
    updateThemeIcon();
    
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
}

function initializeSettingsTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // Remove active class from all
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to current
            button.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// =======================================
// COMPENSATION SYSTEM - FULL UPDATED VERSION
// =======================================

document.addEventListener('DOMContentLoaded', () => {
    initializeCompensationSystem();
});

// =======================================
// Initialization
// =======================================
function initializeCompensationSystem() {
    setupCompensationEventListeners();
    loadEmployeeSuggestions();
    loadCompensationHistory();
    initializeDateFields();
    loadCompensationData();
    updateCompensationStats();
    renderSelectedEmployees();
}

// =======================================
// Compensation System - Complete JS
// =======================================

// =======================================
// Event Listeners Setup
// =======================================
function setupCompensationEventListeners() {
    // Apply Compensation Button
    const applyBtn = document.getElementById('applyCompensationBtn');
    if (applyBtn) applyBtn.addEventListener('click', applyCompensation);

    // Check Eligibility Button
    const checkEligibilityBtn = document.getElementById('checkEligibilityBtn');
    if (checkEligibilityBtn) checkEligibilityBtn.addEventListener('click', checkEligibility);

    // Clear Form Button
    const clearBtn = document.getElementById('clearCompensationForm');
    if (clearBtn) clearBtn.addEventListener('click', clearCompensationForm);

    // Refresh History Button
    const refreshBtn = document.getElementById('refreshHistoryBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', loadCompensationHistory);

    // Add manual employee button
    const addManualBtn = document.getElementById('addManualEmployee');
    if (addManualBtn) addManualBtn.addEventListener('click', addManualEmployee);

    // Enter key for manual input
    const manualInput = document.getElementById('manualEmployeeInput');
    if (manualInput) {
        manualInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') addManualEmployee();
        });
    }
}

// =======================================
// Date Fields Initialization
// =======================================
function initializeDateFields() {
    const today = new Date().toISOString().split('T')[0];
    const compensationDate = document.getElementById('compensationDate');
    if (compensationDate) compensationDate.value = today;

    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const violationDate = document.getElementById('violationDate');
    if (violationDate) violationDate.value = yesterday.toISOString().split('T')[0];
}

// =======================================
// Employee Suggestions
// =======================================
function loadEmployeeSuggestions() {
    fetch('/api/daily_search?limit=1000')
        .then(response => response.json())
        .then(data => {
            if (data.data && data.data.length > 0) {
                const uniqueNames = [...new Set(data.data.map(record => record.Name))].sort();
                const datalist = document.getElementById('employeeSuggestions');
                if (datalist) {
                    datalist.innerHTML = uniqueNames.map(name => `<option value="${name}">${name}</option>`).join('');
                }
            }
        })
        .catch(error => console.error('Error loading employee suggestions:', error));
}

// =======================================
// Eligibility Check
// =======================================
function checkEligibility() {
    const employee = document.getElementById('compensationEmployee').value.trim();
    const violationDate = document.getElementById('violationDate').value;
    const compensationDate = document.getElementById('compensationDate').value; // Fixed
    const compensationType = document.getElementById('compensationType').value;

    if (!employee || !violationDate || !compensationType || !compensationDate) {
        showCompensationResult('Please fill all required fields', 'error');
        return;
    }

    const eligibilityResult = document.getElementById('eligibilityResult');
    eligibilityResult.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking eligibility...';
    eligibilityResult.className = 'eligibility-result';
    eligibilityResult.style.display = 'block';

    fetch('/check_compensation_eligibility', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            employee_name: employee,
            violation_date: violationDate,
            compensation_date: compensationDate,
            compensation_type: compensationType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.eligible) {
            eligibilityResult.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message}`;
            eligibilityResult.className = 'eligibility-result eligible';
        } else {
            eligibilityResult.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
            eligibilityResult.className = 'eligibility-result not-eligible';
        }
    })
    .catch(error => {
        eligibilityResult.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error checking eligibility';
        eligibilityResult.className = 'eligibility-result not-eligible';
        console.error('Eligibility check error:', error);
    });
}

// =======================================
// Apply Compensation
// =======================================
function applyCompensation() {
    const employee = document.getElementById('compensationEmployee').value.trim();
    const violationDate = document.getElementById('violationDate').value;
    const compensationDate = document.getElementById('compensationDate').value;
    const compensationType = document.getElementById('compensationType').value;

    if (!employee || !violationDate || !compensationDate || !compensationType) {
        showCompensationResult('Please fill all required fields', 'error');
        return;
    }

    const applyBtn = document.getElementById('applyCompensationBtn');
    const originalText = applyBtn.innerHTML;
    applyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
    applyBtn.disabled = true;

    fetch('/apply_compensation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            employee_name: employee,
            violation_date: violationDate,
            compensation_date: compensationDate,
            compensation_type: compensationType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showCompensationResult(data.message, 'success');
            clearCompensationForm();
            loadCompensationHistory();
        } else {
            showCompensationResult(data.message, 'error');
        }
    })
    .catch(error => {
        showCompensationResult('Error applying compensation', 'error');
        console.error('Compensation application error:', error);
    })
    .finally(() => {
        applyBtn.innerHTML = originalText;
        applyBtn.disabled = false;
    });
}

// =======================================
// Show Result Messages
// =======================================
function showCompensationResult(message, type) {
    const resultDiv = document.getElementById('compensationResult');
    if (resultDiv) {
        resultDiv.innerHTML = message;
        resultDiv.className = `result-message ${type}`;
        resultDiv.style.display = 'block';
        setTimeout(() => resultDiv.style.display = 'none', 5000);
    }
}

// =======================================
// Clear Form
// =======================================
function clearCompensationForm() {
    document.getElementById('compensationEmployee').value = '';
    document.getElementById('violationDate').value = '';
    document.getElementById('compensationDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('compensationType').value = 'By Late';
    document.getElementById('eligibilityResult').style.display = 'none';
    document.getElementById('compensationResult').style.display = 'none';
}

// =======================================
// Compensation History
// =======================================
function loadCompensationHistory() {
    const historyList = document.getElementById('compensationHistoryList');
    if (!historyList) return;

    historyList.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>Loading history...</p></div>';

    fetch('/api/compensation_history')
        .then(response => response.json())
        .then(data => {
            if (data.history && data.history.length > 0) {
                renderCompensationHistory(data.history);
            } else {
                historyList.innerHTML = `<div class="empty-state"><i class="fas fa-history"></i><p>No compensation records yet</p></div>`;
            }
        })
        .catch(error => {
            console.error('Error loading compensation history:', error);
            historyList.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>Error loading history</p></div>`;
        });
}

function renderCompensationHistory(history) {
    const historyList = document.getElementById('compensationHistoryList');
    if (!historyList) return;

    historyList.innerHTML = history.map(record => `
        <div class="compensation-record">
            <div class="record-info">
                <div class="record-employee">${record.employee_name}</div>
                <div class="record-details">
                    <span class="compensation-badge badge-${record.compensation_type.toLowerCase().replace(' ', '')}">
                        ${record.compensation_type}
                    </span>
                    • Violation: ${record.violation_date} 
                    • Compensated: ${record.compensated_date}
                    <br>
                    <small>Original Status: ${record.original_status} • OT: ${record.overtime}h</small>
                </div>
            </div>
            <div class="record-meta">
                <div class="record-date">${record.violation_date}</div>
            </div>
        </div>
    `).join('');
}

// =======================================
// Placeholder Functions
// =======================================
function loadCompensationData() { /* implement your data loading */ }
function updateCompensationStats() { /* implement stats calculation */ }
function renderSelectedEmployees() { /* implement render selected employees */ }
function addManualEmployee() { /* implement add manual employee */ }

// =======================================
// Initialize All
// =======================================
document.addEventListener('DOMContentLoaded', () => {
    setupCompensationEventListeners();
    initializeDateFields();
    loadEmployeeSuggestions();
    loadCompensationHistory();
    loadCompensationData();
    updateCompensationStats();
    renderSelectedEmployees();
});

// Manual Employee Functions
function addManualEmployee() {
    const manualInput = document.getElementById('manualEmployeeInput');
    const inputValue = manualInput.value.trim();
    
    if (!inputValue) {
        showToast('❌ Please enter employee ID or name', 'warning');
        return;
    }
    
    // Check if employee already exists in selected employees
    const existingEmployee = settingsState.selectedEmployees.find(emp => 
        emp.id === inputValue || emp.name.toLowerCase() === inputValue.toLowerCase()
    );
    
    if (existingEmployee) {
        showToast(`ℹ️ ${existingEmployee.name} is already selected`, 'info');
        manualInput.value = '';
        return;
    }
    
    // Add new temporary employee
    const newEmployee = {
        id: `TEMP_${Date.now()}`,
        name: inputValue,
        department: 'Manual Entry'
    };
    
    settingsState.selectedEmployees.push(newEmployee);
    showToast(`✅ ${inputValue} added manually`, 'success');
    
    manualInput.value = '';
    renderSelectedEmployees();
    saveSelectedEmployees();
}

function removeSelectedEmployee(employeeId) {
    settingsState.selectedEmployees = settingsState.selectedEmployees.filter(emp => emp.id !== employeeId);
    renderSelectedEmployees();
    saveSelectedEmployees();
    showToast('✅ Employee removed from selection', 'success');
}

function renderSelectedEmployees() {
    const selectedContainer = document.getElementById('selectedEmployees');
    if (!selectedContainer) return;
    
    if (settingsState.selectedEmployees.length === 0) {
        selectedContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-user-check"></i>
                <p>No employees selected</p>
            </div>
        `;
        return;
    }
    
    selectedContainer.innerHTML = settingsState.selectedEmployees.map(employee => `
        <div class="selected-employee-tag">
            <span>${employee.name} (${employee.id})</span>
            <button type="button" class="remove-employee" onclick="removeSelectedEmployee('${employee.id}')">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `).join('');
}
// Company Day Off Functions
function initializeCompanyDayOffSystem() {
    loadCompanyOffDays();
    setupCompanyDayOffEventListeners();
}

function setupCompanyDayOffEventListeners() {
    // Add Company Day Off
    const addBtn = document.getElementById('addCompanyOffDay');
    if (addBtn) {
        addBtn.addEventListener('click', addCompanyDayOff);
    }
    
    // Remove Company Day Off
    const removeBtn = document.getElementById('removeCompanyOffDay');
    if (removeBtn) {
        removeBtn.addEventListener('click', removeCompanyDayOff);
    }
    
    // Set today's date as default
    const dateInput = document.getElementById('companyOffDate');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
    }
}

function loadCompanyOffDays() {
    // Load company off days for dropdown and list
    fetch('/api/company_off_days?start_date=2023-01-01')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                populateCompanyOffDropdown(data.off_days);
                renderCompanyOffDaysList(data.off_days);
            }
        })
        .catch(error => {
            console.error('Error loading company off days:', error);
        });
}

function populateCompanyOffDropdown(offDays) {
    const dropdown = document.getElementById('removeCompanyOffDate');
    if (!dropdown) return;
    
    // Clear existing options except the first one
    dropdown.innerHTML = '<option value="">Select date to remove</option>';
    
    offDays.forEach(day => {
        const option = document.createElement('option');
        option.value = day.date;
        option.textContent = `${day.date} - ${day.reason}`;
        dropdown.appendChild(option);
    });
}

function renderCompanyOffDaysList(offDays) {
    const listContainer = document.getElementById('companyOffDaysList');
    if (!listContainer) return;
    
    if (offDays.length === 0) {
        listContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-calendar-times"></i>
                <p>No company days off scheduled</p>
            </div>
        `;
        return;
    }
    
    listContainer.innerHTML = offDays.map(day => `
        <div class="company-off-day-item">
            <div class="company-off-day-info">
                <i class="fas fa-calendar-day"></i>
                <div>
                    <strong>${day.date}</strong>
                    <p>${day.reason || 'Company Day Off'}</p>
                    <small>Added: ${day.created_at}</small>
                </div>
            </div>
            <button class="btn btn-sm btn-outline" onclick="removeCompanyDayOffByDate('${day.date}')">
                <i class="fas fa-trash"></i> Remove
            </button>
        </div>
    `).join('');
}
//=========================
// COMPANY DAY OFF
//==========================
function addCompanyDayOff() {
    const dateInput = document.getElementById('companyOffDate');
    const reasonInput = document.getElementById('companyOffReason');
    
    const date = dateInput.value;
    const reason = reasonInput.value.trim() || 'Company Day Off';
    
    if (!date) {
        showToast('❌ Please select a date', 'error');
        return;
    }
    
    // Show loading
    const addBtn = document.getElementById('addCompanyOffDay');
    const originalText = addBtn.innerHTML;
    addBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    addBtn.disabled = true;
    
    // Send request
    fetch('/company_day_off', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            action: 'add',
            date: date,
            reason: reason
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
            // Clear form
            dateInput.value = new Date().toISOString().split('T')[0];
            reasonInput.value = '';
            // Reload lists
            loadCompanyOffDays();
        } else {
            showToast(`❌ ${data.message}`, 'error');
        }
    })
    .catch(error => {
        showToast('❌ Error adding company day off', 'error');
        console.error('Error:', error);
    })
    .finally(() => {
        // Restore button
        addBtn.innerHTML = originalText;
        addBtn.disabled = false;
    });
}

function removeCompanyDayOff() {
    const dropdown = document.getElementById('removeCompanyOffDate');
    const selectedDate = dropdown.value;
    
    if (!selectedDate) {
        showToast('❌ Please select a date to remove', 'error');
        return;
    }
    
    if (!confirm(`Are you sure you want to remove Company Day Off status from ${selectedDate}?`)) {
        return;
    }
    
    // Show loading
    const removeBtn = document.getElementById('removeCompanyOffDay');
    const originalText = removeBtn.innerHTML;
    removeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing...';
    removeBtn.disabled = true;
    
    // Send request
    fetch('/company_day_off', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            action: 'remove',
            date: selectedDate
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
            // Reset dropdown
            dropdown.value = '';
            // Reload lists
            loadCompanyOffDays();
        } else {
            showToast(`❌ ${data.message}`, 'error');
        }
    })
    .catch(error => {
        showToast('❌ Error removing company day off', 'error');
        console.error('Error:', error);
    })
    .finally(() => {
        // Restore button
        removeBtn.innerHTML = originalText;
        removeBtn.disabled = false;
    });
}

function removeCompanyDayOffByDate(date) {
    if (!confirm(`Are you sure you want to remove Company Day Off status from ${date}?`)) {
        return;
    }
    
    // Set dropdown value and trigger removal
    const dropdown = document.getElementById('removeCompanyOffDate');
    dropdown.value = date;
    removeCompanyDayOff();
}
        document.addEventListener('DOMContentLoaded', function() {
            const sidebar = document.getElementById('sidebar');
            const mainContent = document.getElementById('mainContent');
            
            // Set today's date as default for effective date
            const effectiveDateInput = document.getElementById('effective_date');
            if (effectiveDateInput && !effectiveDateInput.value) {
                const today = new Date().toISOString().split('T')[0];
                effectiveDateInput.value = today;
            }

            // Set joining date to today if empty
            const joiningDateInput = document.getElementById('joining_date');
            if (joiningDateInput && !joiningDateInput.value) {
                const today = new Date().toISOString().split('T')[0];
                joiningDateInput.value = today;
            }

            // Tab switching functionality - Added from Code B
            const tabBtns = document.querySelectorAll('.tab-btn');
            const tabContents = document.querySelectorAll('.tab-content');
            
            tabBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    // Remove active class from all buttons and contents
                    tabBtns.forEach(b => b.classList.remove('active'));
                    tabContents.forEach(c => c.classList.remove('active'));
                    
                    // Add active class to clicked button
                    btn.classList.add('active');
                    
                    // Show corresponding content
                    const tabId = btn.getAttribute('data-tab');
                    document.getElementById(tabId).classList.add('active');
                });
            });

            // Initialize the employee management functionality
            initEmployeeManagement();
        });

        function initEmployeeManagement() {
            // DOM Elements
            const elements = {
                employeeForm: document.getElementById('employeeForm'),
                employeeSearch: document.getElementById('employeeSearch'),
                departmentFilter: document.getElementById('departmentFilter'),
                clearFilters: document.getElementById('clearFilters'),
                employeesTable: document.getElementById('employeesTable'),
                tableBody: document.querySelector('#employeesTable tbody'),
                prevPage: document.getElementById('prevPage'),
                nextPage: document.getElementById('nextPage'),
                pageInfo: document.getElementById('pageInfo'),
                showingCount: document.getElementById('showingCount'),
                totalCount: document.getElementById('totalCount'),
                addEmployeeBtn: document.getElementById('addEmployeeBtn'),
                exportEmployeesBtn: document.getElementById('exportEmployeesBtn'),
                cancelEditBtn: document.getElementById('cancelEditBtn'),
                deleteModal: document.getElementById('deleteModal'),
                cancelDelete: document.getElementById('cancelDelete'),
                confirmDelete: document.getElementById('confirmDelete'),
                deleteEmployeeName: document.getElementById('deleteEmployeeName')
            };

            // State
            const state = {
                currentPage: 1,
                itemsPerPage: 10,
                filteredEmployees: [],
                searchTerm: '',
                departmentFilter: '',
                employeeToDelete: null
            };

            // Initialize
            function init() {
                bindEvents();
                updateTable();
                populateDepartmentFilter();
            }

            // Event Binding
            function bindEvents() {
                // Search and Filter
                elements.employeeSearch.addEventListener('input', handleSearch);
                elements.departmentFilter.addEventListener('change', handleDepartmentFilter);
                elements.clearFilters.addEventListener('click', clearFilters);

                // Pagination
                elements.prevPage.addEventListener('click', goToPrevPage);
                elements.nextPage.addEventListener('click', goToNextPage);

                // Form Actions
                if (elements.addEmployeeBtn) {
                    elements.addEmployeeBtn.addEventListener('click', scrollToForm);
                }

                if (elements.exportEmployeesBtn) {
                    elements.exportEmployeesBtn.addEventListener('click', exportToExcel);
                }

                if (elements.cancelEditBtn) {
                    elements.cancelEditBtn.addEventListener('click', cancelEdit);
                }

                // Delete Modal
                elements.cancelDelete.addEventListener('click', closeDeleteModal);
                elements.confirmDelete.addEventListener('click', confirmDeleteEmployee);

                // Close modal when clicking outside
                elements.deleteModal.addEventListener('click', function(e) {
                    if (e.target === elements.deleteModal) {
                        closeDeleteModal();
                    }
                });

                // Edit and Delete buttons (delegated)
                elements.tableBody.addEventListener('click', handleTableActions);

                // Tab switching - Added for settings tabs
                const tabBtns = document.querySelectorAll('.tab-btn');
                tabBtns.forEach(btn => {
                    btn.addEventListener('click', () => {
                        const tabId = btn.getAttribute('data-tab');
                        // You can add additional logic for tab-specific actions here
                    });
                });
            }

            // Table Actions Handler
            function handleTableActions(e) {
                const target = e.target.closest('.btn-edit, .btn-delete');
                if (!target) return;

                const row = target.closest('tr');
                const employeeId = target.dataset.id;
                const employeeName = target.dataset.name;

                if (target.classList.contains('btn-edit')) {
                    editEmployee(employeeId, employeeName);
                } else if (target.classList.contains('btn-delete')) {
                    showDeleteModal(employeeId, employeeName);
                }
            }

            // Search Handler
            function handleSearch(e) {
                state.searchTerm = e.target.value.toLowerCase();
                state.currentPage = 1;
                updateTable();
            }

            // Department Filter Handler
            function handleDepartmentFilter(e) {
                state.departmentFilter = e.target.value;
                state.currentPage = 1;
                updateTable();
            }

            // Clear Filters
            function clearFilters() {
                elements.employeeSearch.value = '';
                elements.departmentFilter.value = '';
                state.searchTerm = '';
                state.departmentFilter = '';
                state.currentPage = 1;
                updateTable();
            }

            // Pagination
            function goToPrevPage() {
                if (state.currentPage > 1) {
                    state.currentPage--;
                    updateTable();
                }
            }

            function goToNextPage() {
                const totalPages = Math.ceil(state.filteredEmployees.length / state.itemsPerPage);
                if (state.currentPage < totalPages) {
                    state.currentPage++;
                    updateTable();
                }
            }

            // Update Table
            function updateTable() {
                const allRows = Array.from(elements.tableBody.querySelectorAll('tr:not(.empty-state)'));
                
                // Filter employees
                state.filteredEmployees = allRows.filter(row => {
                    const name = row.dataset.name.toLowerCase();
                    const department = row.dataset.department.toLowerCase();
                    
                    const matchesSearch = !state.searchTerm || 
                        name.includes(state.searchTerm) || 
                        department.includes(state.searchTerm);
                    
                    const matchesDepartment = !state.departmentFilter || 
                        department.includes(state.departmentFilter.toLowerCase());
                    
                    return matchesSearch && matchesDepartment;
                });

                // Hide all rows first
                allRows.forEach(row => row.style.display = 'none');

                // Show filtered rows with pagination
                const startIndex = (state.currentPage - 1) * state.itemsPerPage;
                const endIndex = startIndex + state.itemsPerPage;
                const employeesToShow = state.filteredEmployees.slice(startIndex, endIndex);

                employeesToShow.forEach(row => row.style.display = '');

                // Update pagination controls
                updatePagination();

                // Show empty state if no results
                const emptyState = elements.tableBody.querySelector('.empty-state');
                if (emptyState) {
                    emptyState.style.display = state.filteredEmployees.length === 0 ? '' : 'none';
                }
            }

            // Update Pagination
            function updatePagination() {
                const totalEmployees = state.filteredEmployees.length;
                const totalPages = Math.ceil(totalEmployees / state.itemsPerPage);
                const startCount = totalEmployees === 0 ? 0 : (state.currentPage - 1) * state.itemsPerPage + 1;
                const endCount = Math.min(state.currentPage * state.itemsPerPage, totalEmployees);

                // Update counts
                elements.showingCount.textContent = `${startCount}-${endCount}`;
                elements.totalCount.textContent = totalEmployees;

                // Update page info
                elements.pageInfo.textContent = `Page ${state.currentPage} of ${totalPages || 1}`;

                // Update button states
                elements.prevPage.disabled = state.currentPage === 1;
                elements.nextPage.disabled = state.currentPage === totalPages || totalPages === 0;
            }

            // Populate Department Filter
            function populateDepartmentFilter() {
                const departments = new Set();
                const rows = elements.tableBody.querySelectorAll('tr:not(.empty-state)');
                
                rows.forEach(row => {
                    const department = row.dataset.department;
                    if (department) {
                        departments.add(department);
                    }
                });

                // Departments are already in the HTML, no need to populate dynamically
            }

            // Scroll to Form
            function scrollToForm() {
                document.getElementById('employeeFormSection').scrollIntoView({ 
                    behavior: 'smooth' 
                });
            }

            // Export to Excel
            function exportToExcel() {
                // Simple CSV export implementation
                const headers = ['Name', 'Employee ID', 'Joining Date', 'Department', 'Shift', 'Role', 'Effective From'];
                const rows = state.filteredEmployees.map(row => {
                    const cells = row.querySelectorAll('td');
                    return [
                        cells[1].textContent.trim(),
                        cells[0].textContent.trim(),
                        cells[2].textContent.trim(),
                        cells[3].textContent.trim(),
                        cells[4].textContent.trim(),
                        cells[5].textContent.trim(),
                        cells[6].textContent.trim()
                    ];
                });

                const csvContent = [headers, ...rows]
                    .map(row => row.map(cell => `"${cell}"`).join(','))
                    .join('\n');

                const blob = new Blob([csvContent], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `employees_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }

            // Edit Employee
            function editEmployee(employeeId, employeeName) {
                // This would typically involve fetching employee data and populating the form
                // For now, we'll just scroll to the form
                scrollToForm();
                
                // Show notification
                showNotification(`Ready to edit ${employeeName}`, 'success');
            }

            // Cancel Edit
            function cancelEdit() {
                // Reset form and redirect to regular add mode
                window.location.href = "{{ url_for('main.employees') }}";
            }

            // Delete Employee Modal
            function showDeleteModal(employeeId, employeeName) {
                state.employeeToDelete = { id: employeeId, name: employeeName };
                elements.deleteEmployeeName.textContent = employeeName;
                elements.deleteModal.style.display = 'flex';
            }

            function closeDeleteModal() {
                elements.deleteModal.style.display = 'none';
                state.employeeToDelete = null;
            }

            function confirmDeleteEmployee() {
                if (state.employeeToDelete) {
                    // In a real implementation, you would send a DELETE request to the server
                    console.log('Deleting employee:', state.employeeToDelete);
                    
                    // For now, just show a notification
                    showNotification(`Employee ${state.employeeToDelete.name} deleted successfully`, 'success');
                    
                    closeDeleteModal();
                    
                    // Reload the page to reflect changes
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                }
            }

            // Notification System
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
                }, 3000);
            }

            // Initialize the application
            init();
        }
// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // ... existing initialization code ...
    
    // Initialize Company Day Off system
    initializeCompanyDayOffSystem();
});
// Data Management Functions
function loadCompensationData() {
    try {
        const savedData = localStorage.getItem('compensationData');
        if (savedData) {
            settingsState.compensationData = { ...settingsState.compensationData, ...JSON.parse(savedData) };
        }
    } catch (error) {
        console.error('Error loading compensation data:', error);
    }
}

function saveCompensationData() {
    try {
        localStorage.setItem('compensationData', JSON.stringify(settingsState.compensationData));
    } catch (error) {
        console.error('Error saving compensation data:', error);
    }
}

function loadSelectedEmployees() {
    try {
        const savedSelected = localStorage.getItem('selectedEmployees');
        if (savedSelected) {
            settingsState.selectedEmployees = JSON.parse(savedSelected);
        }
    } catch (error) {
        console.error('Error loading selected employees:', error);
    }
}

function saveSelectedEmployees() {
    try {
        localStorage.setItem('selectedEmployees', JSON.stringify(settingsState.selectedEmployees));
    } catch (error) {
        console.error('Error saving selected employees:', error);
    }
}

function updateCompensationStats() {
    // Calculate stats from records
    const pendingLate = settingsState.compensationData.records.filter(r => r.type === 'late').length;
    const pendingAbsent = settingsState.compensationData.records.filter(r => r.type === 'absent').length;
    const totalCompensated = settingsState.compensationData.records.length;
    
    // Update UI
    updateElementText('pendingLateCount', pendingLate);
    updateElementText('pendingAbsentCount', pendingAbsent);
    updateElementText('totalCompensatedCount', totalCompensated);
    
    // Update state
    settingsState.compensationData.pendingLate = pendingLate;
    settingsState.compensationData.pendingAbsent = pendingAbsent;
    settingsState.compensationData.totalCompensated = totalCompensated;
}

// Utility Functions
function updateElementText(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) element.textContent = value;
}

// Toast System
function showToast(message, type = 'info') {
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.style.cssText = `
            position: fixed;
            top: 20px;  
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 10px;
        `;
        document.body.appendChild(toastContainer);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        padding: 12px 20px;
        background: ${getToastColor(type)};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transform: translateX(400px);
        opacity: 0;
        transition: all 0.3s ease;
        max-width: 300px;
        word-wrap: break-word;
    `;
    
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    }, 100);
    
    setTimeout(() => {
        toast.style.transform = 'translateX(400px)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function getToastColor(type) {
    const colors = {
        success: '#28a745',
        error: '#dc3545',
        warning: '#ffc107',
        info: '#4361ee'
    };
    return colors[type] || colors.info;
}

// Validation Functions
function validateCNIC(input) {
    let clean = input.value.replace(/[^\d]/g, '');
    if (clean.length > 13) clean = clean.slice(0, 13);

    if (clean.length === 13) {
        input.value = `${clean.slice(0,5)}-${clean.slice(5,12)}-${clean.slice(12)}`;
    } else {
        input.value = clean;
    }
}

function validatePhone(input) {
    input.value = input.value.replace(/[^\d]/g, '');
    if (input.value.length > 11) input.value = input.value.slice(0, 11);
}

// Confirm before deleting
function confirmDelete(name) {
    return confirm(`Are you sure you want to delete employee: ${name}?`);
}

// Make functions globally available
window.validateCNIC = validateCNIC;
window.validatePhone = validatePhone;
window.confirmDelete = confirmDelete;
window.removeSelectedEmployee = removeSelectedEmployee;
window.addManualEmployee = addManualEmployee;
window.applyCompensation = applyCompensation;
window.toggleTheme = toggleTheme;
window.checkEligibility = checkEligibility;
window.clearCompensationForm = clearCompensationForm;
window.loadCompensationHistory = loadCompensationHistory;