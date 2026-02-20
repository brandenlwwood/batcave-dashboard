/**
 * Alfred's Batcave Command Center v2
 * Phase 1: Cameras, Weather, Infra, Kanban, Health, Frigate
 * Phase 2: Scenes, Lights, Media, Activities, Voice, Chat
 */


// Fix: strip credentials from URL to prevent fetch() failures with basic auth
if (window.location.href.includes("@")) {
    window.location.replace(window.location.protocol + "//" + window.location.host + window.location.pathname + window.location.search + window.location.hash);
}

// ===== Collapsible Widgets =====
function toggleWidget(id) {
    const widget = document.getElementById(id);
    if (!widget) return;
    widget.classList.toggle('collapsed');
    saveWidgetStates();
}

function saveWidgetStates() {
    const states = {};
    document.querySelectorAll('.widget[id]').forEach(w => {
        states[w.id] = w.classList.contains('collapsed');
    });
    localStorage.setItem('batcave-widget-states', JSON.stringify(states));
}

function restoreWidgetStates() {
    try {
        const states = JSON.parse(localStorage.getItem('batcave-widget-states'));
        if (!states) {
            // First visit — collapse all except weather
            document.querySelectorAll('.widget').forEach(w => {
                if (w.id !== 'widget-weather') w.classList.add('collapsed');
            });
            return;
        }
        Object.entries(states).forEach(([id, collapsed]) => {
            const widget = document.getElementById(id);
            if (widget) {
                // Weather always expanded
                if (id === 'widget-weather') { widget.classList.remove('collapsed'); return; }
                if (collapsed) widget.classList.add('collapsed');
                else widget.classList.remove('collapsed');
            }
        });
    } catch(e) {}
}

// ===== WebSocket =====
let ws = null;
let wsRetryDelay = 1000;

function connectWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.onopen = () => {
        wsRetryDelay = 1000;
        document.getElementById('health-ws').textContent = '✓';
        setSystemStatus('online', 'ONLINE');
    };
    ws.onmessage = (evt) => {
        try { handleWsMessage(JSON.parse(evt.data)); } catch(e) {}
    };
    ws.onclose = () => {
        document.getElementById('health-ws').textContent = '✗';
        setSystemStatus('warning', 'RECONNECTING');
        setTimeout(connectWebSocket, wsRetryDelay);
        wsRetryDelay = Math.min(wsRetryDelay * 2, 30000);
    };
    ws.onerror = () => ws.close();
}

function handleWsMessage(msg) {
    switch (msg.type) {
        case 'kanban_update': renderKanban(msg.data); break;
        case 'lights_update': renderLights(msg.data); break;
        case 'media_update': renderMediaPlayers(msg.data); break;
        case 'notification': fetchNotifications(); break;
    }
}

function setSystemStatus(state, text) {
    document.getElementById('systemStatus').className = `status-pill ${state}`;
    document.getElementById('statusText').textContent = text;
}

// ===== Clock =====
function updateClock() {
    const now = new Date();
    document.getElementById('clock').textContent = now.toLocaleTimeString('en-US', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
    });
    const dateEl = document.getElementById('clockDate');
    if (dateEl) dateEl.textContent = now.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'});
}
setInterval(updateClock, 1000);
updateClock();

// ===== Camera Feeds =====
function refreshCameras() {
    const ts = Date.now();
    const c1 = document.getElementById('cam1');
    const c2 = document.getElementById('cam2');
    if (c1) c1.src = `/api/cameras/1?t=${ts}`;
    if (c2) c2.src = `/api/cameras/2?t=${ts}`;
}
setInterval(refreshCameras, 3000);

function toggleCameraFullscreen(el) {
    if (el.classList.contains('fullscreen')) {
        el.classList.remove('fullscreen');
    } else {
        el.classList.add('fullscreen');
    }
}

// ===== Weather =====
async function fetchWeather() {
    try {
        const data = await (await fetch('/api/weather')).json();
        if (data.error) return;
        document.getElementById('wx-temp').textContent = data.current.temp_f;
        document.getElementById('wx-desc').textContent = data.current.description;
        document.getElementById('wx-feels').textContent = data.current.feels_like;
        document.getElementById('wx-humidity').textContent = data.current.humidity;
        document.getElementById('wx-wind').textContent = data.current.wind_mph;
        document.getElementById('wx-today-hi').textContent = data.today.high;
        document.getElementById('wx-today-lo').textContent = data.today.low;
        document.getElementById('wx-tmrw-hi').textContent = data.tomorrow.high;
        document.getElementById('wx-tmrw-lo').textContent = data.tomorrow.low;
        document.getElementById('wx-sunrise').textContent = data.today.sunrise;
        document.getElementById('wx-sunset').textContent = data.today.sunset;
        const sugEl = document.getElementById('wx-suggestions');
        if (data.suggestion?.length) {
            sugEl.innerHTML = data.suggestion.map(s => `<div class="suggestion-item">${s}</div>`).join('');
        }
    } catch(e) { console.error('[Weather]', e); }
}

