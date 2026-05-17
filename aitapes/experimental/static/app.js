/* AITAPES Dashboard — Frontend Logic */

// State
let currentFilter = 'all';
let refreshInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupFilterTabs();
    refreshData();
    startAutoRefresh();
});

// Auto-refresh every 5 seconds
function startAutoRefresh() {
    refreshInterval = setInterval(refreshData, 5000);
}

// Fetch all data
async function refreshData() {
    await Promise.all([
        loadStats(),
        loadLedger(),
        loadContract(),
    ]);
}

// Load statistics
async function loadStats() {
    try {
        const resp = await fetch('/api/stats');
        const stats = await resp.json();

        document.getElementById('stat-plans').textContent = stats.total_plans || 0;
        document.getElementById('stat-builds').textContent = stats.total_builds || 0;
        document.getElementById('stat-checks').textContent = stats.total_checks || 0;

        const passRate = stats.pass_rate || 0;
        document.getElementById('stat-pass-rate').textContent = `${(passRate * 100).toFixed(0)}%`;

        // Update pressure visualization based on stats
        updatePressure(stats);
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

// Load ledger entries
async function loadLedger() {
    try {
        const resp = await fetch('/api/ledger');
        const entries = await resp.json();

        const list = document.getElementById('ledger-list');
        if (entries.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <p>No activity yet.</p>
                </div>
            `;
            return;
        }

        // Filter entries
        const filtered = currentFilter === 'all'
            ? entries
            : entries.filter(e => e.entry_type === currentFilter);

        // Render entries (most recent first)
        list.innerHTML = filtered.reverse().slice(0, 20).map(entry => `
            <div class="ledger-item">
                <div class="ledger-item-header">
                    <span class="ledger-item-type ${entry.entry_type}">${entry.entry_type}</span>
                    <span class="ledger-item-time">${formatTime(entry.timestamp)}</span>
                </div>
                <div class="ledger-item-summary">${escapeHtml(entry.output_summary)}</div>
                <div class="ledger-item-hash">hash: ${entry.input_hash}</div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load ledger:', e);
    }
}

// Load contract
async function loadContract() {
    try {
        const resp = await fetch('/contract');
        const contract = await resp.json();

        const view = document.getElementById('contract-view');
        const status = document.getElementById('contract-status');

        if (!contract.intent) {
            view.innerHTML = `
                <div class="empty-state">
                    <p>No contract loaded.</p>
                    <p class="hint">Run <code>tapes plan</code> to create one.</p>
                </div>
            `;
            status.textContent = 'No contract';
            status.className = 'badge';
            return;
        }

        status.textContent = 'Active';
        status.className = 'badge badge-success';

        let html = `<div class="contract-intent">${escapeHtml(contract.intent)}</div>`;

        if (contract.constraints && contract.constraints.length > 0) {
            html += `
                <div class="contract-section">
                    <h3>Constraints</h3>
                    <ul class="contract-list">
                        ${contract.constraints.map(c => `<li>${escapeHtml(c)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        if (contract.success_criteria && contract.success_criteria.length > 0) {
            html += `
                <div class="contract-section">
                    <h3>Success Criteria</h3>
                    <ul class="contract-list">
                        ${contract.success_criteria.map(c => `<li>${escapeHtml(c)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        if (contract.missing_information && contract.missing_information.length > 0) {
            html += `
                <div class="contract-section">
                    <h3>Missing Information</h3>
                    <ul class="contract-list">
                        ${contract.missing_information.map(m => `<li>⚠ ${escapeHtml(m)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        html += `
            <div class="contract-section">
                <h3>Metadata</h3>
                <ul class="contract-list">
                    <li>Stakes: <strong>${contract.stakes || 'low'}</strong></li>
                    <li>Mutation: <strong>${contract.mutation_boundary || 'local_edit'}</strong></li>
                    ${contract.target_files && contract.target_files.length > 0
                        ? `<li>Target files: ${contract.target_files.join(', ')}</li>`
                        : ''}
                </ul>
            </div>
        `;

        view.innerHTML = html;
    } catch (e) {
        console.error('Failed to load contract:', e);
    }
}

// Update pressure visualization
function updatePressure(stats) {
    const fills = document.querySelectorAll('.pressure-fill');
    const values = document.querySelectorAll('.pressure-value');

    // Simulate pressure based on stats (in real implementation, this comes from the kernel)
    const pressures = [
        Math.min(1, (stats.total_builds || 0) * 0.1),  // Mutation entropy
        Math.random() * 0.3,                            // Contradiction
        Math.min(1, (stats.total_checks || 0) * 0.05), // Branch pressure
        Math.random() * 0.2,                            // Scope bleeding
        Math.random() * 0.15,                           // Rep mismatch
        1 - (stats.pass_rate || 0),                     // Validation volatility
        Math.min(1, (stats.total_builds || 0) * 0.08), // Topology
        Math.random() * 0.25,                           // Ledger pressure
    ];

    fills.forEach((fill, i) => {
        if (i < pressures.length) {
            fill.style.width = `${pressures[i] * 100}%`;
            // Color based on pressure level
            if (pressures[i] > 0.7) {
                fill.style.background = 'linear-gradient(90deg, #ff4466, #ff6688)';
            } else if (pressures[i] > 0.4) {
                fill.style.background = 'linear-gradient(90deg, #ffaa00, #ffcc44)';
            } else {
                fill.style.background = 'linear-gradient(90deg, var(--accent), #00ff88)';
            }
        }
    });

    values.forEach((val, i) => {
        if (i < pressures.length) {
            val.textContent = pressures[i].toFixed(2);
        }
    });
}

// Setup filter tabs
function setupFilterTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentFilter = tab.dataset.filter;
            loadLedger();
        });
    });
}

// Format timestamp
function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    const now = new Date();
    const diff = now - d;

    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
}

// Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
