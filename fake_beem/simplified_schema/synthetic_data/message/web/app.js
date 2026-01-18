let rawData = null;
let currentOrgId = 'all';
let currentSessionId = null;
let searchQuery = '';

async function init() {
    try {
        const response = await fetch('message_data.json');
        rawData = await response.json();
        
        renderOrgSelect();
        renderSessionList();
        
        document.getElementById('org-select').addEventListener('change', (e) => {
            currentOrgId = e.target.value;
            renderSessionList();
        });

        document.getElementById('user-search').addEventListener('input', (e) => {
            searchQuery = e.target.value.trim().toLowerCase();
            renderSessionList();
        });
        
    } catch (err) {
        console.error('Failed to load data:', err);
    }
}

function renderOrgSelect() {
    const select = document.getElementById('org-select');
    for (const [id, name] of Object.entries(rawData.orgs)) {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = name;
        select.appendChild(option);
    }
}

function renderSessionList() {
    const list = document.getElementById('session-list');
    list.innerHTML = '';
    
    const sessions = Object.values(rawData.sessions).filter(s => {
        // Org filter
        if (currentOrgId !== 'all' && s.org_id !== currentOrgId) {
            return false;
        }

        // Search filter
        if (searchQuery) {
            const participants = s.participants || [];
            const hasMatchingParticipant = participants.some(uid => {
                const user = rawData.users[uid];
                return user && user.name.toLowerCase().includes(searchQuery);
            });
            if (!hasMatchingParticipant) {
                return false;
            }
        }

        return true;
    });
    
    // Sort sessions by last message time
    sessions.sort((a, b) => {
        const lastA = a.messages.length > 0 ? a.messages[a.messages.length - 1].time : 0;
        const lastB = b.messages.length > 0 ? b.messages[b.messages.length - 1].time : 0;
        return lastB - lastA;
    });

    sessions.forEach(session => {
        const div = document.createElement('div');
        div.className = `session-item ${session.session_id === currentSessionId ? 'active' : ''}`;
        
        const lastMsg = session.messages.length > 0 ? session.messages[session.messages.length - 1] : null;
        const preview = lastMsg ? formatContent(lastMsg) : 'No messages';
        
        div.innerHTML = `
            <div class="session-title">${session.title}</div>
            <div class="session-preview">${preview}</div>
        `;
        
        div.onclick = () => selectSession(session.session_id);
        list.appendChild(div);
    });
}

function selectSession(sid) {
    currentSessionId = sid;
    renderSessionList(); // Re-render to update active state
    renderChat(sid);
}

function renderChat(sid) {
    const session = rawData.sessions[sid];
    const container = document.getElementById('message-list');
    const title = document.getElementById('chat-title');
    const meta = document.getElementById('chat-meta');
    
    title.textContent = session.title;
    meta.textContent = `${session.messages.length} messages | Org: ${rawData.orgs[session.org_id]}`;
    
    container.innerHTML = '';
    
    session.messages.forEach(msg => {
        const user = rawData.users[msg.from] || { name: msg.from, org_id: '?' };
        const isMe = false; // For demo, we are strictly an observer
        
        const div = document.createElement('div');
        div.className = `message-item ${isMe ? 'me' : ''}`;
        
        const avatarColor = stringToColor(user.name);
        
        div.innerHTML = `
            <div class="avatar" style="background-color: ${avatarColor}">${user.name[0]}</div>
            <div class="message-content-wrapper">
                <div class="sender-name">${user.name}</div>
                <div class="message-bubble ${msg.type === 2 ? 'msg-type-2' : ''} ${msg.type === 3 ? 'msg-type-3' : ''}">
                    ${formatContent(msg)}
                </div>
                <div class="time-stamp">${formatTime(msg.time)}</div>
            </div>
        `;
        
        container.appendChild(div);
    });
    
    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

function formatContent(msg) {
    if (msg.type === 1) return msg.content;
    if (msg.type === 2) return `🔗 ${msg.content}`;
    if (msg.type === 3) return `${msg.content}`;
    return msg.content;
}

function formatTime(ms) {
    return new Date(ms).toLocaleString();
}

function stringToColor(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + '00000'.substring(0, 6 - c.length) + c;
}

init();