// ===== Alfred Health =====
async function fetchHealth() {
    try {
        const data = await (await fetch('/api/health')).json();
        document.getElementById('health-uptime').textContent = data.uptime || '--';
        const raw = data.memory?.raw || '';
        const memEl = document.getElementById('health-memory');
        const badge = document.getElementById('health-badge');
        const match = raw.match(/(\d+)%/);
        if (data.memory?.status === 'healthy') {
            document.getElementById('health-mem-pct').textContent = match ? match[1]+'%' : 'OK';
            memEl.className = 'health-stat ok'; badge.textContent = 'OK';
        } else if (data.memory?.status === 'warning') {
            document.getElementById('health-mem-pct').textContent = match ? match[1]+'%' : '⚠️';
            memEl.className = 'health-stat warn'; badge.textContent = 'WARN';
        } else if (data.memory?.status === 'critical') {
            document.getElementById('health-mem-pct').textContent = match ? match[1]+'%' : '🚨';
            memEl.className = 'health-stat crit'; badge.textContent = 'CRIT';
        }
    } catch(e) { console.error('[Health]', e); }
}

// ===== Infrastructure =====
const INFRA_ICONS = { unraid:'fas fa-hard-drive', proxmox:'fas fa-cubes', mikrotik:'fas fa-network-wired',
    meraki:'fas fa-wifi', homeassistant:'fas fa-home', frigate:'fas fa-eye' };
const INFRA_NAMES = { unraid:'Unraid', proxmox:'Proxmox', mikrotik:'MikroTik',
    meraki:'Meraki', homeassistant:'Home Assistant', frigate:'Frigate NVR' };

async function fetchInfra() {
    try {
        const data = await (await fetch('/api/infra/status')).json();
        document.getElementById('infra-grid').innerHTML = Object.entries(data).map(([key, info]) => {
            const icon = INFRA_ICONS[key] || 'fas fa-circle';
            const name = INFRA_NAMES[key] || key;
            let detail = info.ip || '';
            if (key === 'mikrotik' && info.cpu_load !== undefined)
                detail = `CPU: ${info.cpu_load}% | RAM: ${info.memory_used}% | v${info.version}`;
            if (key === 'meraki' && info.devices_total)
                detail = `${info.devices_online}/${info.devices_total} devices online`;
            if (key === 'frigate' && info.cameras !== undefined)
                detail = `${info.cameras} cameras`;
            return `<div class="infra-item"><div class="infra-dot ${info.status}"></div>
                <div><div class="infra-name"><i class="${icon}" style="margin-right:6px;color:var(--text-muted)"></i>${name}</div>
                <div class="infra-detail">${detail}</div></div></div>`;
        }).join('');
    } catch(e) { console.error('[Infra]', e); }
}

// ===== Frigate Events =====
async function fetchFrigateEvents() {
    try {
        const data = await (await fetch('/api/frigate/events')).json();
        const list = document.getElementById('frigate-list');
        const count = document.getElementById('frigate-count');
        if (data.error || !data.length) {
            list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:20px;">No recent events</div>';
            count.textContent = '0'; return;
        }
        count.textContent = data.length;
        list.innerHTML = data.slice(0,10).map(evt => {
            const time = evt.start ? new Date(evt.start*1000).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:true}) : '--';
            const date = evt.start ? new Date(evt.start*1000).toLocaleDateString('en-US',{month:'short',day:'numeric'}) : '';
            return `<div class="frigate-event" onclick="playClip('${evt.clip}')">
                <img class="frigate-thumb" src="${evt.thumbnail}" alt="${evt.label}" loading="lazy" onerror="this.style.display='none'">
                <div class="frigate-info"><div class="frigate-label">${evt.label||'Unknown'}</div>
                <div class="frigate-meta">${evt.camera||''} · ${date} ${time}</div></div>
                <div class="frigate-score">${Math.round(evt.score*100)}%</div></div>`;
        }).join('');
    } catch(e) { console.error('[Frigate]', e); }
}

// ===== Kanban =====
async function fetchKanban() {
    try { renderKanban(await (await fetch('/api/kanban')).json()); } catch(e) { console.error('[Kanban]', e); }
}

function renderKanban(data) {
    renderKanbanColumn('kanban-todo', data.todo || []);
    renderKanbanColumn('kanban-progress', data.in_progress || []);
    renderKanbanColumn('kanban-done', data.done || []);
}

function renderKanbanColumn(id, items) {
    const el = document.getElementById(id);
    if (!items.length) { el.innerHTML = '<div style="color:var(--text-muted);font-size:11px;text-align:center;padding:10px;">Empty</div>'; return; }
    el.innerHTML = items.map(item => {
        const p = item.priority || 'medium';
        const tags = (item.tags || []).map(t => `<span class="tag">${t}</span>`).join(' ');
        return `<div class="kanban-card priority-${p}">${item.title || item}${tags ? '<div>'+tags+'</div>' : ''}</div>`;
    }).join('');
}

// ===== Phase 2: Scenes =====
async function fetchScenes() {
    try {
        const data = await (await fetch('/api/ha/scenes')).json();
        if (data.error || !Array.isArray(data)) return;
        document.getElementById('scenes-grid').innerHTML = data.map(s => 
            `<button class="scene-btn" onclick="triggerScene('${s.entity_id}')">
                <span class="scene-icon">${s.icon || '🎭'}</span>
                <span class="scene-name">${s.name.replace(/_/g,' ')}</span>
            </button>`
        ).join('');
    } catch(e) { console.error('[Scenes]', e); }
}

