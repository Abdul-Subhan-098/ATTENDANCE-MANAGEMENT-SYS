document.addEventListener('DOMContentLoaded', function() {
    console.log('Activity Logs page loaded - USER ACTIVITIES ONLY');
    
    const activityLogsBody = document.getElementById('activityLogsBody');
    const emptyState = document.getElementById('emptyState');
    const applyFiltersBtn = document.getElementById('applyFilters');
    const clearFiltersBtn = document.getElementById('clearFilters');
    

    loadFilterOptions();
    loadActivityLogs();
    
    // Button event listeners
    applyFiltersBtn.addEventListener('click', function() {
        console.log('Apply filters clicked');
        loadActivityLogs();
    });
    
    clearFiltersBtn.addEventListener('click', function() {
        console.log('Clear filters clicked');
        document.getElementById('usernameFilter').value = '';
        document.getElementById('entityTypeFilter').value = '';
        document.getElementById('startDate').value = '';
        document.getElementById('endDate').value = '';
        loadActivityLogs();
    });

    function loadFilterOptions() {
        console.log('Loading filter options...');
        
        // ✅ SYSTEM/ADMIN EXCLUDE KARNE KE LIYE NAYA ENDPOINT
        fetch('/api/user_activity_filters')
            .then(response => response.json())
            .then(data => {
                console.log('Filter options received:', data);
                
                if (data.success) {
                    // Username filter populate karo
                    const usernameFilter = document.getElementById('usernameFilter');
                    usernameFilter.innerHTML = '<option value="">All Users</option>';
                    
                    data.usernames.forEach(username => {
                        const option = document.createElement('option');
                        option.value = username;
                        option.textContent = username;
                        usernameFilter.appendChild(option);
                    });
                    
                    // Entity type filter populate karo
                    const entityTypeFilter = document.getElementById('entityTypeFilter');
                    entityTypeFilter.innerHTML = '<option value="">All Types</option>';
                    
                    data.entity_types.forEach(entityType => {
                        const option = document.createElement('option');
                        option.value = entityType;
                        // Make display name readable
                        const displayName = entityType
                            .replace(/_/g, ' ')
                            .replace(/\b\w/g, l => l.toUpperCase());
                        option.textContent = displayName;
                        entityTypeFilter.appendChild(option);
                    });
                    
                    console.log('Filters loaded successfully');
                } else {
                    console.error('Failed to load filter options:', data.message);
                    // Fallback: Use old endpoint
                    loadFallbackFilters();
                }
            })
            .catch(error => {
                console.error('Error loading filter options:', error);
                loadFallbackFilters();
            });
    }
    
    // Fallback function agar naya endpoint fail ho
    function loadFallbackFilters() {
        console.log('Trying fallback filter endpoint...');
        fetch('/api/activity_logs/filters')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Username filter
                    const usernameFilter = document.getElementById('usernameFilter');
                    usernameFilter.innerHTML = '<option value="">All Users</option>';
                    
                    // Filter out System and Admin manually
                    data.usernames.forEach(username => {
                        if (!['System', 'Admin', 'system', 'admin'].includes(username)) {
                            const option = document.createElement('option');
                            option.value = username;
                            option.textContent = username;
                            usernameFilter.appendChild(option);
                        }
                    });
                    
                    // Entity type filter
                    const entityTypeFilter = document.getElementById('entityTypeFilter');
                    entityTypeFilter.innerHTML = '<option value="">All Types</option>';
                    
                    data.entity_types.forEach(entityType => {
                        const option = document.createElement('option');
                        option.value = entityType;
                        const displayName = entityType
                            .replace(/_/g, ' ')
                            .replace(/\b\w/g, l => l.toUpperCase());
                        option.textContent = displayName;
                        entityTypeFilter.appendChild(option);
                    });
                }
            })
            .catch(error => {
                console.error('Fallback also failed:', error);
            });
    }
    
    // ✅ FIX 2: LOAD ACTIVITY LOGS FUNCTION (SYSTEM/ADMIN EXCLUDE)
    function loadActivityLogs() {
        console.log('Loading USER activity logs (System/Admin excluded)...');
        
        // Show loading
        activityLogsBody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px;">Loading user activities...</td></tr>';
        emptyState.style.display = 'none';
        
        // Build query
        const username = document.getElementById('usernameFilter').value;
        const entityType = document.getElementById('entityTypeFilter').value;
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        
        // ✅ FIX: Use USER ACTIVITY LOGS endpoint
        let url = '/api/user_activity_logs?limit=100';
        if (username) url += `&username=${encodeURIComponent(username)}`;
        if (entityType) url += `&entity_type=${encodeURIComponent(entityType)}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;
        
        console.log('Fetching USER activities URL:', url);
        
        fetch(url)
            .then(response => {
                console.log('Response status:', response.status, response.statusText);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Received USER activity data:', data);
                
                if (data.success && data.logs && data.logs.length > 0) {
                    displayLogs(data.logs);
                } else {
                    // Agar user logs na mile, toh fallback karo
                    if (data.logs && data.logs.length === 0) {
                        console.log('No user logs found, trying all logs...');
                        loadAllActivityLogsFallback(username, entityType, startDate, endDate);
                    } else {
                        showEmptyState(data.message || 'No user activity logs found');
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching user logs:', error);
                // Agar new endpoint fail ho, toh old endpoint try karo
                loadAllActivityLogsFallback(username, entityType, startDate, endDate);
            });
    }
    
    // Fallback function agar user_activity_logs endpoint fail ho
    function loadAllActivityLogsFallback(username, entityType, startDate, endDate) {
        console.log('Trying fallback to all activity logs...');
        
        let url = '/api/activity_logs?limit=100';
        if (username) url += `&username=${encodeURIComponent(username)}`;
        if (entityType) url += `&entity_type=${encodeURIComponent(entityType)}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.logs && data.logs.length > 0) {
                    // Manually filter out System and Admin
                    const filteredLogs = data.logs.filter(log => 
                        !['System', 'Admin', 'system', 'admin'].includes(log.username)
                    );
                    
                    if (filteredLogs.length > 0) {
                        displayLogs(filteredLogs);
                    } else {
                        showEmptyState('No user activity logs found (System/Admin excluded)');
                    }
                } else {
                    showEmptyState(data.message || 'No activity logs found');
                }
            })
            .catch(error => {
                console.error('Fallback also failed:', error);
                showEmptyState(`Error: ${error.message}`);
            });
    }
    
    // Display logs in table
    function displayLogs(logs) {
        console.log(`Displaying ${logs.length} USER logs`);
        
        activityLogsBody.innerHTML = '';
        emptyState.style.display = 'none';
        
        logs.forEach(log => {
            const row = document.createElement('tr');
            
            let timestampText = 'N/A';
            if (log.timestamp) {
                try {
                    const date = new Date(log.timestamp);
                    timestampText = date.toLocaleString();
                } catch (e) {
                    timestampText = log.timestamp;
                }
            }
            
            // Format entity type
            const entityType = log.entity_type || 'N/A';
            const entityTypeDisplay = entityType
                .replace(/_/g, ' ')
                .replace(/\b\w/g, l => l.toUpperCase());
            
            row.innerHTML = `
                <td>${timestampText}</td>
                <td><strong>${log.username || 'Unknown'}</strong></td>
                <td>${log.action || 'No action'}</td>
                <td><span class="log-entity">${entityTypeDisplay}</span></td>
                <td>
                    ${log.details ? `<div class="log-details">${log.details}</div>` : ''}
                    ${log.entity_id ? `<div class="log-details"><small>ID: ${log.entity_id}</small></div>` : ''}
                </td>
            `;
            
            activityLogsBody.appendChild(row);
        });
    }
    
    // Show empty state
    function showEmptyState(message = 'No user activity logs found') {
        console.log('Showing empty state:', message);
        activityLogsBody.innerHTML = '';
        emptyState.style.display = 'block';
        emptyState.innerHTML = `
            <i class="fas fa-history"></i>
            <h3>${message}</h3>
        `;
    }
    
    // Test API connection
    function testApiConnection() {
        console.log('Testing API connection...');
        
        // Pehle naya endpoint try karo
        fetch('/api/user_activity_logs?limit=3')
            .then(response => {
                console.log('USER API Response Status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('USER API Response Data:', data);
                if (data.success) {
                    console.log(`✅ USER API Success! Found ${data.logs.length} user logs`);
                    if (data.logs.length > 0) {
                        console.log('Sample user log:', data.logs[0]);
                    }
                } else {
                    console.error('❌ USER API Error:', data.message);
                    // Test old endpoint
                    testOldApi();
                }
            })
            .catch(error => {
                console.error('❌ USER API Fetch Error:', error);
                testOldApi();
            });
    }
    
    function testOldApi() {
        fetch('/api/activity_logs?limit=3')
            .then(response => response.json())
            .then(data => {
                console.log('OLD API data:', data);
            });
    }
    
    // Test API on load
    testApiConnection();
});