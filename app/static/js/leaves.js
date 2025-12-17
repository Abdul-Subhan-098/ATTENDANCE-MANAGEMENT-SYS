// ================= ADD LEAVE ======================
document.getElementById("leaveForm").addEventListener("submit", async function (event) {
    event.preventDefault();

    const employee_id = document.getElementById("employee_id").value;
    const leave_date = document.getElementById("leave_date").value;
    const leave_type = document.getElementById("leave_type").value;

    const message = document.getElementById("leaveMessage");
    message.textContent = "Saving...";

    try {
        const response = await fetch("/leaves", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                action: "add",
                employee_name: employee_id,
                leave_date: leave_date,
                leave_type: leave_type,
                reason: ""
            })
        });

        const result = await response.json();
        message.textContent = result.message;

        loadLeaves();
    } catch (error) {
        console.error(error);
        message.textContent = "Error saving leave.";
    }
});


// ================= FETCH LEAVE LIST ======================
async function loadLeaves() {
    try {
        const response = await fetch("/api/leaves");
        const data = await response.json();

        if (!data.success) return;

        const tableBody = document.querySelector("#leaveTable tbody");
        tableBody.innerHTML = "";

        data.leaves.forEach(row => {
            const tr = document.createElement("tr");

            tr.innerHTML = `
                <td>${row.employee_name}</td>
                <td>${row.leave_date}</td>
                <td>${row.leave_type}</td>
                <td><button onclick="removeLeave('${row.employee_name}', '${row.leave_date}')">Remove</button></td>
            `;

            tableBody.appendChild(tr);
        });

    } catch (error) {
        console.error("Error fetching leaves:", error);
    }
}

// ================= REMOVE LEAVE ======================
async function removeLeave(employee_name, leave_date) {
    if (!confirm("Remove this leave?")) return;

    try {
        const response = await fetch("/leaves", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                action: "remove",
                employee_name: employee_name,
                leave_date: leave_date
            })
        });

        const result = await response.json();
        alert(result.message);

        loadLeaves();

    } catch (error) {
        console.error(error);
    }
}

// Load on page start
loadLeaves();