async function triggerScene(entityId) {
    try {
        const btn = event.target.closest('.scene-btn');
        btn.style.transform = 'scale(0.9)';
        setTimeout(() => btn.style.transform = '', 200);
        await fetch(`/api/ha/scene/${entityId}`, { method: 'POST' });
    } catch(e) { console.error('[Scene trigger]', e); }
}

// ===== Phase 2: Lights =====
async function fetchLights() {
    try {
        const data = await (await fetch('/api/ha/lights')).json();
        if (data.error) return;
        renderLights(data);
    } catch(e) { console.error('[Lights]', e); }
}

function renderLights(data) {
    const grid = document.getElementById('lights-grid');
    if (!data || typeof data !== 'object') return;
    grid.innerHTML = Object.entries(data).map(([room, info]) => {
        const isOn = info.any_on;
        const onCount = info.lights.filter(l => l.state === 'on').length;
        const total = info.lights.length;
        // Average brightness of on lights
        const onLights = info.lights.filter(l => l.state === 'on' && l.brightness);
        const avgBright = onLights.length ? Math.round(onLights.reduce((a,l) => a + l.brightness, 0) / onLights.length) : 0;
        const brightPct = Math.round(avgBright / 255 * 100);
        return `<div class="light-room ${isOn ? 'on' : ''}" onclick="toggleRoom('${room}', ${isOn})">
            <div class="light-room-header">
                <span class="light-room-name">${room}</span>
                <span class="light-room-icon"><i class="fas fa-lightbulb"></i></span>
            </div>
            <div class="light-room-count">${onCount}/${total} on</div>
            ${isOn ? `<div class="light-room-brightness"><div class="light-room-brightness-fill" style="width:${brightPct}%"></div></div>` : ''}
        </div>`;
    }).join('');
}

async function toggleRoom(room, currentlyOn) {
    try {
        await fetch('/api/ha/light/toggle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ room, action: currentlyOn ? 'off' : 'on' })
        });
        // Refresh after small delay
        setTimeout(fetchLights, 500);
    } catch(e) { console.error('[Light toggle]', e); }
}

// ===== Phase 2: Media Players =====
async function fetchMediaPlayers() {
    try {
        const data = await (await fetch('/api/ha/media_players')).json();
        if (data.error) return;
        renderMediaPlayers(data);
    } catch(e) { console.error('[Media]', e); }
}

function renderMediaPlayers(data) {
    const list = document.getElementById('media-list');
    if (!Array.isArray(data) || !data.length) {
        list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:10px;">No media devices</div>';
        return;
    }
    // Sort: playing first, then paused, then idle, then unavailable
    const order = { playing: 0, paused: 1, idle: 2, off: 3, unavailable: 4 };
    data.sort((a, b) => (order[a.state] ?? 5) - (order[b.state] ?? 5));

    list.innerHTML = data.map(p => {
        const isActive = ['playing', 'paused'].includes(p.state);
        const stateClass = p.state === 'unavailable' ? 'unavailable' : p.state;
        const nowPlaying = p.media_title ? `${p.media_title}${p.media_artist ? ' — '+p.media_artist : ''}` : '';
        const icon = p.state === 'playing' ? 'fa-play' : p.state === 'paused' ? 'fa-pause' : 'fa-tv';
        const controls = isActive ? `
            <div class="media-controls">
                <button class="media-ctrl-btn" onclick="mediaControl('${p.entity_id}','previous')"><i class="fas fa-backward"></i></button>
                <button class="media-ctrl-btn" onclick="mediaControl('${p.entity_id}','play_pause')"><i class="fas fa-${p.state==='playing'?'pause':'play'}"></i></button>
                <button class="media-ctrl-btn" onclick="mediaControl('${p.entity_id}','next')"><i class="fas fa-forward"></i></button>
                <button class="media-ctrl-btn" onclick="mediaControl('${p.entity_id}','volume_down')"><i class="fas fa-volume-down"></i></button>
                <button class="media-ctrl-btn" onclick="mediaControl('${p.entity_id}','volume_up')"><i class="fas fa-volume-up"></i></button>
            </div>` : '';
        return `<div class="media-player ${stateClass}">
            <div class="media-player-icon"><i class="fas ${icon}"></i></div>
            <div class="media-player-info">
                <div class="media-player-name">${p.name}</div>
                ${nowPlaying ? `<div class="media-player-now">${nowPlaying}</div>` : ''}
                <div class="media-player-state">${p.state}${p.app_name ? ' · '+p.app_name : ''}${p.volume_level != null ? ' · Vol '+Math.round(p.volume_level*100)+'%' : ''}</div>
            </div>
            ${controls}
        </div>`;
    }).join('');
}

async function mediaControl(entityId, action) {
    try {
        await fetch('/api/ha/media/control', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ entity_id: entityId, action })
        });
        setTimeout(fetchMediaPlayers, 500);
    } catch(e) { console.error('[Media control]', e); }
}

