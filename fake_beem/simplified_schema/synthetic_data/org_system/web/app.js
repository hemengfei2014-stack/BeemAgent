// State
let orgData = [];
let currentOrgId = null;

// DOM Elements
const tabsContainer = document.getElementById('orgTabs');
const contentContainer = document.getElementById('orgContent');
const modal = document.getElementById('userModal');
const searchInput = document.getElementById('searchInput');

searchInput.addEventListener('input', (e) => handleSearch(e.target.value));

// Init
fetch('org_data.json')
    .then(response => response.json())
    .then(data => {
        orgData = data;
        if (orgData.length > 0) {
            renderTabs();
            switchTab(orgData[0].id);
        }
    })
    .catch(err => console.error('Failed to load data:', err));

// Render Tabs
function renderTabs() {
    tabsContainer.innerHTML = '';
    orgData.forEach(org => {
        const tab = document.createElement('div');
        tab.className = `tab-item`;
        tab.innerText = org.name;
        tab.onclick = () => switchTab(org.id);
        tab.dataset.id = org.id;
        tabsContainer.appendChild(tab);
    });
}

function switchTab(orgId) {
    currentOrgId = orgId;
    if (searchInput) searchInput.value = '';
    
    // Update Tabs UI
    document.querySelectorAll('.tab-item').forEach(t => {
        if (parseInt(t.dataset.id) === orgId) {
            t.classList.add('active');
        } else {
            t.classList.remove('active');
        }
    });

    renderOrgTree(orgId);
}

function handleSearch(query) {
    query = query.trim().toLowerCase();
    if (!query) {
        if (currentOrgId) renderOrgTree(currentOrgId);
        return;
    }

    contentContainer.innerHTML = '';
    
    const org = orgData.find(o => o.id === currentOrgId);
    if (!org) return;

    const allUsers = getAllUsers(org);
    const results = allUsers.filter(u => u.user.name.toLowerCase().includes(query));

    if (results.length === 0) {
        contentContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No results found</div>';
        return;
    }

    results.forEach(item => {
        contentContainer.appendChild(createUserNode(item.user, item.orgName, item.deptName, item.isLeader));
    });
}

function getAllUsers(org) {
    let users = [];
    
    if (org.ceo) {
        users.push({ user: org.ceo, orgName: org.name, deptName: "CEO Office", isLeader: true });
    }
    
    function traverse(dept) {
        if (dept.leader) {
             users.push({ user: dept.leader, orgName: org.name, deptName: dept.name, isLeader: true });
        }
        if (dept.members) {
            dept.members.forEach(m => {
                users.push({ user: m, orgName: org.name, deptName: dept.name, isLeader: false });
            });
        }
        if (dept.sub_depts) {
            dept.sub_depts.forEach(sd => traverse(sd));
        }
    }

    if (org.depts) {
        org.depts.forEach(d => traverse(d));
    }

    return users;
}

function renderOrgTree(orgId) {
    contentContainer.innerHTML = '';
    const org = orgData.find(o => o.id === orgId);
    if (!org) return;

    // CEO Node (Root)
    // Req: "最外层是ceo和一级部门"
    // Usually CEO is above departments or listed as a node.
    // Based on "Image 1" description: "最外层是ceo和一级部门".
    // Let's create a User Node for CEO first.
    
    if (org.ceo) {
        const ceoNode = createUserNode(org.ceo, org.name, "CEO Office"); // Fake dept for CEO
        contentContainer.appendChild(ceoNode);
    }

    // Departments
    org.depts.forEach(dept => {
        const deptNode = createDeptNode(dept, org.name);
        contentContainer.appendChild(deptNode);
    });
}

// Icons
const ICONS = {
    dept: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
    user: '' // handled by avatar
};

