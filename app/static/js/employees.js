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
    initializeDatePickers(); // Add date picker initialization
});

// =======================================
// DATE PICKER INITIALIZATION
// =======================================
function initializeDatePickers() {
    console.log("📅 Initializing date pickers...");
    
    // Initialize date pickers with max date limit (today)
    const datePickers = document.querySelectorAll('.date-picker');
    datePickers.forEach(picker => {
        flatpickr(picker, {
            dateFormat: "Y-m-d",
            allowInput: true,
            maxDate: "today",
            defaultDate: picker.value || "today"
        });
    });

    // Initialize date picker for company off days WITHOUT max date limit
    const companyOffDatePicker = document.getElementById('companyOffDate');
    if (companyOffDatePicker) {
        flatpickr(companyOffDatePicker, {
            dateFormat: "Y-m-d",
            allowInput: true,
            // No maxDate restriction for company off days
            defaultDate: "today"
        });
    }

    // Handle the compensation form date pickers
    const violationDate = document.getElementById('violationDate');
    const compensationDate = document.getElementById('compensationDate');
    
    if (violationDate) {
        flatpickr(violationDate, {
            dateFormat: "Y-m-d",
            allowInput: true,
            maxDate: "today",
            defaultDate: violationDate.value || "today"
        });
    }
    
    if (compensationDate) {
        flatpickr(compensationDate, {
            dateFormat: "Y-m-d",
            allowInput: true,
            maxDate: "today",
            defaultDate: compensationDate.value || "today"
        });
    }

    // Handle the add employee form date picker
    const employeeJoinDate = document.getElementById('employeeJoinDate');
    if (employeeJoinDate) {
        flatpickr(employeeJoinDate, {
            dateFormat: "Y-m-d",
            allowInput: true,
            maxDate: "today",
            defaultDate: employeeJoinDate.value || "today"
        });
    }

    // Initialize joining_date picker with specific settings
    const joiningDatePicker = document.getElementById('joining_date');
    if (joiningDatePicker) {
        flatpickr(joiningDatePicker, {
            dateFormat: "Y-m-d",
            allowInput: true,
            maxDate: "today",
            defaultDate: joiningDatePicker.value || "today"
        });
    }

    // Initialize effective_date picker with specific settings
    const effectiveDatePicker = document.getElementById('effective_date');
    if (effectiveDatePicker) {
        flatpickr(effectiveDatePicker, {
            dateFormat: "Y-m-d",
            allowInput: true,
            maxDate: "today",
            defaultDate: effectiveDatePicker.value || "today"
        });
    }
}

// =======================================
// EMPLOYEE MANAGEMENT FUNCTIONS
// =======================================
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

// =======================================
// SETTINGS SYSTEM
// =======================================
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

function toggleTheme() {
    settingsState.currentTheme = settingsState.currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', settingsState.currentTheme);
    localStorage.setItem('theme', settingsState.currentTheme);
    updateThemeIcon();
}

function updateThemeIcon() {
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        const icon = themeToggle.querySelector('i');
        if (icon) {
            icon.className = settingsState.currentTheme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
        }
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
// COMPENSATION SYSTEM
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

function setupCompensationEventListeners() {
    // Apply Compensation Button
    const applyBtn = document.getElementById('applyCompensationBtn');
    if (applyBtn) applyBtn.addEventListener('click', applyCompensation);

    // Remove Compensation Button
    const removeBtn = document.getElementById('removeCompensationBtn');
    if (removeBtn) removeBtn.addEventListener('click', removeCompensation);

    // Check Eligibility Button
    const checkEligibilityBtn = document.getElementById('checkEligibilityBtn');
    if (checkEligibilityBtn) checkEligibilityBtn.addEventListener('click', checkEligibility);

    // Clear Form Button
    const clearBtn = document.getElementById('clearCompensationForm');
    if (clearBtn) clearBtn.addEventListener('click', clearCompensationForm);

    // Refresh History Button
    const refreshBtn = document.getElementById('refreshHistoryBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', loadCompensationHistory);

    // Enter key for employee input
    const employeeInput = document.getElementById('compensationEmployee');
    if (employeeInput) {
        employeeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') checkEligibility();
        });
    }
}

function initializeDateFields() {
    const today = new Date().toISOString().split('T')[0];
    const compensationDate = document.getElementById('compensationDate');
    if (compensationDate) compensationDate.value = today;

    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const violationDate = document.getElementById('violationDate');
    if (violationDate) violationDate.value = yesterday.toISOString().split('T')[0];
}