// ===== Phase 2: Family Activities =====
async function fetchActivities() {
    try {
        const data = await (await fetch('/api/activities')).json();
        const list = document.getElementById('activities-list');
        if (!data.activities?.length) {
            list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:20px;">No suggestions right now</div>';
            return;
        }
        list.innerHTML = data.activities.map(a => 
            `<div class="activity-item">
                <div class="activity-icon">${a.icon}</div>
                <div class="activity-info">
                    <div class="activity-title">${a.title}</div>
                    <div class="activity-detail">${a.detail}</div>
                    <span class="activity-for ${a.for}">${a.for}</span>
                </div>
            </div>`
        ).join('');
    } catch(e) { console.error('[Activities]', e); }
}

// ===== Phase 2: Voice / Chat =====
let isListening = false;
let recognition = null;

function initVoice() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) return;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onresult = (e) => {
        const text = e.results[0][0].transcript;
        addChatMessage(text, 'user');
        sendChatMessage(text);
    };

    recognition.onend = () => {
        isListening = false;
        document.getElementById('voiceBtn').classList.remove('listening');
        document.getElementById('chatVoiceBtn').classList.remove('listening');
    };

    recognition.onerror = (e) => {
        console.error('[Voice]', e.error);
        isListening = false;
        document.getElementById('voiceBtn').classList.remove('listening');
        document.getElementById('chatVoiceBtn').classList.remove('listening');
    };
}

function toggleVoice() {
    if (!recognition) { initVoice(); if (!recognition) return; }
    if (isListening) {
        recognition.stop();
    } else {
        recognition.start();
        isListening = true;
        document.getElementById('voiceBtn').classList.add('listening');
        document.getElementById('chatVoiceBtn').classList.add('listening');
    }
}

