const API_BASE = '/api';
let allConversations = [];
let allSafetyLogs = [];
let analyticsData = null;
let chartTopTopics = null;
let chartConversationsTrend = null;

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : text;
    return div.innerHTML;
}

function pluralize(count, singular, plural) {
    return count + ' ' + (count === 1 ? singular : (plural || singular + 's'));
}

function debounce(fn, delay) {
    let timer;
    return function () {
        clearTimeout(timer);
        timer = setTimeout(fn, delay);
    };
}

function getChartColor() {
    const primary = getComputedStyle(document.documentElement).getPropertyValue('--sg-primary').trim();
    return primary || '#991b1b';
}

function hexToRgba(hex, alpha) {
    const h = (hex || '').replace('#', '');
    if (h.length !== 6) return 'rgba(153,27,27,' + alpha + ')';
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
}

function getChartColorRgba(alpha) {
    return hexToRgba(getChartColor(), alpha);
}

function getChartRedShades(count) {
    const vars = ['--sg-red-800', '--sg-red-700', '--sg-red-600', '--sg-red-500'];
    const styles = getComputedStyle(document.documentElement);
    const shades = vars.map(function (v) {
        return styles.getPropertyValue(v).trim() || '#b91c1c';
    });
    const out = [];
    for (let i = 0; i < count; i++) {
        out.push(shades[i % shades.length]);
    }
    return out;
}

function updateResultCount(elementId, count) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = pluralize(count, 'result');
}

function setTableError(elementId, message, colspan) {
    const el = document.getElementById(elementId);
    if (el) el.innerHTML = '<tr><td colspan="' + colspan + '" class="empty-cell text-danger">' + escapeHtml(message) + '</td></tr>';
}

async function fetchAllPages(url) {
    const out = [];
    let nextUrl = url;
    while (nextUrl) {
        const res = await fetch(nextUrl);
        if (!res.ok) throw new Error('Request failed: ' + res.status);
        const data = await res.json();
        const list = data.results !== undefined ? data.results : (Array.isArray(data) ? data : []);
        out.push.apply(out, list);
        nextUrl = data.next || null;
    }
    return out;
}

async function loadDashboard() {
    try {
        const analyticsResponse = await fetch(API_BASE + '/analytics/summary/');
        if (!analyticsResponse.ok) throw new Error('Analytics failed: ' + analyticsResponse.status);
        analyticsData = await analyticsResponse.json() || {};

        document.getElementById('total-conversations').textContent = analyticsData.conversations_7d !== undefined ? analyticsData.conversations_7d : (analyticsData.total_conversations || 0);
        document.getElementById('total-safety-queries').textContent = analyticsData.total_safety_queries !== undefined ? analyticsData.total_safety_queries : 0;
        document.getElementById('active-users').textContent = analyticsData.active_users_7d !== undefined ? analyticsData.active_users_7d : (analyticsData.active_users || 0);
        document.getElementById('total-documents').textContent = (analyticsData.documents || []).length;

        renderTopTopicsChart(analyticsData.top_topics || []);
        renderConversationsTrendChart(analyticsData.conversations_by_day || []);
        renderDocumentStats(analyticsData.documents || []);
        renderDocumentsTable(analyticsData.documents || []);

        allConversations = await fetchAllPages(API_BASE + '/conversations/?page_size=100');
        allSafetyLogs = await fetchAllPages(API_BASE + '/safety-logs/?page_size=100');

        filterConversations();
        renderSafetyLogsTable(allSafetyLogs);
    } catch (error) {
        console.error('Error loading dashboard:', error);
        const msg = 'Failed to load data';
        try {
            setTableError('conversations-table', msg, 4);
            setTableError('safety-logs-table', msg, 4);
            setTableError('documents-table', msg, 4);
            setTableError('documents-stats', msg, 3);
        } catch (e) {}
    }
}

function renderTopTopicsChart(topics) {
    const ctx = document.getElementById('topTopicsChart');
    if (!ctx) return;
    if (chartTopTopics) {
        chartTopTopics.destroy();
        chartTopTopics = null;
    }
    const hasData = topics && topics.length > 0;
    const labels = hasData ? topics.map(function (t) { return (t.sources || 'Other').substring(0, 40); }) : ['No data yet'];
    const values = hasData ? topics.map(function (t) { return t.count; }) : [0];
    const barColors = getChartRedShades(labels.length);
    const borderColors = barColors.slice();
    chartTopTopics = new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Times used',
                data: values,
                backgroundColor: barColors.map(function (c) { return hexToRgba(c, 0.88); }),
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return 'Used ' + pluralize(ctx.parsed.x, 'time');
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 },
                    title: { display: true, text: 'Times used' }
                },
                y: {
                    grid: { display: false },
                    ticks: { font: { size: 12 } }
                }
            }
        }
    });
}

