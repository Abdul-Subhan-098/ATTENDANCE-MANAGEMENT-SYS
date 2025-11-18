document.addEventListener("DOMContentLoaded", () => {
    const table = document.getElementById("attendanceTable");
    const tbody = table.querySelector("tbody");
    const employeeSearch = document.getElementById("employeeSearch");
    const employeeList = document.getElementById("employeeList");
    const dateFilter = document.getElementById("dateFilter");
    const statusFilter = document.getElementById("statusFilter");
    const clearFiltersBtn = document.getElementById("clearFilters");
    const dropdown = document.getElementById("compensateDropdown");
    const compensateBtn = document.getElementById("compensateBtn");
    const searchSpinner = document.getElementById("searchSpinner");

    let selectedEmployee = "";
    let currentData = [];
    let selectedBadge = null;
    const DEFAULT_UI_LIMIT = 400; // Limit UI to 400 rows by default

    const debounce = (fn, delay = 300) => {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn(...args), delay);
        };
    };

    /* ============================
       🔹 INITIAL LOAD
    ============================ */
    async function loadInitialData() {
        try {
            showLoading(true);
            const res = await fetch("/api/daily_search");
            if (!res.ok) throw new Error("Failed to fetch initial data");
            const json = await res.json();
            const records = (json.data || []).sort((a, b) => a.Name.localeCompare(b.Name));
            currentData = records;

            // Limit default UI to 400 rows
            const limitedRecords = records.slice(0, DEFAULT_UI_LIMIT);
            renderFromServer(limitedRecords);

            populateDateFilter(records);
            showNotification(`Loaded ${limitedRecords.length} of ${records.length} records`, "success");
        } catch (err) {
            console.error(err);
            showNotification("Error loading initial data", "error");
        } finally {
            showLoading(false);
        }
    }

    /* ============================
       📅 POPULATE DATE FILTER
    ============================ */
    function populateDateFilter(records) {
        const dates = [...new Set(records.map(r => r.Date).filter(Boolean))];
        dates.sort((a, b) => new Date(b) - new Date(a)); // Sort descending
        
        while (dateFilter.options.length > 1) {
            dateFilter.remove(1);
        }
        
        dates.forEach(date => {
            const option = document.createElement("option");
            option.value = date;
            option.textContent = date;
            dateFilter.appendChild(option);
        });
    }

    /* ============================
       🔍 SEARCHABLE DROPDOWN
    ============================ */
    function initSearchableDropdown() {
        employeeSearch.addEventListener("input", debounce(async () => {
            const query = employeeSearch.value.trim();
            if (query.length === 0) {
                employeeList.style.display = "none";
                selectedEmployee = "";
                loadInitialData();
                return;
            }

            if (query.length < 2) {
                employeeList.style.display = "none";
                return;
            }

            showSpinner(true);
            const suggestions = await fetchEmployeeSuggestions(query);
            showSpinner(false);
            
            employeeList.innerHTML = "";

            if (suggestions.length > 0) {
                suggestions.sort((a, b) => a.localeCompare(b));
                suggestions.forEach(name => {
                    const li = document.createElement("li");
                    li.textContent = name;
                    li.dataset.value = name;
                    li.addEventListener("click", () => {
                        selectedEmployee = name;
                        employeeSearch.value = name;
                        employeeList.style.display = "none";
                        serverSearch(name);
                    });
                    employeeList.appendChild(li);
                });
                employeeList.style.display = "block";
            } else {
                const li = document.createElement("li");
                li.textContent = "No matching names found";
                li.style.color = "#6b7280";
                li.style.fontStyle = "italic";
                li.style.pointerEvents = "none";
                employeeList.appendChild(li);
                employeeList.style.display = "block";
            }
        }, 300));

        employeeSearch.addEventListener("focus", () => {
            if (employeeList.children.length > 0) {
                employeeList.style.display = "block";
            }
        });

        document.addEventListener("click", e => {
            if (!e.target.closest(".searchable-dropdown")) {
                employeeList.style.display = "none";
            }
        });
    }

    /* ============================
       🌐 FETCH EMPLOYEE SUGGESTIONS
    ============================ */
    async function fetchEmployeeSuggestions(query) {
        const dateVal = dateFilter.value;
        const statusVal = statusFilter.value;

        try {
            const params = new URLSearchParams();
            params.append('q', query);
            if (dateVal) params.append('date', dateVal);
            if (statusVal) params.append('status', statusVal);

            const res = await fetch(`/api/daily_search?${params.toString()}`);
            if (!res.ok) throw new Error("Server error");
            const data = await res.json();
            const records = data.data || [];
            const names = [...new Set(records.map(r => r.Name).filter(Boolean))];
            return names.slice(0, 20);
        } catch (err) {
            console.error("Error fetching suggestions:", err);
            return [];
        }
    }

    /* ============================
       🌐 SERVER SEARCH
    ============================ */
    async function serverSearch(query) {
        const dateVal = dateFilter.value;
        const statusVal = statusFilter.value;

        try {
            showLoading(true);
            const params = new URLSearchParams();
            if (query) params.append('q', query);
            if (dateVal) params.append('date', dateVal);
            if (statusVal) params.append('status', statusVal);

            const res = await fetch(`/api/daily_search?${params.toString()}`);
            if (!res.ok) throw new Error("Server error");
            const data = await res.json();
            const records = (data.data || []).sort((a, b) => a.Name.localeCompare(b.Name));
            currentData = records;

            if (records.length > 0) {
                // For search, render all matching rows (no limit)
                renderFromServer(records);
                showNotification(`Found ${records.length} record(s)`, "success");
            } else {
                tbody.innerHTML = `
                    <tr class="empty-state">
                        <td colspan="11">
                            <i class="fas fa-search empty-state-icon"></i>
                            <h3>No matching records found</h3>
                            <p>Try adjusting your search criteria</p>
                        </td>
                    </tr>
                `;
            }
        } catch (err) {
            console.error("Search failed:", err);
            showNotification("Error fetching search results", "error");
        } finally {
            showLoading(false);
        }
    }

    /* ============================
       🧩 RENDER RECORDS
    ============================ */
    function renderFromServer(records) {
        tbody.innerHTML = "";
        
        if (records.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-state">
                    <td colspan="11">
                        <i class="fas fa-clipboard-list empty-state-icon"></i>
                        <h3>No Records Found</h3>
                        <p>No attendance records available for the selected criteria</p>
                    </td>
                </tr>
            `;
            return;
        }

        const fragment = document.createDocumentFragment();
        const batchSize = 100;
        let index = 0;

        function formatOvertime(value) {
            if (!value || parseFloat(value) === 0) return "0h";
            const hours = Math.floor(parseFloat(value));
            const minutes = Math.round((parseFloat(value) - hours) * 60);
            return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`;
        }

        function getStatusClass(status) {
            const statusMap = {
                'Present': 'status-present',
                'Absent': 'status-absent',
                'Late': 'status-late',
                'Half Day': 'status-halfday',
                'Half Day (Sat)': 'status-sat',
                'Full Day (Sat)': 'status-sat',
                'Compensated': 'status-compensated',
                'Sunday': 'status-sunday'
            };
            return statusMap[status] || 'status-absent';
        }

        function getOTClass(overtime) {
            const otValue = parseInt(overtime) || 0;
            return `ot-${Math.min(otValue, 5)}`;
        }

        function renderChunk() {
            const end = Math.min(index + batchSize, records.length);
            for (; index < end; index++) {
                const r = records[index];
                const tr = document.createElement("tr");
                tr.dataset.name = r.Name || "";
                tr.dataset.date = r.Date || "";
                tr.dataset.status = r.Status || "";
                tr.dataset.department = r.Department || "";

                const statusClass = getStatusClass(r.Status);
                const otClass = getOTClass(r.Overtime);
                const overtimeDisplay = formatOvertime(r.Overtime);

                tr.innerHTML = `
                    <td><strong>${r.EmpID || "N/A"}</strong></td>
                    <td>${r.Date || "N/A"}</td>
                    <td><strong>${r.Name || "N/A"}</strong></td>
                    <td>${r.ShiftDisplay || "N/A"}</td>
                    <td>${r.CheckIn || "Not Recorded"}</td>
                    <td>${r.CheckOut || "Not Recorded"}</td>
                    <td>
                        <span class="ot-badge ${otClass}">
                            ${overtimeDisplay}
                        </span>
                    </td>
                    <td>
                        <span class="status-badge ${statusClass}"
                              data-emp-name="${r.Name}" 
                              data-date="${r.Date}">
                              ${r.Status || "Absent"}
                        </span>
                    </td>
                    <td>${r.MissedCheckIn || "No"}</td>
                    <td>${r.MissedCheckOut || "No"}</td>
                    <td>${r.Department || ""}</td>
                `;
                fragment.appendChild(tr);
            }

            tbody.appendChild(fragment);
            if (index < records.length) {
                setTimeout(renderChunk, 0);
            }
        }

        renderChunk();
    }

    /* ============================
       🔔 NOTIFICATION TOAST
    ============================ */
    function showNotification(message, type = "success") {
        const existingNotif = document.querySelector('.notification');
        if (existingNotif) existingNotif.remove();

        const notif = document.createElement("div");
        notif.className = `notification ${type}`;
        notif.innerHTML = `
            <i class="fas fa-${type === "success" ? "check" : "exclamation"}-circle"></i>
            <span>${message}</span>
        `;
        document.body.appendChild(notif);

        requestAnimationFrame(() => notif.style.transform = "translateX(0)");
        setTimeout(() => {
            notif.style.transform = "translateX(400px)";
            setTimeout(() => notif.remove(), 300);
        }, 3000);
    }

    /* ============================
       🧹 CLEAR FILTERS
    ============================ */
    clearFiltersBtn.addEventListener("click", () => {
        employeeSearch.value = "";
        selectedEmployee = "";
        dateFilter.value = "";
        statusFilter.value = "";
        employeeList.style.display = "none";
        loadInitialData();
        showNotification("Filters cleared", "success");
    });

    /* ============================
       📅 DATE FILTER CHANGE
    ============================ */
    dateFilter.addEventListener("change", applyFilters);
    statusFilter.addEventListener("change", applyFilters);

    function applyFilters() {
        serverSearch(selectedEmployee || "");
    }

    /* ============================
       ✅ MARK AS COMPENSATED LOGIC
    ============================ */
    document.addEventListener("click", e => {
        const badge = e.target.closest(".status-badge");
        if (badge) {
            selectedBadge = badge;
            const rect = badge.getBoundingClientRect();
            dropdown.style.display = "block";
            dropdown.style.position = "fixed";
            dropdown.style.left = `${rect.left}px`;
            dropdown.style.top = `${rect.bottom + 8}px`;
            dropdown.dataset.empName = badge.dataset.empName;
            dropdown.dataset.date = badge.dataset.date;
        } else if (!e.target.closest("#compensateDropdown")) {
            dropdown.style.display = "none";
        }
    });

    compensateBtn.addEventListener("click", async () => {
        if (!selectedBadge) return;
        const empName = dropdown.dataset.empName;
        const date = dropdown.dataset.date;
        try {
            const res = await fetch("/update_compensate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ emp_name: empName, date })
            });
            const result = await res.json();
            if (result.success) {
                selectedBadge.textContent = "Compensated";
                selectedBadge.className = "status-badge status-compensated";
                showNotification(`${empName} marked as compensated for ${date}`, "success");
                applyFilters();
            } else {
                showNotification(`${result.message || "Update failed"}`, "error");
            }
        } catch (err) {
            console.error(err);
            showNotification("Server error while updating", "error");
        } finally {
            dropdown.style.display = "none";
            selectedBadge = null;
        }
    });

    /* ============================
       ⚙️ LOADING STATES
    ============================ */
    function showLoading(show) {
        const tableContainer = document.querySelector('.table-container');
        tableContainer.style.opacity = show ? '0.6' : '1';
        tableContainer.style.pointerEvents = show ? 'none' : 'auto';
    }

    function showSpinner(show) {
        if (searchSpinner) searchSpinner.style.display = show ? 'inline-block' : 'none';
    }

    /* ============================
       🚀 INITIALIZATION
    ============================ */
    function init() {
        initSearchableDropdown();
        loadInitialData();
        document.addEventListener('keydown', e => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                employeeSearch.focus();
            }
        });
    }

    init();
});
