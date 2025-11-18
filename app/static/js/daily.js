document.addEventListener("DOMContentLoaded", () => {
    // Cache DOM elements
    const elements = {
        table: document.getElementById("attendanceTable"),
        tbody: document.querySelector("#attendanceTable tbody"),
        employeeSearch: document.getElementById("employeeSearch"),
        employeeList: document.getElementById("employeeList"),
        dateFilter: document.getElementById("dateFilter"),
        statusFilter: document.getElementById("statusFilter"),
        clearFiltersBtn: document.getElementById("clearFilters"),
        dropdown: document.getElementById("compensateDropdown"),
        compensateBtn: document.getElementById("compensateBtn"),
        searchSpinner: document.getElementById("searchSpinner"),
        tableContainer: document.querySelector('.table-container')
    };

    // State management
    const state = {
        selectedEmployee: "",
        currentData: [],
        selectedBadge: null,
        DEFAULT_UI_LIMIT: 400,
        isRendering: false,
        abortController: null
    };

    // Configuration
    const config = {
        BATCH_SIZE: 50,
        DEBOUNCE_DELAY: 300,
        NOTIFICATION_TIMEOUT: 3000
    };

    // Status mappings (compile-time optimization)
    const STATUS_CLASSES = {
        'Present': 'status-present',
        'Absent': 'status-absent',
        'Late': 'status-late',
        'Half Day': 'status-halfday',
        'Half Day (Sat)': 'status-sat',
        'Full Day (Sat)': 'status-sat',
        'Compensated': 'status-compensated',
        'Sunday': 'status-sunday'
    };

    /* ============================
       🚀 PERFORMANCE UTILITIES
    ============================ */
    const debounce = (fn, delay = config.DEBOUNCE_DELAY) => {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => fn(...args), delay);
        };
    };

    const throttle = (fn, delay = 16) => {
        let lastCall = 0;
        return (...args) => {
            const now = Date.now();
            if (now - lastCall >= delay) {
                lastCall = now;
                fn(...args);
            }
        };
    };

    // Fast DOM creation with template literals
    const createElement = (html) => {
        const template = document.createElement('template');
        template.innerHTML = html.trim();
        return template.content.firstElementChild;
    };

    /* ============================
       🔹 INITIAL LOAD (OPTIMIZED)
    ============================ */
    async function loadInitialData() {
        // Cancel previous request if any
        if (state.abortController) {
            state.abortController.abort();
        }
        state.abortController = new AbortController();

        try {
            showLoading(true);
            const res = await fetch("/api/daily_search", {
                signal: state.abortController.signal
            });
            
            if (!res.ok) throw new Error("Failed to fetch initial data");
            
            const json = await res.json();
            const records = (json.data || []).sort((a, b) => a.Name.localeCompare(b.Name));
            state.currentData = records;

            // Limit default UI to improve performance
            const limitedRecords = records.slice(0, state.DEFAULT_UI_LIMIT);
            await renderFromServer(limitedRecords);

            populateDateFilter(records);
            showNotification(`Loaded ${limitedRecords.length} of ${records.length} records`, "success");
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error(err);
                showNotification("Error loading initial data", "error");
            }
        } finally {
            showLoading(false);
            state.abortController = null;
        }
    }

    /* ============================
       📅 POPULATE DATE FILTER (OPTIMIZED)
    ============================ */
    function populateDateFilter(records) {
        const dates = [...new Set(records.map(r => r.Date).filter(Boolean))];
        dates.sort((a, b) => new Date(b) - new Date(a));
        
        // Batch DOM updates
        const fragment = document.createDocumentFragment();
        dates.forEach(date => {
            const option = document.createElement("option");
            option.value = date;
            option.textContent = date;
            fragment.appendChild(option);
        });
        
        // Remove existing options efficiently
        while (elements.dateFilter.options.length > 1) {
            elements.dateFilter.remove(1);
        }
        
        elements.dateFilter.appendChild(fragment);
    }

    /* ============================
       🔍 SEARCHABLE DROPDOWN (OPTIMIZED)
    ============================ */
    function initSearchableDropdown() {
        const handleSearch = debounce(async () => {
            const query = elements.employeeSearch.value.trim();
            
            if (query.length === 0) {
                elements.employeeList.style.display = "none";
                state.selectedEmployee = "";
                loadInitialData();
                return;
            }

            if (query.length < 2) {
                elements.employeeList.style.display = "none";
                return;
            }

            showSpinner(true);
            const suggestions = await fetchEmployeeSuggestions(query);
            showSpinner(false);
            
            renderSuggestions(suggestions);
        });

        elements.employeeSearch.addEventListener("input", handleSearch);

        elements.employeeSearch.addEventListener("focus", () => {
            if (elements.employeeList.children.length > 0) {
                elements.employeeList.style.display = "block";
            }
        });

        document.addEventListener("click", e => {
            if (!e.target.closest(".searchable-dropdown")) {
                elements.employeeList.style.display = "none";
            }
        });
    }

    function renderSuggestions(suggestions) {
        elements.employeeList.innerHTML = "";

        if (suggestions.length === 0) {
            const li = createElement(`
                <li style="color: #6b7280; font-style: italic; pointer-events: none;">
                    No matching names found
                </li>
            `);
            elements.employeeList.appendChild(li);
            elements.employeeList.style.display = "block";
            return;
        }

        const fragment = document.createDocumentFragment();
        suggestions.sort((a, b) => a.localeCompare(b));
        
        suggestions.forEach(name => {
            const li = createElement(`<li data-value="${name}">${name}</li>`);
            li.addEventListener("click", () => {
                state.selectedEmployee = name;
                elements.employeeSearch.value = name;
                elements.employeeList.style.display = "none";
                serverSearch(name);
            });
            fragment.appendChild(li);
        });
        
        elements.employeeList.appendChild(fragment);
        elements.employeeList.style.display = "block";
    }

    /* ============================
       🌐 FETCH EMPLOYEE SUGGESTIONS (OPTIMIZED)
    ============================ */
    async function fetchEmployeeSuggestions(query) {
        const dateVal = elements.dateFilter.value;
        const statusVal = elements.statusFilter.value;

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
       🌐 SERVER SEARCH (OPTIMIZED)
    ============================ */
    async function serverSearch(query) {
        const dateVal = elements.dateFilter.value;
        const statusVal = elements.statusFilter.value;

        // Cancel previous request
        if (state.abortController) {
            state.abortController.abort();
        }
        state.abortController = new AbortController();

        try {
            showLoading(true);
            const params = new URLSearchParams();
            if (query) params.append('q', query);
            if (dateVal) params.append('date', dateVal);
            if (statusVal) params.append('status', statusVal);

            const res = await fetch(`/api/daily_search?${params.toString()}`, {
                signal: state.abortController.signal
            });
            
            if (!res.ok) throw new Error("Server error");
            
            const data = await res.json();
            const records = (data.data || []).sort((a, b) => a.Name.localeCompare(b.Name));
            state.currentData = records;

            if (records.length > 0) {
                await renderFromServer(records);
                showNotification(`Found ${records.length} record(s)`, "success");
            } else {
                showEmptyState();
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error("Search failed:", err);
                showNotification("Error fetching search results", "error");
            }
        } finally {
            showLoading(false);
            state.abortController = null;
        }
    }

    /* ============================
       🧩 RENDER RECORDS (HEAVILY OPTIMIZED)
    ============================ */
    async function renderFromServer(records) {
        if (state.isRendering) return;
        state.isRendering = true;

        elements.tbody.innerHTML = "";
        
        if (records.length === 0) {
            showEmptyState();
            state.isRendering = false;
            return;
        }

        // Use requestAnimationFrame for smooth rendering
        await new Promise(resolve => {
            const renderChunk = throttle(() => {
                const batchSize = config.BATCH_SIZE;
                const totalRecords = records.length;
                let renderedCount = 0;

                const renderBatch = () => {
                    const start = renderedCount;
                    const end = Math.min(renderedCount + batchSize, totalRecords);
                    const batch = records.slice(start, end);
                    
                    const fragment = document.createDocumentFragment();
                    
                    batch.forEach(r => {
                        const tr = createTableRow(r);
                        fragment.appendChild(tr);
                    });
                    
                    elements.tbody.appendChild(fragment);
                    renderedCount = end;

                    if (renderedCount < totalRecords) {
                        setTimeout(renderBatch, 0);
                    } else {
                        state.isRendering = false;
                        resolve();
                    }
                };

                renderBatch();
            });

            requestAnimationFrame(renderChunk);
        });
    }

    function createTableRow(r) {
        const statusClass = STATUS_CLASSES[r.Status] || 'status-absent';
        const otClass = `ot-${Math.min(parseInt(r.Overtime) || 0, 5)}`;
        const overtimeDisplay = formatOvertime(r.Overtime);

        return createElement(`
            <tr data-name="${r.Name || ""}" data-date="${r.Date || ""}" data-status="${r.Status || ""}" data-department="${r.Department || ""}">
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
            </tr>
        `);
    }

    function formatOvertime(value) {
        if (!value || parseFloat(value) === 0) return "0h";
        const hours = Math.floor(parseFloat(value));
        const minutes = Math.round((parseFloat(value) - hours) * 60);
        return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`;
    }

    function showEmptyState() {
        elements.tbody.innerHTML = `
            <tr class="empty-state">
                <td colspan="11">
                    <i class="fas fa-search empty-state-icon"></i>
                    <h3>No matching records found</h3>
                    <p>Try adjusting your search criteria</p>
                </td>
            </tr>
        `;
    }

    /* ============================
       🔔 NOTIFICATION TOAST (OPTIMIZED)
    ============================ */
    function showNotification(message, type = "success") {
        const existingNotif = document.querySelector('.notification');
        if (existingNotif) existingNotif.remove();

        const notif = createElement(`
            <div class="notification ${type}">
                <i class="fas fa-${type === "success" ? "check" : "exclamation"}-circle"></i>
                <span>${message}</span>
            </div>
        `);

        document.body.appendChild(notif);

        requestAnimationFrame(() => notif.style.transform = "translateX(0)");
        setTimeout(() => {
            notif.style.transform = "translateX(400px)";
            setTimeout(() => notif.remove(), 300);
        }, config.NOTIFICATION_TIMEOUT);
    }

    /* ============================
       🧹 CLEAR FILTERS
    ============================ */
    elements.clearFiltersBtn.addEventListener("click", () => {
        elements.employeeSearch.value = "";
        state.selectedEmployee = "";
        elements.dateFilter.value = "";
        elements.statusFilter.value = "";
        elements.employeeList.style.display = "none";
        loadInitialData();
        showNotification("Filters cleared", "success");
    });

    /* ============================
       📅 FILTER CHANGE HANDLERS
    ============================ */
    elements.dateFilter.addEventListener("change", applyFilters);
    elements.statusFilter.addEventListener("change", applyFilters);

    function applyFilters() {
        serverSearch(state.selectedEmployee || "");
    }

    /* ============================
       ✅ MARK AS COMPENSATED (OPTIMIZED)
    ============================ */
    function initCompensationHandler() {
        document.addEventListener("click", e => {
            const badge = e.target.closest(".status-badge");
            if (badge) {
                state.selectedBadge = badge;
                const rect = badge.getBoundingClientRect();
                elements.dropdown.style.display = "block";
                elements.dropdown.style.position = "fixed";
                elements.dropdown.style.left = `${rect.left}px`;
                elements.dropdown.style.top = `${rect.bottom + 8}px`;
                elements.dropdown.dataset.empName = badge.dataset.empName;
                elements.dropdown.dataset.date = badge.dataset.date;
            } else if (!e.target.closest("#compensateDropdown")) {
                elements.dropdown.style.display = "none";
            }
        });

        elements.compensateBtn.addEventListener("click", async () => {
            if (!state.selectedBadge) return;
            const empName = elements.dropdown.dataset.empName;
            const date = elements.dropdown.dataset.date;
            
            try {
                const res = await fetch("/update_compensate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ emp_name: empName, date })
                });
                const result = await res.json();
                
                if (result.success) {
                    state.selectedBadge.textContent = "Compensated";
                    state.selectedBadge.className = "status-badge status-compensated";
                    showNotification(`${empName} marked as compensated for ${date}`, "success");
                    applyFilters();
                } else {
                    showNotification(`${result.message || "Update failed"}`, "error");
                }
            } catch (err) {
                console.error(err);
                showNotification("Server error while updating", "error");
            } finally {
                elements.dropdown.style.display = "none";
                state.selectedBadge = null;
            }
        });
    }

    /* ============================
       ⚙️ LOADING STATES
    ============================ */
    function showLoading(show) {
        if (elements.tableContainer) {
            elements.tableContainer.style.opacity = show ? '0.6' : '1';
            elements.tableContainer.style.pointerEvents = show ? 'none' : 'auto';
        }
    }

    function showSpinner(show) {
        if (elements.searchSpinner) {
            elements.searchSpinner.style.display = show ? 'inline-block' : 'none';
        }
    }

    /* ============================
       🚀 INITIALIZATION
    ============================ */
    function init() {
        initSearchableDropdown();
        initCompensationHandler();
        loadInitialData();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', e => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                elements.employeeSearch.focus();
            }
        });
    }

    init();
});