function renderConversationsTrendChart(data) {
    const ctx = document.getElementById('conversationsTrendChart');
    if (!ctx) return;
    if (chartConversationsTrend) {
        chartConversationsTrend.destroy();
        chartConversationsTrend = null;
    }
    const color = getChartColor();
    const colorRgba = getChartColorRgba(0.25);
    const chartCtx = ctx.getContext('2d');
    const gradient = chartCtx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, colorRgba);
    gradient.addColorStop(1, getChartColorRgba(0.02));
    const labels = (data && data.length) ? data.map(function (d) {
        return new Date(d.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    }) : [];
    const values = data ? data.map(function (d) { return d.count; }) : [];
    chartConversationsTrend = new Chart(chartCtx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Chats',
                data: values,
                borderColor: color,
                backgroundColor: gradient,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: color,
                pointBorderColor: '#fff',
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return pluralize(ctx.parsed.y, 'chat');
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    title: { display: true, text: 'Day' },
                    ticks: { font: { size: 12 } }
                },
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1, font: { size: 12 } },
                    title: { display: true, text: 'Number of chats' }
                }
            }
        }
    });
}

function renderDocumentStats(documents) {
    const tbody = document.getElementById('documents-stats');
    tbody.innerHTML = '';
    if (!documents || documents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="empty-cell">No usage data yet</td></tr>';
        return;
    }
    const total = (analyticsData && analyticsData.total_safety_queries) || 0;
    documents.forEach(function (doc) {
        const count = doc.usage_count || 0;
        const percentage = total > 0 ? Math.round((count / total) * 100) : 0;
        const row = document.createElement('tr');
        row.innerHTML = '<td><strong>' + escapeHtml(doc.title) + '</strong></td><td><span class="badge badge-red">' + pluralize(count, 'time') + '</span></td><td>' + percentage + '%</td>';
        tbody.appendChild(row);
    });
}

function renderDocumentsTable(documents) {
    const tbody = document.getElementById('documents-table');
    tbody.innerHTML = '';
    if (documents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state"><div class="empty-state-title">No safety guides yet</div><p class="empty-state-text mb-0">Upload a guide using the button above to get started.</p></td></tr>';
        return;
    }
    documents.forEach(function (doc) {
        const row = document.createElement('tr');
        const uploadDate = doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—';
        const count = doc.usage_count || 0;
        row.innerHTML = '<td><strong>' + escapeHtml(doc.title) + '</strong></td><td>' + uploadDate + '</td><td><span class="badge badge-red">' + pluralize(count, 'time') + '</span></td><td><button class="btn btn-sm btn-outline-primary" onclick="reindexDocument(' + doc.id + ')" title="Re-add this guide to the answer system (use after editing the file)">Update in system</button></td>';
        tbody.appendChild(row);
    });
}

function renderConversationsTable(conversations) {
    const tbody = document.getElementById('conversations-table');
    tbody.innerHTML = '';
    updateResultCount('conversations-result-count', conversations.length);
    if (conversations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-cell">No chats match the filters</td></tr>';
        return;
    }
    conversations.forEach(function (conv) {
        const row = document.createElement('tr');
        const time = new Date(conv.created_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
        const rawMsg = conv.message || '';
        const msg = rawMsg.length > 80 ? rawMsg.substring(0, 80) + '…' : (rawMsg || '—');
        const typeLabel = (conv.message_type || 'text');
        row.innerHTML = '<td><span class="text-muted">' + escapeHtml(time) + '</span></td><td>' + escapeHtml(conv.user_phone || '—') + '</td><td>' + escapeHtml(msg) + '</td><td><span class="badge badge-outline-red">' + escapeHtml(typeLabel) + '</span></td>';
        tbody.appendChild(row);
    });
}

function renderSafetyLogsTable(logs) {
    const tbody = document.getElementById('safety-logs-table');
    tbody.innerHTML = '';
    updateResultCount('safety-logs-result-count', logs.length);
    if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-cell">No safety answers yet</td></tr>';
        return;
    }
    logs.forEach(function (log) {
        const row = document.createElement('tr');
        const ts = log.timestamp || log.created_at || '';
        const time = ts ? new Date(ts).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : '—';
        const rawTask = log.task_description || '';
        const task = rawTask.length > 60 ? rawTask.substring(0, 60) + '…' : (rawTask || '—');
        const rawSources = log.sources || '';
        const sources = rawSources.trim() ? escapeHtml(rawSources.substring(0, 50)) + (rawSources.length > 50 ? '…' : '') : '—';
        row.innerHTML = '<td><span class="text-muted">' + escapeHtml(time) + '</span></td><td>' + escapeHtml(log.user_phone || '—') + '</td><td>' + escapeHtml(task) + '</td><td class="text-muted small">' + sources + '</td>';
        tbody.appendChild(row);
    });
}