function loadEmployeeSuggestions() {
    fetch('/api/daily_search?limit=1000')
        .then(res => res.json())
        .then(data => {
            if (data.data && data.data.length) {
                const uniqueNames = [...new Set(data.data.map(r => r.Name))].sort();
                const datalist = document.getElementById('employeeSuggestions');
                if (datalist) datalist.innerHTML = uniqueNames.map(name => `<option value="${name}">${name}</option>`).join('');
            }
        })
        .catch(err => console.error('Error loading employee suggestions:', err));
}

function checkEligibility() {
    const employee = document.getElementById('compensationEmployee').value.trim();
    const violationDate = document.getElementById('violationDate').value;
    const compensationDate = document.getElementById('compensationDate').value;
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
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            employee_name: employee,
            violation_date: violationDate,
            compensation_date: compensationDate,
            compensation_type: compensationType
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.eligible) {
            eligibilityResult.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message}`;
            eligibilityResult.className = 'eligibility-result eligible';
        } else {
            eligibilityResult.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
            eligibilityResult.className = 'eligibility-result not-eligible';
        }
    })
    .catch(err => {
        eligibilityResult.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error checking eligibility';
        eligibilityResult.className = 'eligibility-result not-eligible';
        console.error('Eligibility check error:', err);
    });
}

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
    const removeBtn = document.getElementById('removeCompensationBtn');
    const originalText = applyBtn.innerHTML;

    applyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
    applyBtn.disabled = true;
    removeBtn.disabled = true;

    fetch('/apply_compensation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            employee_name: employee,
            violation_date: violationDate,
            compensation_date: compensationDate,
            compensation_type: compensationType
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showCompensationResult(data.message, 'success');
            clearCompensationForm();
            loadCompensationHistory();
        } else {
            showCompensationResult(data.message, 'error');
        }
    })
    .catch(err => {
        showCompensationResult('Error applying compensation', 'error');
        console.error('Compensation apply error:', err);
    })
    .finally(() => {
        applyBtn.innerHTML = originalText;
        applyBtn.disabled = false;
        removeBtn.disabled = false;
    });
}

function removeCompensation() {
    const employee = document.getElementById('compensationEmployee').value.trim();
    const violationDate = document.getElementById('violationDate').value;

    if (!employee || !violationDate) {
        showCompensationResult('Select employee and violation date to remove compensation', 'error');
        return;
    }

    if (!confirm(`Are you sure you want to remove compensation for ${employee} on ${violationDate}?`)) return;

    const removeBtn = document.getElementById('removeCompensationBtn');
    const originalText = removeBtn.innerHTML;

    removeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing...';
    removeBtn.disabled = true;

    fetch('/remove_compensation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            employee_name: employee,
            violation_date: violationDate
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showCompensationResult(data.message, 'success');
            clearCompensationForm();
            loadCompensationHistory();
        } else {
            showCompensationResult(data.message, 'error');
        }
    })
    .catch(err => {
        showCompensationResult('Error removing compensation', 'error');
        console.error('Remove compensation error:', err);
    })
    .finally(() => {
        removeBtn.innerHTML = originalText;
        removeBtn.disabled = false;
    });
}

function showCompensationResult(message, type) {
    const resultDiv = document.getElementById('compensationResult');
    if (resultDiv) {
        resultDiv.innerHTML = message;
        resultDiv.className = `result-message ${type}`;
        resultDiv.style.display = 'block';
        setTimeout(() => resultDiv.style.display = 'none', 5000);
    }
}

function clearCompensationForm() {
    document.getElementById('compensationEmployee').value = '';
    document.getElementById('violationDate').value = '';
    document.getElementById('compensationDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('compensationType').value = 'By Late';
    document.getElementById('eligibilityResult').style.display = 'none';
    document.getElementById('compensationResult').style.display = 'none';
}

function loadCompensationHistory() {
    const historyList = document.getElementById('compensationHistoryList');
    if (!historyList) return;

    historyList.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>Loading history...</p></div>';

    fetch('/api/compensation_history')
        .then(res => res.json())
        .then(data => {
            if (data.history && data.history.length) {
                renderCompensationHistory(data.history);
            } else {
                historyList.innerHTML = '<div class="empty-state"><i class="fas fa-history"></i><p>No compensation records yet</p></div>';
            }
        })
        .catch(err => {
            console.error('Error loading compensation history:', err);
            historyList.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>Error loading history</p></div>';
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
                    </span> • Violation: ${record.violation_date} • Compensated: ${record.compensated_date}
                    <br><small>Status: ${record.original_status} • OT: ${record.overtime}h</small>
                </div>
            </div>
            <div class="record-date">${record.violation_date}</div>
        </div>
    `).join('');
}

