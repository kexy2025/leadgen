// ============================================
// LEAD MANAGEMENT PLATFORM - FRONTEND LOGIC
// ============================================

// Global State
let currentView = 'dashboard';
let currentPage = 1;
let leadsPerPage = 25;
let allLeads = [];
let filteredLeads = [];
let unknownHeaders = [];

// ========== INITIALIZATION ==========
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Lead Management Platform Initialized');
    
    // Setup navigation
    setupNavigation();
    
    // Setup file upload
    setupFileUpload();
    
    // Load initial data
    loadStats();
    loadLeads();
    loadConfig();
    
    // Setup search and filters
    setupSearchAndFilters();
});

// ========== NAVIGATION ==========
function setupNavigation() {
    const navTabs = document.querySelectorAll('.nav-tab');
    
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const view = tab.getAttribute('data-view');
            showView(view);
        });
    });
}

function showView(viewName) {
    // Update active tab
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.getAttribute('data-view') === viewName) {
            tab.classList.add('active');
        }
    });
    
    // Update active view
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    
    const targetView = document.getElementById(`${viewName}-view`);
    if (targetView) {
        targetView.classList.add('active');
        currentView = viewName;
        
        // Load data for specific views
        if (viewName === 'leads') {
            loadLeads();
        } else if (viewName === 'config') {
            loadConfig();
        }
    }
}

// ========== DATA LOADING ==========
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        document.getElementById('totalLeads').textContent = data.total_leads || 0;
        document.getElementById('activeLeads').textContent = data.active_leads || 0;
        document.getElementById('duplicates').textContent = data.duplicates || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadLeads() {
    try {
        const response = await fetch('/api/leads');
        const data = await response.json();
        
        allLeads = data.leads || [];
        filteredLeads = [...allLeads];
        renderLeads();
    } catch (error) {
        console.error('Error loading leads:', error);
        showToast('Failed to load leads', 'error');
    }
}

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        renderConfig(data);
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// ========== FILE UPLOAD ==========
function setupFileUpload() {
    const fileInput = document.getElementById('fileInput');
    const dropZone = document.getElementById('dropZone');
    
    // File input change
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });
    
    // Drag and drop
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        
        const file = e.dataTransfer.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });
}

async function handleFileUpload(file) {
    // Validate file type
    const validTypes = ['.csv', '.xlsx', '.xls'];
    const fileName = file.name.toLowerCase();
    const isValid = validTypes.some(type => fileName.endsWith(type));
    
    if (!isValid) {
        showToast('Invalid file type. Please upload CSV or Excel files.', 'error');
        return;
    }
    
    // Show file info
    const fileInfo = document.getElementById('fileInfo');
    fileInfo.style.display = 'block';
    fileInfo.innerHTML = `
        <strong>📄 ${file.name}</strong><br>
        Size: ${(file.size / 1024).toFixed(2)} KB
    `;
    
    // Show progress
    const progressDiv = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    progressDiv.style.display = 'block';
    progressFill.style.width = '20%';
    progressText.textContent = 'Uploading file...';
    
    // Upload file
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        progressFill.style.width = '50%';
        progressText.textContent = 'Processing headers...';
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.unknown_headers && result.unknown_headers.length > 0) {
            // Show mapping modal
            progressFill.style.width = '75%';
            progressText.textContent = 'Unknown headers detected. Please map them...';
            
            showMappingModal(result.unknown_headers, file);
        } else {
            // Process complete
            progressFill.style.width = '100%';
            progressText.textContent = 'Complete!';
            
            setTimeout(() => {
                progressDiv.style.display = 'none';
                showUploadResults(result);
                loadStats();
                loadLeads();
            }, 1000);
        }
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Upload failed. Please try again.', 'error');
        progressDiv.style.display = 'none';
    }
}