function speakText(text) {
    if (!('speechSynthesis' in window)) return;
    // Clean text for speech - remove emoji, markdown
    const cleanText = text.replace(/[\u{1F600}-\u{1F6FF}\u{2600}-\u{2B55}\u{1F900}-\u{1F9FF}]/gu, '')
        .replace(/[*_`#]/g, '').replace(/\n/g, '. ').trim();
    if (!cleanText) return;
    
    const utter = new SpeechSynthesisUtterance(cleanText);
    utter.rate = 1.0;
    utter.pitch = 0.85;
    utter.volume = 1.0;
    
    // Try to find a good English voice — prefer British male for the Alfred vibe
    const voices = speechSynthesis.getVoices();
    const preferred = voices.find(v => 
        v.name.includes('Google UK English Male') || 
        v.name.includes('Daniel') ||
        v.name.includes('Arthur') ||
        (v.lang === 'en-GB' && v.name.toLowerCase().includes('male'))
    ) || voices.find(v => v.lang.startsWith('en') && v.name.includes('Male'))
      || voices.find(v => v.lang.startsWith('en'));
    if (preferred) utter.voice = preferred;
    
    speechSynthesis.speak(utter);
}

function sendChat() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addChatMessage(text, 'user');
    sendChatMessage(text);
}

function addChatMessage(text, sender) {
    const msgs = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `chat-msg ${sender}`;
    div.innerHTML = `<div class="chat-bubble">${escapeHtml(text)}</div>`;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
}

async function sendChatMessage(text) {
    // Show typing indicator
    const typingId = 'typing-' + Date.now();
    const msgs = document.getElementById('chat-messages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chat-msg alfred';
    typingDiv.id = typingId;
    typingDiv.innerHTML = '<div class="chat-avatar">A</div><div class="chat-bubble typing-indicator"><span></span><span></span><span></span></div>';
    msgs.appendChild(typingDiv);
    msgs.scrollTop = msgs.scrollHeight;
    
    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ message: text })
        });
        const data = await resp.json();
        
        // Remove typing indicator
        const typing = document.getElementById(typingId);
        if (typing) typing.remove();
        
        const response = data.response || data.error || "No response";
        addChatMessage(response, 'alfred');
        
        // Speak the response via TTS
        speakText(response);
    } catch(e) {
        const typing = document.getElementById(typingId);
        if (typing) typing.remove();
        addChatMessage("Connection error. Try Telegram directly.", 'alfred');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


// ===== Frigate Clip Player =====
function playClip(url) {
    // Remove existing modal if any
    const existing = document.getElementById('clip-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'clip-modal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;cursor:pointer;';
    modal.onclick = () => modal.remove();

    const video = document.createElement('video');
    video.src = url;
    video.controls = true;
    video.autoplay = true;
    video.style.cssText = 'max-width:90vw;max-height:85vh;border-radius:8px;border:1px solid #1a1d30;';
    video.onclick = (e) => e.stopPropagation();

    const closeBtn = document.createElement('div');
    closeBtn.textContent = '✕';
    closeBtn.style.cssText = 'position:absolute;top:20px;right:30px;font-size:28px;color:#d4a848;cursor:pointer;z-index:10001;';
    closeBtn.onclick = () => modal.remove();

    modal.appendChild(video);
    modal.appendChild(closeBtn);
    document.body.appendChild(modal);

    // Close on escape key
    const escHandler = (e) => {
        if (e.key === 'Escape') { modal.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}


// ===== Load Chat History =====
async function loadChatHistory() {
    try {
        const history = await (await fetch('/api/chat/history')).json();
        if (Array.isArray(history) && history.length) {
            const msgs = document.getElementById('chat-messages');
            // Clear default message
            msgs.innerHTML = '';
            // Show last 10 messages
            for (const msg of history.slice(-10)) {
                addChatMessage(msg.content, msg.role === 'user' ? 'user' : 'alfred');
            }
        }
    } catch(e) { console.error('[Chat History]', e); }
}


// ===== Calendar Widget =====
let calStartDate = null; // null = today
const CAL_WINDOW_DAYS = 30;

function calDateStr(d) {
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}
function calGetStart() {
    if (calStartDate) return new Date(calStartDate + 'T00:00:00');
    const now = new Date(); return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}
function calNav(offset) {
    const cur = calGetStart();
    cur.setDate(cur.getDate() + offset);
    calStartDate = calDateStr(cur);
    fetchCalendar();
}
function calGoToday() {
    calStartDate = null;
    fetchCalendar();
}
function calPickDate() {
    const picker = document.getElementById('cal-date-picker');
    if (picker) { picker.showPicker ? picker.showPicker() : picker.click(); }
}
function calOnDatePick(val) {
    if (val) { calStartDate = val; fetchCalendar(); }
}

async function fetchCalendar() {
    try {
        const startParam = calStartDate || calDateStr(new Date());
        const data = await (await fetch(`/api/calendar?start=${startParam}&days=${CAL_WINDOW_DAYS}`)).json();
        const view = document.getElementById('calendar-view');
        const sourcePills = document.getElementById('cal-sources');
        
        // Source pills
        if (data.sources?.length) {
            sourcePills.innerHTML = data.sources.map(s => 
                `<span class="cal-source-pill">${s}</span>`
            ).join('');
        }
        
        // Navigation bar
        const rangeStart = calGetStart();
        const rangeEnd = new Date(rangeStart);
        rangeEnd.setDate(rangeEnd.getDate() + CAL_WINDOW_DAYS - 1);
        const fmtOpts = { month: 'short', day: 'numeric' };
        const rangeLabel = rangeStart.toLocaleDateString('en-US', fmtOpts) + ' \u2013 ' + rangeEnd.toLocaleDateString('en-US', {...fmtOpts, year: 'numeric'});
        
        let navHtml = `<div class="cal-nav">
            <button class="cal-nav-btn" onclick="calNav(-${CAL_WINDOW_DAYS})" title="Previous ${CAL_WINDOW_DAYS} days"><i class="fas fa-angles-left"></i></button>
            <button class="cal-nav-btn" onclick="calNav(-7)" title="Back 1 week"><i class="fas fa-chevron-left"></i></button>
            <button class="cal-nav-btn cal-nav-today" onclick="calGoToday()" title="Jump to today"><i class="fas fa-crosshairs"></i> TODAY</button>
            <span class="cal-nav-range">${rangeLabel}</span>
            <input type="date" id="cal-date-picker" class="cal-date-picker" value="${startParam}" onchange="calOnDatePick(this.value)">
            <button class="cal-nav-btn" onclick="calPickDate()" title="Pick a date"><i class="fas fa-calendar-alt"></i></button>
            <button class="cal-nav-btn" onclick="calNav(7)" title="Forward 1 week"><i class="fas fa-chevron-right"></i></button>
            <button class="cal-nav-btn" onclick="calNav(${CAL_WINDOW_DAYS})" title="Next ${CAL_WINDOW_DAYS} days"><i class="fas fa-angles-right"></i></button>
        </div>`;
        
        if (!data.events?.length) {
            view.innerHTML = navHtml + '<div class="loading-placeholder">No events in this window</div>';
            return;
        }
        
        const byDay = data.by_day || {};
        const today = calDateStr(new Date());
        const tomorrow = calDateStr(new Date(Date.now() + 86400000));
        
        let html = navHtml + '<div class="cal-timeline">';
        
        const dayKeys = Object.keys(byDay).sort();
        for (const dayKey of dayKeys) {
            const events = byDay[dayKey];
            const dayDate = new Date(dayKey + 'T12:00:00');
            
            let dayLabel;
            if (dayKey === today) dayLabel = 'TODAY';
            else if (dayKey === tomorrow) dayLabel = 'TOMORROW';
            else dayLabel = dayDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase();
            
            const isToday = dayKey === today;
            
            html += `<div class="cal-day ${isToday ? 'cal-today' : ''}">
                <div class="cal-day-header">
                    <span class="cal-day-label">${dayLabel}</span>
                    <span class="cal-day-count">${events.length} event${events.length !== 1 ? 's' : ''}</span>
                </div>
                <div class="cal-events">`;
            
            for (const evt of events) {
                const startDt = new Date(evt.start);
                const timeStr = evt.all_day ? 'ALL DAY' : startDt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
                let endStr = '';
                if (evt.end && !evt.all_day) {
                    const endDt = new Date(evt.end);
                    endStr = ' \u2013 ' + endDt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
                }
                
                html += `<div class="cal-event" style="border-left-color: ${evt.color || '#00b4e8'}">
                    <div class="cal-event-time">${timeStr}${endStr}</div>
                    <div class="cal-event-title">${escapeHtml(evt.title)}</div>
                    ${evt.location ? `<div class="cal-event-location"><i class="fas fa-map-pin"></i> ${escapeHtml(evt.location)}</div>` : ''}
                    <span class="cal-event-source" style="color: ${evt.color || '#00b4e8'}">${evt.source}</span>
                </div>`;
            }
            
            html += '</div></div>';
        }
        
        html += '</div>';
        view.innerHTML = html;
    } catch(e) { console.error('[Calendar]', e); }
}


// ===== Init =====

// ===== Phase 3: News Ticker =====
let newsExpanded = false;

async function fetchNews() {
    try {
        const data = await (await fetch('/api/news')).json();
        const ticker = document.getElementById('news-ticker');
        const topicBadge = document.getElementById('news-topic');
        const articles = document.getElementById('news-articles');
        
        const tagMap = { ebpf: 'eBPF', federal: 'FED IT', cisco: 'CISCO', zerotrust: 'ZERO TRUST' };
        topicBadge.textContent = tagMap[data.topic] || data.topic?.toUpperCase() || 'INTEL';
        
        if (!data.articles?.length) {
            ticker.innerHTML = '<div class="ticker-item"><span class="ticker-text">No intel available — check back later</span></div>';
            return;
        }
        
        // Scrolling ticker
        const tickerHtml = data.articles.map(a => 
            `<span class="ticker-item" onclick="toggleNewsPanel()">
                <span class="ticker-source">${a.source || ''}</span>
                <span class="ticker-text">${escapeHtml(a.title)}</span>
                ${a.age ? `<span class="ticker-age">${a.age}</span>` : ''}
            </span>`
        ).join('<span class="ticker-sep">◆</span>');
        
        ticker.innerHTML = `<div class="ticker-scroll">${tickerHtml}${tickerHtml}</div>`;
        
        // Expandable article list
        articles.innerHTML = data.articles.map(a => 
            `<a class="news-article" href="${a.url}" target="_blank" rel="noopener">
                <div class="news-article-title">${escapeHtml(a.title)}</div>
                <div class="news-article-meta">
                    <span class="news-source">${a.source || ''}</span>
                    ${a.age ? `<span class="news-age">${a.age}</span>` : ''}
                </div>
                ${a.description ? `<div class="news-article-desc">${escapeHtml(a.description)}</div>` : ''}
            </a>`
        ).join('');
    } catch(e) { console.error('[News]', e); }
}

function toggleNewsPanel() {
    const articles = document.getElementById('news-articles');
    newsExpanded = !newsExpanded;
    articles.style.display = newsExpanded ? 'block' : 'none';
}

// ===== Phase 3: Network Topology =====
async function fetchTopology() {
    try {
        const data = await (await fetch('/api/network/topology')).json();
        const map = document.getElementById('topology-map');
        const countBadge = document.getElementById('topo-device-count');
        
        const totalDevices = (data.dhcp_leases?.length || 0) + (data.meraki_devices?.length || 0);
        countBadge.textContent = totalDevices + ' DEVICES';
        
        let html = '';
        
        // Router node
        if (data.router) {
            html += `<div class="topo-section">
                <div class="topo-node topo-router">
                    <i class="fas fa-network-wired"></i>
                    <div class="topo-node-info">
                        <div class="topo-node-name">${data.router.name}</div>
                        <div class="topo-node-detail">v${data.router.version} · CPU ${data.router.cpu_load}% · RAM ${data.router.memory_pct}%</div>
                        <div class="topo-node-detail">${data.router.uptime}</div>
                    </div>
                </div>
            </div>`;
        }
        
        // VLANs
        if (data.vlans?.length) {
            html += '<div class="topo-section"><div class="topo-section-title">VLANs</div><div class="topo-vlan-grid">';
            for (const vlan of data.vlans) {
                const leaseCount = data.dhcp_leases?.filter(l => {
                    const net = vlan.network;
                    if (!net) return false;
                    return l.address.startsWith(net.split('.').slice(0,3).join('.'));
                }).length || 0;
                html += `<div class="topo-vlan">
                    <div class="topo-vlan-name">${vlan.name}</div>
                    <div class="topo-vlan-addr">${vlan.address}</div>
                    <div class="topo-vlan-devices">${leaseCount} devices</div>
                </div>`;
            }
            html += '</div></div>';
        }
        
        // Meraki devices
        if (data.meraki_devices?.length) {
            html += '<div class="topo-section"><div class="topo-section-title">Wireless</div><div class="topo-device-list">';
            for (const dev of data.meraki_devices) {
                const statusClass = dev.status === 'online' ? 'online' : 'offline';
                html += `<div class="topo-device">
                    <div class="infra-dot ${statusClass}"></div>
                    <div><div class="topo-device-name">${dev.name || dev.model}</div>
                    <div class="topo-device-detail">${dev.model} · ${dev.ip || 'no IP'}</div></div>
                </div>`;
            }
            html += '</div></div>';
        }
        
        // Active interfaces
        if (data.interfaces?.length) {
            const activeIfaces = data.interfaces.filter(i => i.running);
            if (activeIfaces.length) {
                html += '<div class="topo-section"><div class="topo-section-title">Active Links</div><div class="topo-iface-grid">';
                for (const iface of activeIfaces.slice(0, 12)) {
                    const rx = formatBytes(iface.rx_bytes);
                    const tx = formatBytes(iface.tx_bytes);
                    html += `<div class="topo-iface">
                        <div class="topo-iface-name">${iface.name}</div>
                        <div class="topo-iface-speed">${iface.speed || iface.type}</div>
                        <div class="topo-iface-traffic">↓${rx} ↑${tx}</div>
                    </div>`;
                }
                html += '</div></div>';
            }
        }
        
        map.innerHTML = html || '<div class="loading-placeholder">No topology data</div>';
    } catch(e) { console.error('[Topology]', e); }
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1048576) return (bytes/1024).toFixed(0) + 'K';
    if (bytes < 1073741824) return (bytes/1048576).toFixed(1) + 'M';
    return (bytes/1073741824).toFixed(1) + 'G';
}

// ===== Phase 3: Speedtest =====
async function fetchSpeedtestHistory() {
    try {
        const data = await (await fetch('/api/speedtest/history')).json();
        const results = data.results || [];
        
        if (results.length) {
            const latest = results[results.length - 1];
            document.getElementById('speed-down').textContent = latest.download_mbps || '--';
            document.getElementById('speed-up').textContent = latest.upload_mbps || '--';
            document.getElementById('speed-ping').textContent = latest.ping_ms || '--';
            
            // Render simple bar chart for last 10 results
            renderSpeedChart(results.slice(-10));
        }
    } catch(e) { console.error('[Speedtest]', e); }
}

function renderSpeedChart(results) {
    const chart = document.getElementById('speedtest-chart');
    if (!results.length) { chart.innerHTML = ''; return; }
    
    const maxDown = Math.max(...results.map(r => r.download_mbps || 0), 1);
    
    chart.innerHTML = `<div class="speed-chart-bars">
        ${results.map(r => {
            const downPct = ((r.download_mbps || 0) / maxDown * 100).toFixed(0);
            const upPct = ((r.upload_mbps || 0) / maxDown * 100).toFixed(0);
            const time = r.timestamp ? new Date(r.timestamp).toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit', hour12:true}) : '';
            const date = r.timestamp ? new Date(r.timestamp).toLocaleDateString('en-US', {month:'short', day:'numeric'}) : '';
            return `<div class="speed-bar-group" title="${date} ${time}\n↓ ${r.download_mbps} Mbps\n↑ ${r.upload_mbps} Mbps">
                <div class="speed-bar-container">
                    <div class="speed-bar down" style="height:${downPct}%"></div>
                    <div class="speed-bar up" style="height:${upPct}%"></div>
                </div>
                <div class="speed-bar-label">${date.split(' ')[1] || ''}</div>
            </div>`;
        }).join('')}
    </div>`;
}

async function runSpeedtest() {
    const btn = document.getElementById('speedtest-btn');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> TESTING';
    btn.disabled = true;
    try {
        const resp = await fetch('/api/speedtest/run', { method: 'POST' });
        const data = await resp.json();
        if (data.result) {
            document.getElementById('speed-down').textContent = data.result.download_mbps;
            document.getElementById('speed-up').textContent = data.result.upload_mbps;
            document.getElementById('speed-ping').textContent = data.result.ping_ms;
            fetchSpeedtestHistory(); // refresh chart
        } else {
            console.error('[Speedtest]', data.error);
        }
    } catch(e) { console.error('[Speedtest]', e); }
    btn.innerHTML = '<i class="fas fa-play"></i> RUN';
    btn.disabled = false;
}

// ===== Phase 3: Notifications =====
async function fetchNotifications() {
    try {
        const data = await (await fetch('/api/notifications')).json();
        renderNotifications(data.notifications || []);
    } catch(e) { console.error('[Notifications]', e); }
}

function renderNotifications(notifs) {
    const list = document.getElementById('notification-list');
    const countBadge = document.getElementById('notif-count');
    const unread = notifs.filter(n => !n.read).length;
    
    if (unread > 0) {
        countBadge.textContent = unread;
        countBadge.style.display = '';
    } else {
        countBadge.style.display = 'none';
    }
    
    if (!notifs.length) {
        list.innerHTML = '<div class="notif-empty">No alerts. All quiet on the home front.</div>';
        return;
    }
    
    const typeIcons = { info: 'fa-info-circle', warning: 'fa-exclamation-triangle', success: 'fa-check-circle', error: 'fa-times-circle' };
    
    list.innerHTML = notifs.slice(0, 15).map(n => {
        const time = n.timestamp ? new Date(n.timestamp).toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit', hour12:true}) : '';
        const date = n.timestamp ? new Date(n.timestamp).toLocaleDateString('en-US', {month:'short', day:'numeric'}) : '';
        return `<div class="notif-item ${n.type || 'info'} ${n.read ? 'read' : 'unread'}" onclick="markNotifRead('${n.id}', this)">
            <div class="notif-icon"><i class="fas ${typeIcons[n.type] || typeIcons.info}"></i></div>
            <div class="notif-content">
                <div class="notif-title">${escapeHtml(n.title || '')}</div>
                <div class="notif-message">${escapeHtml(n.message || '')}</div>
                <div class="notif-time">${date} ${time}</div>
            </div>
        </div>`;
    }).join('');
}

async function markNotifRead(id, el) {
    try {
        await fetch(`/api/notifications/${id}/read`, { method: 'POST' });
        el.classList.remove('unread');
        el.classList.add('read');
        // Update count
        const countBadge = document.getElementById('notif-count');
        const current = parseInt(countBadge.textContent) || 0;
        if (current > 1) {
            countBadge.textContent = current - 1;
        } else {
            countBadge.style.display = 'none';
        }
    } catch(e) {}
}

// ===== Phase 3: Quick Timers =====
let activeTimers = [];
let timerInterval = null;

function startTimer(minutes, label) {
    const timer = {
        id: Date.now(),
        label: label || `${minutes}m Timer`,
        endTime: Date.now() + minutes * 60 * 1000,
        totalMs: minutes * 60 * 1000,
        done: false,
    };
    activeTimers.push(timer);
    renderTimers();
    
    if (!timerInterval) {
        timerInterval = setInterval(updateTimers, 1000);
    }
}

function startCustomTimer() {
    const input = document.getElementById('timer-custom-min');
    const min = parseInt(input.value);
    if (min && min > 0 && min <= 180) {
        startTimer(min, `${min}m Timer`);
        input.value = '';
    }
}

function updateTimers() {
    const now = Date.now();
    let anyActive = false;
    
    for (const timer of activeTimers) {
        if (!timer.done && now >= timer.endTime) {
            timer.done = true;
            timerAlarm(timer);
        }
        if (!timer.done) anyActive = true;
    }
    
    renderTimers();
    
    if (!anyActive && activeTimers.every(t => t.done)) {
        // Keep interval for display updates but could stop
    }
}

function timerAlarm(timer) {
    // Visual flash
    document.getElementById('widget-timers').classList.add('timer-alarm');
    setTimeout(() => document.getElementById('widget-timers').classList.remove('timer-alarm'), 3000);
    
    // Audio alert
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        [0, 300, 600].forEach(delay => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            osc.type = 'sine';
            gain.gain.value = 0.3;
            osc.start(ctx.currentTime + delay/1000);
            osc.stop(ctx.currentTime + delay/1000 + 0.15);
        });
    } catch(e) {}
}

function removeTimer(id) {
    activeTimers = activeTimers.filter(t => t.id !== id);
    renderTimers();
}

function renderTimers() {
    const container = document.getElementById('active-timers');
    if (!activeTimers.length) {
        container.innerHTML = '';
        return;
    }
    
    const now = Date.now();
    container.innerHTML = activeTimers.map(t => {
        if (t.done) {
            return `<div class="timer-active done">
                <div class="timer-label">${escapeHtml(t.label)}</div>
                <div class="timer-display">DONE!</div>
                <button class="timer-dismiss" onclick="removeTimer(${t.id})"><i class="fas fa-times"></i></button>
            </div>`;
        }
        const remaining = Math.max(0, t.endTime - now);
        const min = Math.floor(remaining / 60000);
        const sec = Math.floor((remaining % 60000) / 1000);
        const pct = ((t.totalMs - remaining) / t.totalMs * 100).toFixed(0);
        return `<div class="timer-active">
            <div class="timer-label">${escapeHtml(t.label)}</div>
            <div class="timer-display">${String(min).padStart(2,'0')}:${String(sec).padStart(2,'0')}</div>
            <div class="timer-progress"><div class="timer-progress-fill" style="width:${pct}%"></div></div>
            <button class="timer-dismiss" onclick="removeTimer(${t.id})"><i class="fas fa-times"></i></button>
        </div>`;
    }).join('');
}



// ===== Load Chat History =====
async function loadChatHistory() {
    try {
        const history = await (await fetch('/api/chat/history')).json();
        if (Array.isArray(history) && history.length) {
            const msgs = document.getElementById('chat-messages');
            // Clear default message
            msgs.innerHTML = '';
            // Show last 10 messages
            for (const msg of history.slice(-10)) {
                addChatMessage(msg.content, msg.role === 'user' ? 'user' : 'alfred');
            }
        }
    } catch(e) { console.error('[Chat History]', e); }
}





// ===== Init =====
async function init() {
    restoreWidgetStates();
    connectWebSocket();
    initVoice();
    
    await Promise.allSettled([
        fetchWeather(),
        fetchHealth(),
        fetchInfra(),
        fetchFrigateEvents(),
        fetchKanban(),
        fetchScenes(),
        fetchLights(),
        fetchMediaPlayers(),
        fetchActivities(),
        fetchNews(),
        fetchTopology(),
        fetchSpeedtestHistory(),
        fetchNotifications(),
        loadChatHistory(),
        fetchCalendar(),
    ]);

    // Periodic refreshes
    setInterval(fetchWeather, 5 * 60 * 1000);
    setInterval(fetchHealth, 60 * 1000);
    setInterval(fetchInfra, 30 * 1000);
    setInterval(fetchFrigateEvents, 15 * 1000);
    setInterval(fetchKanban, 60 * 1000);
    setInterval(fetchScenes, 5 * 60 * 1000);
    setInterval(fetchLights, 10 * 1000);
    setInterval(fetchMediaPlayers, 10 * 1000);
    setInterval(fetchActivities, 30 * 60 * 1000);
    setInterval(fetchNews, 15 * 60 * 1000);
    setInterval(fetchTopology, 60 * 1000);
    setInterval(fetchSpeedtestHistory, 5 * 60 * 1000);
    setInterval(fetchNotifications, 30 * 1000);
    setInterval(fetchCalendar, 5 * 60 * 1000);
}

init();