// =======================================
// MANUAL EMPLOYEE FUNCTIONS
// =======================================
function addManualEmployee() {
    const manualInput = document.getElementById('manualEmployeeInput');
    const inputValue = manualInput.value.trim();
    
    if (!inputValue) {
        showToast('❌ Please enter employee ID or name', 'warning');
        return;
    }
    
    const existingEmployee = settingsState.selectedEmployees.find(emp => 
        emp.id === inputValue || emp.name.toLowerCase() === inputValue.toLowerCase()
    );
    
    if (existingEmployee) {
        showToast(`ℹ️ ${existingEmployee.name} is already selected`, 'info');
        manualInput.value = '';
        return;
    }
    
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

// =======================================
// COMPANY DAY OFF FUNCTIONS - ENHANCED
// =======================================
function initializeCompanyDayOffSystem() {
    loadCompanyOffDays();
    setupCompanyDayOffEventListeners();
}

function setupCompanyDayOffEventListeners() {
    const addBtn = document.getElementById('addCompanyOffDay');
    if (addBtn) addBtn.addEventListener('click', addCompanyDayOff);

    const removeBtn = document.getElementById('removeCompanyOffDay');
    if (removeBtn) removeBtn.addEventListener('click', removeCompanyDayOff);

    const dateInput = document.getElementById('companyOffDate');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
    }
}

// Fetch and render company off days
function loadCompanyOffDays() {
    fetch('/api/company_off_days?start_date=2023-01-01')
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                populateCompanyOffDropdown(data.off_days);
                renderCompanyOffDaysList(data.off_days);
            }
        })
        .catch(err => console.error('Error loading company off days:', err));
}