function createDeptNode(dept, orgName, parentDeptName = null) {
    const container = document.createElement('div');
    container.className = 'tree-node';

    // Header
    const header = document.createElement('div');
    header.className = 'node-header';
    
    // Count total people in this branch?
    // Let's just count direct members + subdepts members logic if needed.
    // For now simple name.
    
    // Calculate count
    let count = (dept.members ? dept.members.length : 0);
    if (dept.leader) count += 1;
    if (dept.sub_depts) {
        dept.sub_depts.forEach(sd => {
             if (sd.leader) count += 1;
             if (sd.members) count += sd.members.length;
        });
    }

    header.innerHTML = `
        <div class="icon">${ICONS.dept}</div>
        <div class="node-info">
            <span class="node-title">${dept.name}</span>
            <span class="node-count">(${count})</span>
        </div>
    `;

    // Children Container
    const children = document.createElement('div');
    children.className = 'node-children';

    header.onclick = () => {
        const isExpanded = children.classList.contains('expanded');
        if (isExpanded) {
            children.classList.remove('expanded');
            header.classList.remove('active');
        } else {
            children.classList.add('expanded');
            header.classList.add('active');
        }
    };

    container.appendChild(header);
    container.appendChild(children);

    // Populate Children (Lazy or Immediate - Immediate is fine for this size)
    // Order: Leader -> SubDepts (alphabetical) -> Members (alphabetical) OR
    // Req: "如果有二级部门...一级部门leader和二级部门...二级部门名称按照字母顺序展开"
    // Req: "如果没有二级部门...leader在第一个，组员...展开"
    
    // 1. Leader
    if (dept.leader) {
        children.appendChild(createUserNode(dept.leader, orgName, dept.name, true));
    }

    // 2. Sub Depts
    if (dept.sub_depts && dept.sub_depts.length > 0) {
        dept.sub_depts.forEach(sd => {
            children.appendChild(createDeptNode(sd, orgName, dept.name));
        });
    }

    // 3. Members
    if (dept.members && dept.members.length > 0) {
        dept.members.forEach(m => {
            children.appendChild(createUserNode(m, orgName, dept.name));
        });
    }

    return container;
}

function createUserNode(user, orgName, deptName, isLeader = false) {
    const el = document.createElement('div');
    el.className = 'user-item';
    
    // Avatar
    const avatarUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=random&color=fff`;
    
    el.innerHTML = `
        <div class="avatar" style="background-image: url('${avatarUrl}')"></div>
        <div class="user-details">
            <div class="user-name">
                ${user.name} 
                ${isLeader ? '<span class="leader-badge">Leader</span>' : ''}
            </div>
            <div class="user-role">${user.role_name}</div>
        </div>
    `;

    el.onclick = (e) => {
        e.stopPropagation(); // Prevent dept collapse/expand if user is inside header? No user is separate.
        showUserModal(user, orgName, deptName);
    };

    return el;
}

// Modal Logic
function showUserModal(user, orgName, deptName) {
    document.getElementById('modalUserId').innerText = user.id;
    document.getElementById('modalName').innerText = user.name;
    document.getElementById('modalRole').innerText = user.role_name;
    document.getElementById('modalUnit').innerText = orgName;
    document.getElementById('modalDept').innerText = deptName || "N/A";
    document.getElementById('modalManager').innerText = user.manager_name;
    document.getElementById('modalJob').innerText = user.role_name;
    document.getElementById('modalPhone').innerHTML = formatPhone(user.mobile);
    document.getElementById('modalEmail').innerText = user.email;
    document.getElementById('modalJoinDate').innerText = user.join_date_str;
    document.getElementById('modalGender').innerText = user.gender_name;

    const avatarUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=random&color=fff&size=128`;
    document.getElementById('modalAvatar').style.backgroundImage = `url('${avatarUrl}')`;

    modal.style.display = 'flex';
}

function closeModal(e) {
    if (e && e.target !== modal && !e.target.classList.contains('close-btn')) return;
    modal.style.display = 'none';
}

function formatPhone(phone) {
    if (!phone) return "";
    // Hide middle 4 digits
    if (phone.length === 11) {
        return `+86-${phone.substring(0,3)}****${phone.substring(7)} <a href="#" class="show-link" onclick="event.preventDefault(); this.parentElement.innerText='+86-${phone}'">Show</a>`;
    }
    return phone;
}
