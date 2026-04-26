"""
Replace the entire REAL-TIME ALERTS SYSTEM block in supervisor_dashboard.html
with a robust fetch-based polling implementation.
"""

with open('templates/police/supervisor_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# ── Locate the block to replace ──────────────────────────────────────────────
alert_section_header = '// REAL-TIME ALERTS SYSTEM'
connect_stream_fn = '        function connectAlertStream() {'

header_pos = content.find(alert_section_header)
assert header_pos != -1, 'Could not find REAL-TIME ALERTS SYSTEM marker'

# Walk back to the opening //=== line
block_start = content.rfind('\n        // ====', 0, header_pos)
assert block_start != -1, 'Could not find opening separator'

connect_fn_pos = content.find(connect_stream_fn, header_pos)
assert connect_fn_pos != -1, 'Could not find connectAlertStream function'

# Find closing brace of connectAlertStream
brace = 0
started = False
i = connect_fn_pos
while i < len(content):
    ch = content[i]
    if ch == '{':
        brace += 1
        started = True
    elif ch == '}' and started:
        brace -= 1
        if brace == 0:
            block_end = i + 1
            break
    i += 1

old_block = content[block_start:block_end]
print(f'Replacing {len(old_block)} chars ({block_start}:{block_end})')

# ── Replacement ───────────────────────────────────────────────────────────────
new_block = r"""
        // ============================================================================
        // REAL-TIME ALERTS SYSTEM
        // Fetch-based polling — reliable, no SSE buffering/auth issues.
        // ============================================================================
        let activeAlerts = [];          // [{alert_id, severity, message, timestamp}]
        let seenAlertIds = new Set();   // Prevents duplicates across polls
        let unreadAlertCount = 0;
        let alertPollTimer = null;

        function playAlertBeep(frequency = 800, duration = 200) {
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                oscillator.frequency.value = frequency;
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration / 1000);
                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + duration / 1000);
            } catch (e) {
                console.warn('Web Audio API not available:', e);
            }
        }

        function getSeverityIcon(severity) {
            const s = String(severity || 'low').toLowerCase();
            if (s === 'critical') return '🚨';
            if (s === 'high')     return '⚠️';
            if (s === 'medium')   return 'ℹ️';
            return '✓';
        }

        function updateAlertBadge() {
            const badge = document.getElementById('alert-badge');
            if (!badge) return;
            if (unreadAlertCount > 0) {
                badge.textContent = unreadAlertCount > 99 ? '99+' : unreadAlertCount;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }

        function addAlertToList(alert) {
            if (seenAlertIds.has(alert.alert_id)) return; // skip duplicate
            seenAlertIds.add(alert.alert_id);

            const alertsList = document.getElementById('alerts-list');
            const emptyState = document.getElementById('alerts-empty');
            if (!alertsList) return;

            const alertItem = document.createElement('div');
            alertItem.className = `alert-item ${alert.severity || 'low'}`;
            alertItem.dataset.alertId = alert.alert_id;

            const timestamp = new Date(alert.timestamp);
            const timeStr = isNaN(timestamp) ? '' : timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            alertItem.innerHTML = `
                <div class="alert-content">
                    <div class="alert-header-row">
                        <span class="alert-severity-icon">${getSeverityIcon(alert.severity)}</span>
                        <span class="alert-message">${escapeHtml(alert.message)}</span>
                        <button class="alert-dismiss-btn" onclick="dismissAlert('${alert.alert_id}')" title="Dismiss">×</button>
                    </div>
                    <div class="alert-timestamp">${timeStr}</div>
                </div>
            `;

            if (alertsList.firstChild) {
                alertsList.insertBefore(alertItem, alertsList.firstChild);
            } else {
                alertsList.appendChild(alertItem);
            }

            if (emptyState) emptyState.style.display = 'none';

            activeAlerts.unshift(alert);
            if (activeAlerts.length > 100) {
                activeAlerts = activeAlerts.slice(0, 100);
                const items = alertsList.querySelectorAll('.alert-item');
                if (items.length > 100) items[items.length - 1].remove();
            }

            // Sound cues
            if (alert.severity === 'critical') {
                playAlertBeep(1000, 300);
                setTimeout(() => playAlertBeep(1000, 300), 400);
            } else if (alert.severity === 'high') {
                playAlertBeep(800, 200);
            }
        }

        function dismissAlert(alertId) {
            const alertItem = document.querySelector(`[data-alert-id="${alertId}"]`);
            if (alertItem) {
                alertItem.style.animation = 'slideOut 0.3s ease forwards';
                setTimeout(() => alertItem.remove(), 300);
                unreadAlertCount = Math.max(0, unreadAlertCount - 1);
                updateAlertBadge();
                const alertsList = document.getElementById('alerts-list');
                const emptyState = document.getElementById('alerts-empty');
                if (alertsList && alertsList.children.length === 0 && emptyState) {
                    emptyState.style.display = 'block';
                }
            }
        }

        function toggleAlertSidebar() {
            const sidebar = document.getElementById('alert-sidebar');
            sidebar.classList.toggle('open');
            if (sidebar.classList.contains('open')) {
                // Mark all as read when sidebar is opened
                unreadAlertCount = 0;
                updateAlertBadge();
                // Immediately fetch latest alerts
                fetchAlerts();
            }
        }

        async function fetchAlerts() {
            try {
                const response = await fetch('/police/alerts/list', {
                    credentials: 'same-origin',
                    headers: { 'Accept': 'application/json' },
                    cache: 'no-store',
                });
                if (!response.ok) return;
                const payload = await response.json();
                const alerts = payload.alerts || [];
                let newCount = 0;
                alerts.forEach(alert => {
                    if (!seenAlertIds.has(alert.alert_id)) {
                        addAlertToList(alert);
                        newCount++;
                    }
                });
                if (newCount > 0) {
                    unreadAlertCount += newCount;
                    updateAlertBadge();
                }
            } catch (err) {
                console.warn('Alert fetch failed:', err);
            }
        }

        function startAlertPolling() {
            // Immediate first fetch
            fetchAlerts();
            // Poll every 8 seconds
            alertPollTimer = setInterval(fetchAlerts, 8000);
        }

        function connectAlertStream() {
            // Legacy entry-point kept so existing callers don't break.
            // Simply starts the fetch-based polling loop.
            if (alertPollTimer) return; // already running
            startAlertPolling();
        }"""

content = content[:block_start] + new_block + content[block_end:]

with open('templates/police/supervisor_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('SUCCESS: alert system replaced with fetch-based polling')
