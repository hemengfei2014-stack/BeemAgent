// State
let calendarData = [];
let currentOrgId = null;
let currentSearchQuery = '';

// DOM Elements
const tabsContainer = document.getElementById('orgTabs');
const contentContainer = document.getElementById('eventList');
const modal = document.getElementById('eventModal');
const searchInput = document.getElementById('searchInput');

// Init
fetch('calendar_data.json')
    .then(response => response.json())
    .then(data => {
        calendarData = data;
        if (calendarData.length > 0) {
            renderTabs();
            switchTab(calendarData[0].id);
        } else {
            contentContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No events found.</div>';
        }
    })
    .catch(err => console.error('Failed to load data:', err));

// Event Listeners
searchInput.addEventListener('input', (e) => {
    currentSearchQuery = e.target.value.trim();
    if (currentOrgId) {
        renderEvents(currentOrgId);
    }
});

// Render Tabs
function renderTabs() {
    tabsContainer.innerHTML = '';
    calendarData.forEach(org => {
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
    
    // Update Tabs UI
    document.querySelectorAll('.tab-item').forEach(t => {
        if (t.dataset.id === orgId) {
            t.classList.add('active');
        } else {
            t.classList.remove('active');
        }
    });

    renderEvents(orgId);
}

function renderEvents(orgId) {
    contentContainer.innerHTML = '';
    const orgGroup = calendarData.find(o => o.id === orgId);
    
    if (!orgGroup || !orgGroup.events || orgGroup.events.length === 0) {
        contentContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No events for this organization.</div>';
        return;
    }

    let eventsToRender = orgGroup.events;

    // Filter by search query
    if (currentSearchQuery) {
        const query = currentSearchQuery.toLowerCase();
        eventsToRender = eventsToRender.filter(event => {
            const organizerMatch = event.organizer_name && event.organizer_name.toLowerCase().includes(query);
            const participantMatch = event.participants && event.participants.some(p => p.toLowerCase().includes(query));
            return organizerMatch || participantMatch;
        });
    }

    if (eventsToRender.length === 0) {
        contentContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No matching events found.</div>';
        return;
    }

    eventsToRender.forEach(event => {
        const card = createEventCard(event);
        contentContainer.appendChild(card);
    });
}

function createEventCard(event) {
    const card = document.createElement('div');
    card.className = 'event-card';
    card.onclick = () => showEventDetails(event);

    const initial = event.organizer_name ? event.organizer_name[0] : '?';

    card.innerHTML = `
        <div class="event-header">
            <div class="event-subject">${event.subject}</div>
        </div>
        <div class="event-time">
            <span class="time-icon">🕒</span>
            ${event.start_time} - ${event.end_time.split(' ')[1]}
        </div>
        <div class="event-footer">
            <div class="organizer">
                <div class="avatar-small">${initial}</div>
                <span>${event.organizer_name}</span>
            </div>
            <div class="participants-summary">
                ${event.participant_count} participants
            </div>
        </div>
    `;
    return card;
}

function showEventDetails(event) {
    document.getElementById('modalSubject').innerText = event.subject;
    document.getElementById('modalTime').innerText = `${event.start_time} - ${event.end_time}`;
    document.getElementById('modalOrganizer').innerText = event.organizer_name;
    document.getElementById('modalId').innerText = event.event_id;

    const participantsContainer = document.getElementById('modalParticipants');
    participantsContainer.innerHTML = '';
    
    event.participants.forEach(p => {
        const tag = document.createElement('span');
        tag.className = 'participant-tag';
        tag.innerText = p;
        participantsContainer.appendChild(tag);
    });

    modal.classList.add('active');
}

function closeModal(e) {
    if (e) e.stopPropagation();
    modal.classList.remove('active');
}