function getSelectedConversationType() {
    const active = document.querySelector('.filter-option-type.active');
    return active ? (active.getAttribute('data-value') || '') : '';
}

function filterConversations() {
    const q = (document.getElementById('conversation-search').value || '').trim().toLowerCase();
    const typeFilter = getSelectedConversationType();
    let filtered = allConversations;
    if (typeFilter) {
        filtered = filtered.filter(function (conv) { return (conv.message_type || 'text') === typeFilter; });
    }
    if (q) {
        filtered = filtered.filter(function (conv) {
            return (conv.message || '').toLowerCase().includes(q) ||
                (conv.response || '').toLowerCase().includes(q) ||
                (conv.user_phone || '').toLowerCase().includes(q);
        });
    }
    renderConversationsTable(filtered);
}

function showUploadMessage(text, isError) {
    const el = document.getElementById('upload-doc-message');
    if (!el) return;
    el.textContent = text;
    el.classList.remove('d-none', 'alert-success', 'alert-danger');
    el.classList.add(isError ? 'alert-danger' : 'alert-success');
}

function hideUploadMessage() {
    const el = document.getElementById('upload-doc-message');
    if (el) el.classList.add('d-none');
}

function showPageSuccess(message) {
    const container = document.getElementById('page-success-toast');
    if (!container) return;
    const el = container.querySelector('.toast-message');
    if (el) el.textContent = message;
    container.classList.remove('d-none');
    setTimeout(function () {
        container.classList.add('d-none');
    }, 5000);
}

async function uploadDocument() {
    const title = (document.getElementById('doc-title').value || '').trim();
    const fileInput = document.getElementById('doc-file');
    const file = fileInput && fileInput.files && fileInput.files[0];
    hideUploadMessage();
    if (!title || !file) {
        showUploadMessage('Please provide both title and file.', true);
        return;
    }
    const submitBtn = document.getElementById('upload-doc-submit');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Uploading…';
    }
    const formData = new FormData();
    formData.append('title', title);
    formData.append('file', file);
    try {
        const response = await fetch(API_BASE + '/documents/upload/', { method: 'POST', body: formData });
        const data = await response.json();
        if (response.ok) {
            document.getElementById('upload-form').reset();
            const modalEl = document.getElementById('upload-modal');
            if (modalEl && typeof bootstrap !== 'undefined') {
                const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
                modal.hide();
            }
            hideUploadMessage();
            showPageSuccess('Safety guide added. It is now available for worker answers.');
            loadDashboard();
        } else {
            showUploadMessage('Error: ' + (data.error || 'Failed to upload document.'), true);
        }
    } catch (error) {
        showUploadMessage('Error: ' + error.message, true);
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Upload';
        }
    }
}

async function reindexDocument(docId) {
    if (!confirm('Update this guide in the answer system? This can take a moment.')) return;
    try {
        const response = await fetch(API_BASE + '/documents/' + docId + '/reindex/', { method: 'POST' });
        const data = await response.json();
        if (response.ok) {
            showPageSuccess('Guide updated in the answer system.');
            loadDashboard();
        } else {
            alert('Something went wrong: ' + (data.error || 'Could not update guide.'));
        }
    } catch (error) {
        alert('Something went wrong: ' + error.message);
    }
}

function csvSafe(value) {
    let s = (value == null ? '' : String(value)).replace(/"/g, '""');
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return '"' + s + '"';
}

function exportToCSV() {
    let csv = 'Time,Worker,Message,Type\n';
    allConversations.forEach(function (conv) {
        const time = new Date(conv.created_at).toISOString();
        csv += csvSafe(time) + ',' + csvSafe(conv.user_phone) + ',' + csvSafe(conv.message) + ',' + csvSafe(conv.message_type || 'text') + '\n';
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'safeguardai-conversations-' + new Date().toISOString().split('T')[0] + '.csv';
    a.click();
    window.URL.revokeObjectURL(url);
}

document.addEventListener('DOMContentLoaded', function () {
    loadDashboard();
    var searchInput = document.getElementById('conversation-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterConversations, 250));
    }
    document.querySelectorAll('.filter-option-type').forEach(function (el) {
        el.addEventListener('click', function (e) {
            e.preventDefault();
            const val = this.getAttribute('data-value') || '';
            document.querySelectorAll('.filter-option-type').forEach(function (o) { o.classList.remove('active'); });
            this.classList.add('active');
            const btn = document.getElementById('conversation-type-btn');
            if (btn) {
                btn.textContent = val === '' ? 'All types' : (val === 'text' ? 'Text' : (val === 'voice' ? 'Voice' : 'Image'));
            }
            filterConversations();
        });
    });
    const uploadModal = document.getElementById('upload-modal');
    if (uploadModal && typeof bootstrap !== 'undefined') {
        uploadModal.addEventListener('show.bs.modal', function () {
            hideUploadMessage();
        });
    }
});