async function importFromSheets() {
    const urlInput = document.getElementById('sheetsUrl');
    const url = urlInput.value.trim();
    
    if (!url) {
        showToast('Please enter a Google Sheets URL', 'warning');
        return;
    }
    
    if (!url.includes('docs.google.com/spreadsheets')) {
        showToast('Invalid Google Sheets URL', 'error');
        return;
    }
    
    showToast('Importing from Google Sheets...', 'info');
    
    try {
        const response = await fetch('/api/import-sheets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(`Successfully imported ${result.leads_added} leads!`, 'success');
            loadStats();
            loadLeads();
            urlInput.value = '';
        } else {
            showToast(result.error || 'Import failed', 'error');
        }
    } catch (error) {
        console.error('Import error:', error);
        showToast('Import failed. Please check the URL and try again.', 'error');
    }
}

// ========== MAPPING MODAL ==========
function showMappingModal(headers, file) {
    unknownHeaders = headers;
    const modal = document.getElementById('mappingModal');
    const mappingList = document.getElementById('mappingList');
    
    // Clear previous mappings
    mappingList.innerHTML = '';
    
    // Create mapping items
    headers.forEach((header, index) => {
        const item = document.createElement('div');
        item.className = 'mapping-item';
        item.innerHTML = `
            <strong>Unknown Header: "${header.original}"</strong>
            <p style="font-size: 13px; color: var(--gray-600); margin: 4px 0;">
                Sample values: ${header.samples.slice(0, 3).join(', ')}
            </p>
            <select id="mapping-${index}" class="mapping-select">
                <option value="">-- Select mapping --</option>
                ${header.suggestions.map(s => `
                    <option value="${s.column}">${s.column} (${(s.confidence * 100).toFixed(0)}% match)</option>
                `).join('')}
                <option value="__create_new__">➕ Create New Column</option>
                <option value="__skip__">⏭️ Skip this header</option>
            </select>
        `;
        
        mappingList.appendChild(item);
    });
    
    modal.style.display = 'flex';
}

function closeMappingModal() {
    const modal = document.getElementById('mappingModal');
    modal.style.display = 'none';
}

async function applyMappings() {
    const mappings = {};
    
    unknownHeaders.forEach((header, index) => {
        const select = document.getElementById(`mapping-${index}`);
        const value = select.value;
        
        if (value && value !== '__skip__') {
            mappings[header.original] = value;
        }
    });
    
    // Send mappings to backend
    try {
        const response = await fetch('/api/apply-mappings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ mappings })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Mappings applied successfully!', 'success');
            closeMappingModal();
            
            // Update progress and complete
            const progressDiv = document.getElementById('uploadProgress');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            
            progressFill.style.width = '100%';
            progressText.textContent = 'Complete!';
            
            setTimeout(() => {
                progressDiv.style.display = 'none';
                showUploadResults(result);
                loadStats();
                loadLeads();
            }, 1000);
        } else {
            showToast('Failed to apply mappings', 'error');
        }
    } catch (error) {
        console.error('Mapping error:', error);
        showToast('Failed to apply mappings', 'error');
    }
}

// ========== LEADS RENDERING ==========
function renderLeads() {
    const tbody = document.getElementById('leadsTableBody');
    
    if (filteredLeads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No leads found</td></tr>';
        return;
    }
    
    const startIndex = (currentPage - 1) * leadsPerPage;
    const endIndex = startIndex + leadsPerPage;
    const pageLeads = filteredLeads.slice(startIndex, endIndex);
    
    tbody.innerHTML = pageLeads.map(lead => `
        <tr>
            <td>${lead.Name || '-'}</td>
            <td>${lead.Email || '-'}</td>
            <td>${lead.Title || '-'}</td>
            <td>${lead.Company_Name || '-'}</td>
            <td>${lead.Mobile_Phone || lead.Company_Phone || '-'}</td>
            <td>
                <span style="
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: 500;
                    background: ${getStatusColor(lead.Lead_Status)};
                    color: white;
                ">
                    ${lead.Lead_Status || 'Active'}
                </span>
            </td>
            <td>${lead.Date_Added ? new Date(lead.Date_Added).toLocaleDateString() : '-'}</td>
        </tr>
    `).join('');
    
    updatePagination();
}

