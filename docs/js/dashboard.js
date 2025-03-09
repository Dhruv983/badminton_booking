document.addEventListener('DOMContentLoaded', function() {
    // Fetch configuration
    fetchConfig();
    
    // Fetch latest results
    fetchLatestResults();
    
    // Fetch booking history
    fetchBookingHistory();
    
    // Update countdown timer
    updateNextRunCountdown();
    setInterval(updateNextRunCountdown, 1000);
});

function fetchConfig() {
    fetch('../config.ini')
        .then(response => {
            if (!response.ok) {
                throw new Error('Config file not found');
            }
            return response.text();
        })
        .then(data => {
            // Display the raw config.ini content
            document.getElementById('configDisplay').textContent = data;
            
            // Parse config.ini to extract user information
            const users = parseConfigIni(data);
            
            // Update the next bookings list
            updateNextBookingsList(users);
        })
        .catch(error => {
            console.error('Error fetching config:', error);
            document.getElementById('configDisplay').textContent = 
                'Error loading configuration: ' + error.message;
        });
}

function parseConfigIni(iniContent) {
    const users = {};
    let currentUser = null;
    let sectionType = null;
    
    // Split by lines
    const lines = iniContent.split('\n');
    
    for (const line of lines) {
        const trimmedLine = line.trim();
        
        // Skip comments and empty lines
        if (trimmedLine === '' || trimmedLine.startsWith(';')) {
            continue;
        }
        
        // Check for section headers like [USER1_LOGIN] or [USER1_BOOKING]
        const sectionMatch = trimmedLine.match(/^\[(USER\d+)_(LOGIN|BOOKING)\]$/);
        if (sectionMatch) {
            currentUser = sectionMatch[1];
            sectionType = sectionMatch[2].toLowerCase();
            
            // Create user object if it doesn't exist
            if (!users[currentUser]) {
                users[currentUser] = {
                    login: {},
                    booking: {}
                };
            }
            continue;
        }
        
        // Process key-value pairs
        const kvMatch = trimmedLine.match(/^([^=]+)=(.*)$/);
        if (kvMatch && currentUser && sectionType) {
            const key = kvMatch[1].trim();
            const value = kvMatch[2].trim();
            
            // Add to the appropriate section
            users[currentUser][sectionType][key] = value;
        }
    }
    
    return users;
}

function updateNextBookingsList(users) {
    const container = document.getElementById('nextBookingsList');
    
    if (!users || Object.keys(users).length === 0) {
        container.innerHTML = '<div class="alert alert-warning">No user configurations found!</div>';
        return;
    }
    
    // Calculate next booking date (6 days from now)
    const today = new Date();
    const nextBookingDate = new Date(today.setDate(today.getDate() + 6));
    const dateStr = nextBookingDate.toISOString().split('T')[0]; // YYYY-MM-DD format
    
    // Update the next booking date display
    document.getElementById('nextBookingDate').innerText = formatDate(dateStr);
    
    let html = '<div class="list-group">';
    
    // Add each user's booking details
    for (const userId in users) {
        const user = users[userId];
        
        // Skip users without booking info
        if (!user.booking || !user.booking.time || !user.booking.facility) {
            continue;
        }
        
        const facility = user.booking.facility || 'Unknown';
        const time = user.booking.time || 'Unknown';
        const username = user.login.username || userId;
        
        html += `
            <div class="list-group-item">
                <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">${username}</h5>
                    <span class="time-badge">${time}</span>
                </div>
                <p class="mb-1">${capitalizeFirstLetter(facility)}</p>
                <small class="text-muted">Court to be booked on ${formatDate(dateStr)}</small>
            </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
}

function fetchLatestResults() {
    fetch('results/latest.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('No results available yet');
            }
            return response.json();
        })
        .then(data => {
            displayLatestResults(data);
        })
        .catch(error => {
            console.log('No results yet:', error);
            document.getElementById('latestResultsContainer').innerHTML = 
                '<div class="alert alert-info">No booking results available yet. The first booking attempt will occur at 12:00:30 AM.</div>';
        });
}

function displayLatestResults(results) {
    const container = document.getElementById('latestResultsContainer');
    
    if (!results || !results.date) {
        container.innerHTML = '<div class="alert alert-info">No booking results available yet.</div>';
        return;
    }
    
    let html = `
        <div class="d-flex justify-content-between mb-3">
            <h6>Results for: ${formatDate(results.date)}</h6>
            <small class="text-muted">${formatTimestamp(results.timestamp)}</small>
        </div>
    `;
    
    if (!results.users || Object.keys(results.users).length === 0) {
        html += '<div class="alert alert-warning">No booking attempts were recorded.</div>';
    } else {
        html += '<div class="list-group">';
        
        for (const userId in results.users) {
            const result = results.users[userId];
            const success = result.success;
            
            html += `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <span>${userId}</span>
                        <span class="badge ${success ? 'bg-success' : 'bg-danger'}">
                            ${success ? 'Success' : 'Failed'}
                        </span>
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
    }
    
    container.innerHTML = html;
}

