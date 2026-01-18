
let allData = null;
let currentOrgId = null;
let selectedDocId = null;
let searchQuery = '';

// Init
fetch('doc_data.json')
    .then(response => response.json())
    .then(data => {
        allData = data;
        renderTabs();
        
        // Setup search
        document.getElementById('searchInput').addEventListener('input', (e) => {
            searchQuery = e.target.value.trim().toLowerCase();
            renderDocList();
        });

        // Default to first org
        const firstOrgId = Object.keys(allData.orgs)[0];
        if (firstOrgId) {
            switchOrg(firstOrgId);
        }
    })
    .catch(err => console.error('Failed to load data:', err));

function renderTabs() {
    const container = document.getElementById('orgTabs');
    container.innerHTML = '';
    
    Object.keys(allData.orgs).forEach(orgId => {
        const tab = document.createElement('div');
        tab.className = 'tab-item';
        tab.textContent = allData.orgs[orgId];
        tab.dataset.id = orgId;
        tab.onclick = () => switchOrg(orgId);
        container.appendChild(tab);
    });
}

function switchOrg(orgId) {
    currentOrgId = orgId;
    selectedDocId = null;
    
    // Update tabs UI
    document.querySelectorAll('.tab-item').forEach(tab => {
        if (tab.dataset.id === orgId) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    renderDocList();
    renderDocDetail(null);
}

function renderDocList() {
    const container = document.getElementById('docList');
    container.innerHTML = '';
    
    let docs = allData.docs.filter(d => d.org_id === currentOrgId);
    
    if (searchQuery) {
        docs = docs.filter(doc => {
            const ownerName = getUserName(doc.owner).toLowerCase();
            const hasAccess = doc.access_list.some(uid => {
                const name = getUserName(uid).toLowerCase();
                return name.includes(searchQuery);
            });
            return ownerName.includes(searchQuery) || hasAccess;
        });
    }

    if (docs.length === 0) {
        container.innerHTML = '<div style="padding:20px; color:#999; text-align:center;">No docs found</div>';
        return;
    }
    
    docs.forEach(doc => {
        const item = document.createElement('div');
        item.className = `doc-item ${selectedDocId === doc.doc_id ? 'active' : ''}`;
        item.onclick = () => selectDoc(doc);
        
        const ownerName = getUserName(doc.owner);
        
        item.innerHTML = `
            <div class="doc-title">
                <span class="doc-type-badge type-${doc.ctype}">${doc.ctype}</span>
                <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${doc.title}</span>
            </div>
            <div class="doc-meta">
                <span>${ownerName}</span>
                <span>${doc.create_time_str.split(' ')[0]}</span>
            </div>
        `;
        
        container.appendChild(item);
    });
}

function selectDoc(doc) {
    selectedDocId = doc.doc_id;
    
    // Update list UI
    document.querySelectorAll('.doc-item').forEach(item => {
        item.classList.remove('active');
    });
    // Re-render list to highlight (lazy way, but works for small list)
    renderDocList();
    
    renderDocDetail(doc);
}

function renderDocDetail(doc) {
    const container = document.getElementById('docDetail');
    
    if (!doc) {
        container.innerHTML = '<div class="empty-state">Select a document to view details</div>';
        return;
    }
    
    const ownerName = getUserName(doc.owner);
    
    // Generate access list HTML
    const accessHtml = doc.access_list.map(uid => {
        const name = getUserName(uid);
        const isOwner = uid === doc.owner;
        const avatarChar = name ? name[0] : '?';
        
        return `
            <div class="user-tag">
                <div class="user-avatar">${avatarChar}</div>
                ${name}
                ${isOwner ? '<span class="owner-badge">Owner</span>' : ''}
            </div>
        `;
    }).join('');
    
    container.innerHTML = `
        <div class="detail-header">
            <div class="detail-title">
                <span class="doc-type-badge type-${doc.ctype}" style="font-size:14px; padding:4px 8px;">${doc.ctype}</span>
                ${doc.title}
            </div>
            <div class="detail-meta">
                <div>Owner: <strong>${ownerName}</strong></div>
                <div>Created: ${doc.create_time_str}</div>
                <div>ID: ${doc.doc_id}</div>
            </div>
        </div>
        
        <div class="detail-content">${doc.note}</div>
        
        <div class="access-section">
            <h3>Access Permissions (${doc.access_list.length} users)</h3>
            <div class="user-list">
                ${accessHtml}
            </div>
        </div>
    `;
}

function getUserName(uid) {
    if (allData.users[uid]) {
        return allData.users[uid].name;
    }
    return uid;
}