// Populate dropdown for removal
function populateCompanyOffDropdown(offDays) {
    const dropdown = document.getElementById('removeCompanyOffDate');
    if (!dropdown) return;

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

    // Empty state
    if (!offDays || offDays.length === 0) {
        listContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-calendar-times"></i>
                <p>No company days off scheduled</p>
            </div>
        `;
        return;
    }

    // Render each company day off in table-style row
    listContainer.innerHTML = offDays.map(day => `
        <div class="company-off-day-item">
            <div class="company-off-day-info">
                <span class="off-day-reason">${day.reason || 'Company Day Off'}</span>
                <span class="off-day-date">${day.date}</span>
                <span class="off-day-added">Added: ${day.created_at}</span>
            </div>
        </div>
    `).join('');

    // Optional: highlight today or upcoming dates
    const today = new Date().toISOString().split('T')[0];
    offDays.forEach((day, index) => {
        if (day.date === today) {
            const row = listContainer.children[index];
            if (row) {
                row.style.backgroundColor = 'rgba(99, 102, 241, 0.1)'; // light purple
                row.style.borderColor = '#6366f1';
            }
        }
    });
}


// Add a company day off
function addCompanyDayOff() {
    const dateInput = document.getElementById('companyOffDate');
    const reasonInput = document.getElementById('companyOffReason');

    const date = dateInput.value;
    const reason = reasonInput.value.trim() || 'Company Day Off';

    if (!date) {
        showToast('❌ Please select a date', 'error');
        return;
    }

    const addBtn = document.getElementById('addCompanyOffDay');
    const originalText = addBtn.innerHTML;
    addBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    addBtn.disabled = true;

    fetch('/company_day_off', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ action: 'add', date, reason })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
            dateInput.value = new Date().toISOString().split('T')[0];
            reasonInput.value = '';
            loadCompanyOffDays();
        } else {
            showToast(`❌ ${data.message}`, 'error');
        }
    })
    .catch(err => {
        showToast('❌ Error adding company day off', 'error');
        console.error(err);
    })
    .finally(() => {
        addBtn.innerHTML = originalText;
        addBtn.disabled = false;
    });
}

// Remove a company day off
function removeCompanyDayOff() {
    const dropdown = document.getElementById('removeCompanyOffDate');
    const selectedDate = dropdown.value;

    if (!selectedDate) {
        showToast('❌ Please select a date to remove', 'error');
        return;
    }

    if (!confirm(`Are you sure you want to remove Company Day Off status from ${selectedDate}?`)) return;

    const removeBtn = document.getElementById('removeCompanyOffDay');
    const originalText = removeBtn.innerHTML;
    removeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing...';
    removeBtn.disabled = true;

    fetch('/company_day_off', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ action: 'remove', date: selectedDate })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
            dropdown.value = '';
            loadCompanyOffDays();
        } else {
            showToast(`❌ ${data.message}`, 'error');
        }
    })
    .catch(err => {
        showToast('❌ Error removing company day off', 'error');
        console.error(err);
    })
    .finally(() => {
        removeBtn.innerHTML = originalText;
        removeBtn.disabled = false;
    });
}

// Remove by date button
function removeCompanyDayOffByDate(date) {
    if (!confirm(`Are you sure you want to remove Company Day Off status from ${date}?`)) return;

    const dropdown = document.getElementById('removeCompanyOffDate');
    dropdown.value = date;
    removeCompanyDayOff();
}

// ===============================
// Toast Notification System
// ===============================
function showToast(message, type='success') {
    const toast = document.createElement('div');
    toast.className = `company-off-message ${type}`;
    toast.innerHTML = `<i class="fas ${type==='success'?'fa-check-circle':'fa-exclamation-circle'}"></i> ${message}`;
    
    document.body.appendChild(toast);

    // Auto-remove after 3s
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(() => document.body.removeChild(toast), 400);
    }, 3000);
}

// Initialize system on page load
document.addEventListener('DOMContentLoaded', initializeCompanyDayOffSystem);


// =======================================
// EMPLOYEE TABLE MANAGEMENT
// =======================================
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
    }

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

    function handleSearch(e) {
        state.searchTerm = e.target.value.toLowerCase();
        state.currentPage = 1;
        updateTable();
    }

    function handleDepartmentFilter(e) {
        state.departmentFilter = e.target.value;
        state.currentPage = 1;
        updateTable();
    }

    function clearFilters() {
        elements.employeeSearch.value = '';
        elements.departmentFilter.value = '';
        state.searchTerm = '';
        state.departmentFilter = '';
        state.currentPage = 1;
        updateTable();
    }

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

    function populateDepartmentFilter() {
        // Departments are already in the HTML
    }

    function scrollToForm() {
        document.getElementById('employeeFormSection').scrollIntoView({ 
            behavior: 'smooth' 
        });
    }

    function exportToExcel() {
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

    function editEmployee(employeeId, employeeName) {
        scrollToForm();
        showNotification(`Ready to edit ${employeeName}`, 'success');
    }

    function cancelEdit() {
        window.location.href = "{{ url_for('main.employees') }}";
    }

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
            console.log('Deleting employee:', state.employeeToDelete);
            showNotification(`Employee ${state.employeeToDelete.name} deleted successfully`, 'success');
            closeDeleteModal();
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }
    }

    function showNotification(message, type = 'success') {
        const existingNotif = document.querySelector('.custom-notification');
        if (existingNotif) existingNotif.remove();

        const notif = document.createElement('div');
        notif.className = `custom-notification ${type}`;
        notif.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check' : 'exclamation'}-circle"></i>
            <span>${message}</span>
        `;

        document.body.appendChild(notif);

        setTimeout(() => notif.classList.add('show'), 100);

        setTimeout(() => {
            notif.classList.remove('show');
            setTimeout(() => notif.remove(), 300);
        }, 3000);
    }

    init();
}

// =======================================
// DATA MANAGEMENT FUNCTIONS
// =======================================
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
    const pendingLate = settingsState.compensationData.records.filter(r => r.type === 'late').length;
    const pendingAbsent = settingsState.compensationData.records.filter(r => r.type === 'absent').length;
    const totalCompensated = settingsState.compensationData.records.length;
    
    updateElementText('pendingLateCount', pendingLate);
    updateElementText('pendingAbsentCount', pendingAbsent);
    updateElementText('totalCompensatedCount', totalCompensated);
    
    settingsState.compensationData.pendingLate = pendingLate;
    settingsState.compensationData.pendingAbsent = pendingAbsent;
    settingsState.compensationData.totalCompensated = totalCompensated;
}

// =======================================
// UTILITY FUNCTIONS
// =======================================
function updateElementText(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) element.textContent = value;
}

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

function confirmDelete(name) {
    return confirm(`Are you sure you want to delete employee: ${name}?`);
}

// =======================================
// GLOBAL FUNCTIONS
// =======================================
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

// =======================================
// DOM READY INITIALIZATION
// =======================================
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    
    const effectiveDateInput = document.getElementById('effective_date');
    if (effectiveDateInput && !effectiveDateInput.value) {
        const today = new Date().toISOString().split('T')[0];
        effectiveDateInput.value = today;
    }

    const joiningDateInput = document.getElementById('joining_date');
    if (joiningDateInput && !joiningDateInput.value) {
        const today = new Date().toISOString().split('T')[0];
        joiningDateInput.value = today;
    }

    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const tabId = btn.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });

    initEmployeeManagement();
    initializeCompanyDayOffSystem();
});