function getStatusColor(status) {
    const colors = {
        'Active': '#10b981',
        'Duplicate': '#ef4444',
        'Suppressed': '#6b7280',
        'Converted': '#3b82f6'
    };
    return colors[status] || '#6b7280';
}

function updatePagination() {
    const totalPages = Math.ceil(filteredLeads.length / leadsPerPage);
    document.getElementById('pageInfo').textContent = `Page ${currentPage} of ${totalPages}`;
}

function nextPage() {
    const totalPages = Math.ceil(filteredLeads.length / leadsPerPage);
    if (currentPage < totalPages) {
        currentPage++;
        renderLeads();
    }
}

function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        renderLeads();
    }
}

// ========== SEARCH & FILTERS ==========
function setupSearchAndFilters() {
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    
    searchInput.addEventListener('input', (e) => {
        applyFilters();
    });
    
    statusFilter.addEventListener('change', (e) => {
        applyFilters();
    });
}

function applyFilters() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;
    
    filteredLeads = allLeads.filter(lead => {
        // Search filter
        const matchesSearch = !searchTerm || 
            Object.values(lead).some(val => 
                String(val).toLowerCase().includes(searchTerm)
            );
        
        // Status filter
        const matchesStatus = !statusFilter || lead.Lead_Status === statusFilter;
        
        return matchesSearch && matchesStatus;
    });
    
    currentPage = 1;
    renderLeads();
}

// ========== CONFIG RENDERING ==========
function renderConfig(config) {
    const columnsDiv = document.getElementById('columnsConfig');
    const aliasesDiv = document.getElementById('aliasesConfig');
    
    if (!config || !config.columns) {
        columnsDiv.innerHTML = '<div class="loading">No configuration found</div>';
        return;
    }
    
    // Render columns
    columnsDiv.innerHTML = config.columns.map(col => `
        <div class="config-item">
            <span><strong>${col}</strong></span>
            <span style="font-size: 12px; color: var(--gray-500);">Canonical Column</span>
        </div>
    `).join('');
    
    // Render aliases
    if (config.aliases) {
        aliasesDiv.innerHTML = Object.entries(config.aliases).map(([column, aliases]) => `
            <div class="alias-item">
                <strong>${column}</strong>
                <span>${aliases.join(', ')}</span>
            </div>
        `).join('');
    }
}

// ========== EXPORT ==========
async function exportLeads() {
    try {
        showToast('Preparing export...', 'info');
        
        const response = await fetch('/api/export');
        const blob = await response.blob();
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `leads_export_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showToast('Export complete!', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Export failed', 'error');
    }
}

// ========== UPLOAD RESULTS ==========
function showUploadResults(result) {
    const resultsDiv = document.getElementById('uploadResults');
    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML = `
        <h3 style="margin-bottom: 12px;">✅ Upload Complete</h3>
        <div style="display: grid; gap: 8px;">
            <div><strong>Leads Added:</strong> ${result.leads_added || 0}</div>
            <div><strong>Duplicates Skipped:</strong> ${result.duplicates_skipped || 0}</div>
            <div><strong>Total Processed:</strong> ${result.total_processed || 0}</div>
        </div>
        <button class="btn btn-primary" onclick="showView('leads')" style="margin-top: 16px;">
            View Leads
        </button>
    `;
}

// ========== TOAST NOTIFICATIONS ==========
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => {
            container.removeChild(toast);
        }, 300);
    }, 3000);
}

// ========== UTILITY FUNCTIONS ==========
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatNumber(num) {
    if (!num) return '0';
    return num.toLocaleString();
}

// Make functions globally available
window.showView = showView;
window.nextPage = nextPage;
window.prevPage = prevPage;
window.exportLeads = exportLeads;
window.importFromSheets = importFromSheets;
window.closeMappingModal = closeMappingModal;
window.applyMappings = applyMappings;
