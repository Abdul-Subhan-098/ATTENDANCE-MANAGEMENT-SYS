// =======================================
// EMPLOYEE MANAGEMENT JS - FIXED VERSION
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
    initializeCompensationSystem(); // Fixed: Added this line
});

// Employee Management Functions
function initializeEmployeeSystem() {
    // Auto-fill form when editing employee
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

    // Auto reset form button
    const resetBtn = document.getElementById("reset-btn");
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            submitBtn.innerHTML = `<i class="fas fa-plus"></i> Add Employee`;
            submitBtn.style.background = "linear-gradient(135deg, #667eea, #764ba2)";
        });
    }

    // Smooth table animations
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

// Settings System Functions
function initializeSettingsSystem() {
    initializeThemeSystem();
    initializeSettingsTabs();
    loadSelectedEmployees();
}

// Theme System
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
    showToast(`🌙 ${settingsState.currentTheme === 'dark' ? 'Dark' : 'Light'} theme activated`, 'success');
}

function updateThemeIcon() {
    const themeIcon = document.getElementById('themeIcon');
    if (themeIcon) {
        themeIcon.className = settingsState.currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }
}

// Settings Tabs
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
// COMPENSATION SYSTEM - FIXED VERSION
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
    if (applyBtn) {
        applyBtn.addEventListener('click', applyCompensation);
    }
    
    // Check Eligibility Button
    const checkEligibilityBtn = document.getElementById('checkEligibilityBtn');
    if (checkEligibilityBtn) {
        checkEligibilityBtn.addEventListener('click', checkEligibility);
    }
    
    // Clear Form Button
    const clearBtn = document.getElementById('clearCompensationForm');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearCompensationForm);
    }
    
    // Refresh History Button
    const refreshBtn = document.getElementById('refreshHistoryBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadCompensationHistory);
    }
    
    // Add manual employee button
    const addManualBtn = document.getElementById('addManualEmployee');
    if (addManualBtn) {
        addManualBtn.addEventListener('click', addManualEmployee);
    }
    
    // Enter key for manual input
    const manualInput = document.getElementById('manualEmployeeInput');
    if (manualInput) {
        manualInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                addManualEmployee();
            }
        });
    }
}

function initializeDateFields() {
    // Set default dates for new compensation form
    const today = new Date().toISOString().split('T')[0];
    const compensationDate = document.getElementById('compensationDate');
    if (compensationDate) {
        compensationDate.value = today;
    }
    
    // Set violation date to yesterday by default
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const violationDate = document.getElementById('violationDate');
    if (violationDate) {
        violationDate.value = yesterday.toISOString().split('T')[0];
    }
}

function loadEmployeeSuggestions() {
    // Load employee names for autocomplete
    fetch('/api/daily_search?limit=1000')
        .then(response => response.json())
        .then(data => {
            if (data.data && data.data.length > 0) {
                const uniqueNames = [...new Set(data.data.map(record => record.Name))].sort();
                const datalist = document.getElementById('employeeSuggestions');
                if (datalist) {
                    datalist.innerHTML = uniqueNames.map(name => 
                        `<option value="${name}">${name}</option>`
                    ).join('');
                }
            }
        })
        .catch(error => {
            console.error('Error loading employee suggestions:', error);
        });
}

function checkEligibility() {
    const employee = document.getElementById('compensationEmployee').value.trim();
    const violationDate = document.getElementById('violationDate').value;
    const compensationType = document.getElementById('compensationType').value;
    
    if (!employee || !violationDate || !compensationType) {
        showCompensationResult('Please fill all required fields', 'error');
        return;
    }
    
    // Show loading state
    const eligibilityResult = document.getElementById('eligibilityResult');
    eligibilityResult.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking eligibility...';
    eligibilityResult.className = 'eligibility-result';
    eligibilityResult.style.display = 'block';
    
    // Check eligibility via API
    fetch('/check_compensation_eligibility', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            employee_name: employee,
            violation_date: violationDate,
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

function applyCompensation() {
    const employee = document.getElementById('compensationEmployee').value.trim();
    const violationDate = document.getElementById('violationDate').value;
    const compensationDate = document.getElementById('compensationDate').value;
    const compensationType = document.getElementById('compensationType').value;
    
    if (!employee || !violationDate || !compensationDate || !compensationType) {
        showCompensationResult('Please fill all required fields', 'error');
        return;
    }
    
    // Show loading state
    const applyBtn = document.getElementById('applyCompensationBtn');
    const originalText = applyBtn.innerHTML;
    applyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
    applyBtn.disabled = true;
    
    // Apply compensation via API
    fetch('/apply_compensation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
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
            loadCompensationHistory(); // Refresh history
        } else {
            showCompensationResult(data.message, 'error');
        }
    })
    .catch(error => {
        showCompensationResult('Error applying compensation', 'error');
        console.error('Compensation application error:', error);
    })
    .finally(() => {
        // Restore button state
        applyBtn.innerHTML = originalText;
        applyBtn.disabled = false;
    });
}

function showCompensationResult(message, type) {
    const resultDiv = document.getElementById('compensationResult');
    if (resultDiv) {
        resultDiv.innerHTML = message;
        resultDiv.className = `result-message ${type}`;
        resultDiv.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            resultDiv.style.display = 'none';
        }, 5000);
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
    
    // Show loading
    historyList.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>Loading history...</p></div>';
    
    // Fetch compensation history
    fetch('/api/compensation_history')
        .then(response => response.json())
        .then(data => {
            if (data.history && data.history.length > 0) {
                renderCompensationHistory(data.history);
            } else {
                historyList.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-history"></i>
                        <p>No compensation records yet</p>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading compensation history:', error);
            historyList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>Error loading history</p>
                </div>
            `;
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