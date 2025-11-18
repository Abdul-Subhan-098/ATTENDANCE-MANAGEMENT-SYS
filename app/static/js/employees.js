// =======================================
// EMPLOYEE MANAGEMENT JS
// =======================================

// --------- 1. Auto-fill form when editing employee ---------
document.addEventListener("DOMContentLoaded", () => {
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
});

// --------- 2. Validate CNIC Format ---------
function validateCNIC(input) {
    let clean = input.value.replace(/[^\d]/g, '');
    if (clean.length > 13) clean = clean.slice(0, 13);

    if (clean.length === 13) {
        input.value = `${clean.slice(0,5)}-${clean.slice(5,12)}-${clean.slice(12)}`;
    } else {
        input.value = clean;
    }
}

// --------- 3. Validate Phone ---------
function validatePhone(input) {
    input.value = input.value.replace(/[^\d]/g, '');
    if (input.value.length > 11) input.value = input.value.slice(0, 11);
}

// --------- 4. Smooth table animations ---------
document.addEventListener("DOMContentLoaded", () => {
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
});

// --------- 5. Confirm before deleting ---------
function confirmDelete(name) {
    return confirm(`Are you sure you want to delete employee: ${name}?`);
}

// --------- 6. Auto reset form button ---------
document.addEventListener("DOMContentLoaded", () => {
    const resetBtn = document.getElementById("reset-btn");
    const submitBtn = document.getElementById("submit-btn");

    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            submitBtn.innerHTML = `<i class="fas fa-plus"></i> Add Employee`;
            submitBtn.style.background = "linear-gradient(135deg, #667eea, #764ba2)";
        });
    }
});