function fetchBookingHistory() {
    // We'll use GitHub API to list all files in the results directory
    fetch('results/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Cannot access results directory');
            }
            
            // Since we can't list directory contents easily,
            // we'll try fetching recent dates directly
            const dates = [];
            const today = new Date();
            
            // Try the last 10 days
            for (let i = 0; i < 10; i++) {
                const date = new Date(today);
                date.setDate(date.getDate() - i);
                dates.push(date.toISOString().split('T')[0]); // YYYY-MM-DD
            }
            
            return Promise.all(dates.map(date => 
                fetch(`results/results_${date}.json`)
                    .then(resp => resp.ok ? resp.json() : null)
                    .catch(() => null)
            ));
        })
        .then(results => {
            // Filter out null results
            const validResults = results.filter(result => result !== null);
            displayBookingHistory(validResults);
        })
        .catch(error => {
            console.error('Error fetching history:', error);
            document.getElementById('historyList').innerHTML = 
                '<div class="alert alert-warning">Could not load booking history.</div>';
        });
}

function displayBookingHistory(historyItems) {
    const container = document.getElementById('historyList');
    
    if (!historyItems || historyItems.length === 0) {
        container.innerHTML = '<div class="alert alert-info">No booking history available yet.</div>';
        return;
    }
    
    // Sort history by date (newest first)
    historyItems.sort((a, b) => new Date(b.date) - new Date(a.date));
    
    let html = '';
    
    historyItems.forEach(item => {
        const users = item.users || {};
        const userCount = Object.keys(users).length;
        const successCount = Object.values(users).filter(u => u.success).length;
        
        html += `
            <div class="list-group-item">
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${formatDate(item.date)}</h6>
                    <small>${formatTimestamp(item.timestamp)}</small>
                </div>
                <p class="mb-1">
                    <span class="badge bg-success">${successCount} Successful</span>
                    <span class="badge bg-danger">${userCount - successCount} Failed</span>
                    <span class="badge bg-secondary">${userCount} Total Attempts</span>
                </p>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function updateNextRunCountdown() {
    const now = new Date();
    const nextRun = new Date(now);
    
    // If it's already past midnight, set for next day
    if (now.getHours() >= 0 && now.getMinutes() > 0) {
        nextRun.setDate(nextRun.getDate() + 1);
    }
    
    // Set to 12:00:30 AM
    nextRun.setHours(0, 0, 30, 0);
    
    // Calculate time difference
    const diff = nextRun - now;
    
    // Convert to hours, minutes, seconds
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);
    
    // Update the countdown element
    const countdownElement = document.getElementById('nextRunCountdown');
    countdownElement.innerHTML = `Next booking run in: ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

// Helper functions
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
        weekday: 'short',
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}

function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

function capitalizeFirstLetter(string) {
    if (!string) return '';
    return string.charAt(0).toUpperCase() + string.slice(1);
}