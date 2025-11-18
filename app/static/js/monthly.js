// Initialize Searchable Dropdown
function initSearchableDropdown(id) {
    const dropdown = document.getElementById(id);
    if (!dropdown) return;

    const input = dropdown.querySelector(".search-input");
    const hidden = dropdown.querySelector("input[type='hidden']");
    const list = dropdown.querySelector(".dropdown-list");

    input.addEventListener("input", () => {
        const filter = input.value.toLowerCase();
        let hasVisibleItems = false;

        list.querySelectorAll("li").forEach(li => {
            const visible = li.textContent.toLowerCase().includes(filter);
            li.style.display = visible ? "block" : "none";
            if (visible) hasVisibleItems = true;
        });

        list.style.display = hasVisibleItems ? "block" : "none";
    });

    list.querySelectorAll("li").forEach(li => {
        li.addEventListener("click", () => {
            input.value = li.textContent;
            hidden.value = li.dataset.value;
            list.style.display = "none";
        });
    });

    input.addEventListener("focus", () => {
        list.style.display = "block";
        list.querySelectorAll("li").forEach(li => li.style.display = "block");
    });

    document.addEventListener("click", (e) => {
        if (!dropdown.contains(e.target)) list.style.display = "none";
    });
}

// Table Search - IMPROVED VERSION
function initTableSearch() {
    const searchInput = document.getElementById("agentSearch");
    const table = document.getElementById("summaryTable");
    
    if (!searchInput || !table) return;

    searchInput.addEventListener("input", function() {
        const searchTerm = this.value.toLowerCase().trim();
        const tbody = table.querySelector('tbody');
        const rows = tbody.getElementsByTagName('tr');
        
        let visibleCount = 0;
        
        for (let row of rows) {
            // Search in Name column (2nd column - index 1)
            const nameCell = row.cells[1];
            const name = nameCell.textContent.toLowerCase();
            
            if (name.includes(searchTerm)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        }
        
        // Show message if no results found
        showNoResultsMessage(visibleCount === 0 && searchTerm !== '');
    });
}

// Show no results message
function showNoResultsMessage(show) {
    let messageDiv = document.getElementById('noResultsMessage');
    
    if (show && !messageDiv) {
        messageDiv = document.createElement('div');
        messageDiv.id = 'noResultsMessage';
        messageDiv.style.cssText = `
            text-align: center;
            padding: 20px;
            color: #666;
            font-style: italic;
            background: #f8f9fa;
            border-radius: 8px;
            margin: 10px 0;
        `;
        messageDiv.textContent = 'No employees found matching your search.';
        
        const tableContainer = document.getElementById('tableContainer');
        if (tableContainer) {
            tableContainer.appendChild(messageDiv);
        }
    } else if (!show && messageDiv) {
        messageDiv.remove();
    }
}

// Clear search when page loads
function clearSearchOnLoad() {
    const searchInput = document.getElementById("agentSearch");
    if (searchInput) {
        searchInput.value = '';
    }
    showNoResultsMessage(false);
}

// Enhanced table sorting (optional)
function initTableSorting() {
    const table = document.getElementById("summaryTable");
    if (!table) return;

    const headers = table.querySelectorAll('thead th');
    
    headers.forEach((header, index) => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', () => {
            sortTableByColumn(table, index);
        });
    });
}

// Sort table by column
function sortTableByColumn(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const isAscending = !tbody.getAttribute('data-sort-asc');
    
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();
        
        // Try to convert to number for numeric columns
        const aNum = parseFloat(aText);
        const bNum = parseFloat(bText);
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAscending ? aNum - bNum : bNum - aNum;
        }
        
        // Otherwise sort as text
        return isAscending 
            ? aText.localeCompare(bText)
            : bText.localeCompare(aText);
    });
    
    // Remove existing rows
    rows.forEach(row => tbody.removeChild(row));
    
    // Add sorted rows
    rows.forEach(row => tbody.appendChild(row));
    
    // Toggle sort direction
    tbody.setAttribute('data-sort-asc', isAscending ? 'true' : '');
}

// Initialize all
document.addEventListener("DOMContentLoaded", () => {
    initSearchableDropdown("shiftDropdown");
    initSearchableDropdown("compDropdown");
    initTableSearch();
    initTableSorting();
    clearSearchOnLoad();
    
    // Add search icon click functionality
    const searchInput = document.getElementById("agentSearch");
    if (searchInput) {
        // Create and add clear button
        const clearButton = document.createElement('button');
        clearButton.innerHTML = '&times;';
        clearButton.style.cssText = `
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
        `;
        clearButton.addEventListener('click', () => {
            searchInput.value = '';
            searchInput.dispatchEvent(new Event('input'));
            searchInput.focus();
        });
        
        const searchBox = searchInput.parentElement;
        searchBox.style.position = 'relative';
        searchBox.appendChild(clearButton);
        
        // Show/hide clear button
        searchInput.addEventListener('input', function() {
            clearButton.style.display = this.value ? 'block' : 'none';
        });
    }
});