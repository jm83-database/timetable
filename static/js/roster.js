/**
 * Timetable Dashboard - 직원근무표 페이지 로직
 */

let calendar = null;
let employees = [];                 // [{name, color}]
let activeEmployees = new Set();
let categoryColors = {};
const CATEGORY_LABELS = { office: '사무실', event: '일정', leave: '휴가', laptop: '노트북', memo: '메모' };
const CATEGORY_ORDER = ['office', 'event', 'leave', 'laptop', 'memo'];
let activeCategories = new Set(CATEGORY_ORDER);
let currentEvent = null;
let uploadFilepath = null;
let selectedSummaryDate = null;

// 주간 뷰 인라인 편집 상태 (엑셀처럼 셀 선택 → 입력)
let selectedCell = null;        // { date, person }
let selectedEventId = null;
let pendingEditor = null;       // 저장 후 재렌더링되면 편집기를 열 셀 { date, person }
let weekRenderGen = 0;
let dragEventId = null;
let dragFromPerson = '';

const WEEKDAY_KO = ['일', '월', '화', '수', '목', '금', '토'];

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML.replace(/"/g, '&quot;');
}

// FullCalendar 마커 Date는 로컬 날짜가 UTC 필드에 담겨 있음
function markerYmd(d) {
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
}

function localYmd(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function todayYmd() {
    return localYmd(new Date());
}

function formatKoDate(ymd) {
    const [y, m, d] = ymd.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    return `${y}년 ${m}월 ${d}일 (${WEEKDAY_KO[date.getDay()]})`;
}

function employeeColor(name) {
    const emp = employees.find(e => e.name === name);
    return emp ? emp.color : '#6B7280';
}

function eventVisible(ep) {
    if (!activeCategories.has(ep.category)) return false;
    const people = ep.people || [];
    if (people.length === 0) return true;
    return people.some(p => activeEmployees.has(p));
}

// === 초기화 ===

document.addEventListener('DOMContentLoaded', async () => {
    await loadEmployees();
    initCalendar();
    renderCategoryFilters();
    loadDaySummary(todayYmd());
    initUploadModal();
});

async function loadEmployees() {
    try {
        const res = await fetch('/api/roster/employees');
        const data = await res.json();
        employees = data.employees || [];
        categoryColors = data.category_colors || {};
        activeEmployees = new Set(employees.map(e => e.name));
        renderEmployeeFilters();
        renderStatus(data);
        document.getElementById('no-roster').classList.toggle('hidden', data.entry_count > 0);
        const dl = document.getElementById('employee-datalist');
        dl.innerHTML = employees.map(e => `<option value="${escapeHtml(e.name)}">`).join('');
    } catch (err) {
        console.error('직원 목록 로딩 실패:', err);
    }
}

function renderStatus(data) {
    const el = document.getElementById('roster-status');
    if (!data.entry_count) {
        el.textContent = '등록된 근무표가 없습니다.';
        return;
    }
    const months = (data.months || []).map(m => m.replace('-', '년 ') + '월');
    el.innerHTML = `<p>총 <b>${data.entry_count}</b>건 · 직원 ${employees.length}명</p>
        <p class="mt-1 text-gray-400">${escapeHtml(months.join(', '))}</p>`;
}

// === 필터 ===

function renderEmployeeFilters() {
    const container = document.getElementById('employee-filters');
    container.innerHTML = '';
    document.getElementById('employee-filter-controls').classList.toggle('hidden', employees.length < 2);

    employees.forEach(emp => {
        const btn = document.createElement('button');
        btn.dataset.name = emp.name;
        btn.innerHTML = `<span class="dot"></span>${escapeHtml(emp.name)}`;
        btn.addEventListener('click', (e) => {
            if (e.ctrlKey || e.metaKey) {
                activeEmployees = new Set([emp.name]);
            } else if (activeEmployees.has(emp.name)) {
                activeEmployees.delete(emp.name);
            } else {
                activeEmployees.add(emp.name);
            }
            updateEmployeeFilterStates();
            calendar.refetchEvents();
        });
        container.appendChild(btn);
    });
    updateEmployeeFilterStates();
}

function updateEmployeeFilterStates() {
    document.querySelectorAll('#employee-filters button').forEach(btn => {
        const emp = employees.find(e => e.name === btn.dataset.name);
        if (!emp) return;
        const active = activeEmployees.has(emp.name);
        btn.className = `course-filter-btn ${active ? 'active' : 'inactive'}`;
        btn.style.backgroundColor = active ? emp.color : '';
        btn.querySelector('.dot').style.backgroundColor = active ? 'rgba(255,255,255,0.5)' : emp.color;
    });
}

function clearEmployeeFilters() {
    activeEmployees.clear();
    updateEmployeeFilterStates();
    calendar.refetchEvents();
}

function selectAllEmployees() {
    activeEmployees = new Set(employees.map(e => e.name));
    updateEmployeeFilterStates();
    calendar.refetchEvents();
}

function renderCategoryFilters() {
    const container = document.getElementById('category-filters');
    container.innerHTML = '';
    CATEGORY_ORDER.forEach(cat => {
        const btn = document.createElement('button');
        btn.dataset.cat = cat;
        btn.innerHTML = `<span class="dot"></span>${CATEGORY_LABELS[cat]}`;
        btn.addEventListener('click', () => {
            if (activeCategories.has(cat)) activeCategories.delete(cat);
            else activeCategories.add(cat);
            updateCategoryFilterStates();
            calendar.refetchEvents();
        });
        container.appendChild(btn);
    });
    updateCategoryFilterStates();
}

function updateCategoryFilterStates() {
    document.querySelectorAll('#category-filters button').forEach(btn => {
        const cat = btn.dataset.cat;
        const active = activeCategories.has(cat);
        const color = categoryColors[cat] || '#6B7280';
        btn.className = `course-filter-btn ${active ? 'active' : 'inactive'}`;
        btn.style.backgroundColor = active ? color : '';
        btn.querySelector('.dot').style.backgroundColor = active ? 'rgba(255,255,255,0.5)' : color;
    });
}

// === 캘린더 ===

function initCalendar() {
    const calendarEl = document.getElementById('calendar');
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'ko',
        headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,rosterWeek' },
        buttonText: { today: '오늘', month: '월간' },
        views: {
            rosterWeek: {
                duration: { weeks: 1 },
                buttonText: '주간',
                hiddenDays: [0, 6],
                titleFormat: { year: 'numeric', month: 'long', day: 'numeric' },
                content: renderRosterWeekView,
            },
        },
        firstDay: 0,
        height: 'auto',
        dayMaxEvents: 10,
        moreLinkText: '+{0}개',
        dateClick: (info) => {
            loadDaySummary(info.dateStr);
        },
        eventClick: (info) => showRosterDetail(info.event),
        eventDidMount: (info) => {
            const ep = info.event.extendedProps;
            info.el.title = [ep.title, (ep.people || []).join(', '), ep.note].filter(Boolean).join(' · ');
            if (ep.category === 'leave') info.el.style.opacity = '0.85';
        },
        loading: (isLoading) => {
            document.getElementById('calendar-loading').classList.toggle('hidden', !isLoading);
        },
        events: fetchRosterEvents,
    });
    calendar.render();
    document.getElementById('calendar-loading').classList.add('hidden');

    calendarEl.addEventListener('click', (e) => {
        if (e.target.closest('.tt-roster-editor')) return;
        const cell = e.target.closest('.tt-roster-cell');
        if (!cell) return;
        const card = e.target.closest('.tt-roster-card');
        if (e.target.closest('.tt-roster-card-more')) {
            const ev = calendar.getEventById(card.dataset.eventId);
            if (ev) showRosterDetail(ev);
            return;
        }
        selectCell(cell, card ? card.dataset.eventId : null);
        loadDaySummary(cell.dataset.date);
        if (e.detail === 2) openCellEditor(cell, card);
    });
    initWeekDragDrop(calendarEl);
    document.addEventListener('keydown', handleWeekKeydown);
}

async function fetchRosterEvents(fetchInfo, successCallback, failureCallback) {
    try {
        const params = new URLSearchParams({ start: fetchInfo.startStr, end: fetchInfo.endStr });
        const res = await fetch(`/api/roster/entries?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const events = await res.json();
        const genBefore = weekRenderGen;
        successCallback(events.filter(e => eventVisible(e.extendedProps)));
        if (pendingEditor) applyPendingEditor(genBefore);
    } catch (err) {
        console.error('근무표 로딩 실패:', err);
        showToast('근무표를 불러오지 못했습니다.', 'error');
        failureCallback(err);
    }
}

// === 주간 매트릭스 뷰 (행=직원, 열=월~금) ===

function renderRosterCard(seg) {
    const def = seg.def;
    const ep = def.extendedProps || {};
    const color = def.ui.backgroundColor || categoryColors[ep.category] || '#6B7280';
    const label = CATEGORY_LABELS[ep.category] || ep.category;
    const isOffice = ep.category === 'office';
    const main = isOffice ? '🏢 사무실근무' : (ep.title || ep.note || label);
    const sub = isOffice ? (ep.note || '') : ((ep.people || []).join(', '));
    const selected = def.publicId === selectedEventId ? ' is-selected' : '';
    return `<div class="tt-roster-card is-${escapeHtml(ep.category)}${selected}" data-event-id="${escapeHtml(def.publicId)}"
         draggable="true" style="background-color:${escapeHtml(color)}" title="${escapeHtml(def.title)}">
        <button type="button" class="tt-roster-card-more" title="상세 보기">⋯</button>
        ${isOffice ? '' : `<div class="tt-roster-card-top"><span class="tt-week-badge">${escapeHtml(label)}</span></div>`}
        <div class="tt-roster-card-main">${escapeHtml(main)}</div>
        ${sub ? `<div class="tt-roster-card-sub">${escapeHtml(sub)}</div>` : ''}
    </div>`;
}

function renderRosterWeekView(props) {
    const range = props.dateProfile.activeRange;
    const today = todayYmd();
    const days = [];
    for (let d = new Date(range.start); d < range.end; d = new Date(d.getTime() + 86400000)) {
        const dow = d.getUTCDay();
        if (dow === 0 || dow === 6) continue;
        days.push({ ymd: markerYmd(d), label: `${WEEKDAY_KO[dow]} ${d.getUTCMonth() + 1}/${d.getUTCDate()}` });
    }

    const rows = new Map();   // person → { ymd → [seg] }
    const unassigned = {};
    for (const seg of FullCalendar.sliceEvents(props, true)) {
        const ep = seg.def.extendedProps || {};
        const ymd = markerYmd(seg.range.start);
        const people = ep.people || [];
        if (people.length === 0) {
            (unassigned[ymd] = unassigned[ymd] || []).push(seg);
            continue;
        }
        for (const p of people) {
            if (!rows.has(p)) rows.set(p, {});
            const r = rows.get(p);
            (r[ymd] = r[ymd] || []).push(seg);
        }
    }

    const order = employees.map(e => e.name).filter(n => activeEmployees.has(n));
    for (const p of rows.keys()) if (!order.includes(p) && activeEmployees.has(p)) order.push(p);
    const hasUnassigned = Object.keys(unassigned).length > 0;

    weekRenderGen++;
    // 항목이 없어도 직원 행은 유지해 빈 셀에 바로 입력할 수 있게 함
    if (order.length === 0 && !hasUnassigned) {
        return { html: '<div class="tt-week-empty">표시할 직원이 없습니다. 직원 필터를 선택하거나 <b>+ 항목 추가</b>로 등록해주세요.</div>' };
    }
    order.push('');   // 담당자 없음 행 (항상 표시: 메모 등 입력용)

    let html = `<div class="tt-week-wrap"><table class="tt-week tt-roster" data-gen="${weekRenderGen}"><thead><tr><th class="tt-week-corner">직원</th>`;
    for (const day of days) {
        html += `<th class="tt-week-dayhead${day.ymd === today ? ' is-today' : ''}">${day.label}</th>`;
    }
    html += '</tr></thead><tbody>';

    const renderRow = (person, color, byDay) => {
        const label = person || '담당자 없음';
        html += `<tr><th class="tt-week-rowhead">
            <span class="tt-week-dot" style="background-color:${escapeHtml(color)}"></span>
            <span class="tt-week-coursename" title="${escapeHtml(label)}">${escapeHtml(label)}</span></th>`;
        for (const day of days) {
            const list = (byDay[day.ymd] || []);
            const isSel = selectedCell && selectedCell.date === day.ymd && selectedCell.person === person;
            html += `<td class="tt-week-cell tt-roster-cell${day.ymd === today ? ' is-today' : ''}${isSel ? ' is-selected' : ''}" data-date="${day.ymd}" data-person="${escapeHtml(person)}">`;
            for (const seg of list) html += renderRosterCard(seg);
            html += '</td>';
        }
        html += '</tr>';
    };

    for (const name of order) {
        if (name === '') renderRow('', '#9CA3AF', unassigned);
        else renderRow(name, employeeColor(name), rows.get(name) || {});
    }

    html += '</tbody></table></div>';
    html += `<p class="tt-roster-hint">셀 더블클릭·Enter: 입력 &nbsp;·&nbsp; 카드 더블클릭·F2: 수정 &nbsp;·&nbsp; 드래그: 이동 (Ctrl+드래그: 복사) &nbsp;·&nbsp; Delete: 삭제 &nbsp;·&nbsp; Tab/방향키: 이동</p>`;
    return { html };
}

// === 주간 뷰 인라인 편집 (셀 선택 → 입력 / 드래그 이동 / 키보드) ===

function isTypingTarget(el) {
    return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable);
}

function anyModalOpen() {
    return ['roster-detail-modal', 'roster-form-modal', 'roster-upload-modal', 'roster-help-modal']
        .some(id => !document.getElementById(id).classList.contains('hidden'));
}

function findCell(date, person) {
    return [...document.querySelectorAll('.tt-roster-cell')]
        .find(c => c.dataset.date === date && c.dataset.person === person) || null;
}

function selectCell(cell, eventId = null) {
    document.querySelectorAll('.tt-roster-cell.is-selected, .tt-roster-card.is-selected')
        .forEach(c => c.classList.remove('is-selected'));
    selectedCell = cell ? { date: cell.dataset.date, person: cell.dataset.person } : null;
    selectedEventId = eventId || null;
    if (!cell) return;
    cell.classList.add('is-selected');
    if (eventId) {
        const card = [...cell.querySelectorAll('.tt-roster-card')].find(c => c.dataset.eventId === eventId);
        if (card) card.classList.add('is-selected');
    }
}

function adjacentCell(cell, dRow, dCol) {
    const row = cell.parentElement;
    const rows = [...row.parentElement.children];
    const colIdx = [...row.querySelectorAll('.tt-roster-cell')].indexOf(cell);
    const targetRow = rows[rows.indexOf(row) + dRow];
    if (!targetRow) return null;
    return targetRow.querySelectorAll('.tt-roster-cell')[colIdx + dCol] || null;
}

function moveSelection(dRow, dCol) {
    if (!selectedCell) return;
    const cur = findCell(selectedCell.date, selectedCell.person);
    const target = cur && adjacentCell(cur, dRow, dCol);
    if (!target) return;
    selectCell(target);
    loadDaySummary(target.dataset.date);
}

function selectedCard() {
    if (!selectedCell || !selectedEventId) return null;
    const cell = findCell(selectedCell.date, selectedCell.person);
    return cell ? [...cell.querySelectorAll('.tt-roster-card')].find(c => c.dataset.eventId === selectedEventId) || null : null;
}

function inferCategory(text) {
    if (/휴가|연차|반차|병가|휴무/.test(text)) return 'leave';
    if (/사무실/.test(text)) return 'office';
    if (/노트북/.test(text)) return 'laptop';
    return 'event';
}

async function rosterRequest(url, method, body) {
    try {
        const res = await fetch(url, {
            method,
            headers: body ? { 'Content-Type': 'application/json' } : undefined,
            body: body ? JSON.stringify(body) : undefined,
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        showToast(data.message, 'success');
        await refreshAll();
        return true;
    } catch (err) {
        showToast(err.message || '저장에 실패했습니다.', 'error');
        return false;
    }
}

async function createFromCell(cell, text) {
    const person = cell.dataset.person;
    const category = inferCategory(text);
    return rosterRequest('/api/roster/entries', 'POST', {
        date: cell.dataset.date,
        category: person ? category : (category === 'event' ? 'memo' : category),
        title: text,
        people: person ? [person] : [],
        note: '',
    });
}

async function saveCardText(ev, field, text) {
    const ep = ev.extendedProps;
    if (text === (ep[field] || '')) return false;
    const url = `/api/roster/entries/${encodeURIComponent(ep.entry_id)}`;
    if (!text && field === 'title') {
        if (!confirm(`'${ev.title}' 항목을 삭제하시겠습니까?`)) return false;
        return rosterRequest(url, 'DELETE');
    }
    return rosterRequest(url, 'PUT', { [field]: text });
}

async function deleteSelectedCard() {
    const ev = selectedEventId && calendar.getEventById(selectedEventId);
    if (!ev) return;
    if (!confirm(`'${ev.title}' 항목을 삭제하시겠습니까?`)) return;
    selectedEventId = null;
    await rosterRequest(`/api/roster/entries/${encodeURIComponent(ev.extendedProps.entry_id)}`, 'DELETE');
}

function openCellEditor(cell, card = null, initialText = null) {
    if (!cell || document.querySelector('.tt-roster-editor')) return;
    const ev = card ? calendar.getEventById(card.dataset.eventId) : null;
    const ep = ev ? ev.extendedProps : null;
    // 사무실근무 카드는 제목이 고정이므로 메모를 편집
    const field = ep && ep.category === 'office' ? 'note' : 'title';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'tt-roster-editor';
    input.maxLength = field === 'note' ? 300 : 100;
    input.value = initialText !== null ? initialText : (ep ? (ep[field] || '') : '');
    input.placeholder = ev ? '' : '내용 입력 후 Enter';
    if (card) { card.classList.add('is-editing'); card.appendChild(input); }
    else cell.appendChild(input);
    input.focus();
    if (initialText === null) input.select();

    let done = false;
    const finish = async (commit, dCol = 0) => {
        if (done) return;
        done = true;
        const text = input.value.trim();
        const next = dCol ? adjacentCell(cell, 0, dCol) : null;
        input.remove();
        if (card) card.classList.remove('is-editing');
        let changed = false;
        if (commit) {
            if (ev) changed = await saveCardText(ev, field, text);
            else if (text) changed = await createFromCell(cell, text);
        }
        if (!next) return;
        if (changed) pendingEditor = { date: next.dataset.date, person: next.dataset.person };
        else { selectCell(next); loadDaySummary(next.dataset.date); openCellEditor(next); }
    };
    input.addEventListener('keydown', (e) => {
        e.stopPropagation();
        if (e.key === 'Enter') { e.preventDefault(); finish(true); }
        else if (e.key === 'Escape') { e.preventDefault(); finish(false); }
        else if (e.key === 'Tab') { e.preventDefault(); finish(true, e.shiftKey ? -1 : 1); }
    });
    input.addEventListener('blur', () => finish(true));
    ['click', 'dblclick', 'mousedown'].forEach(t => input.addEventListener(t, e => e.stopPropagation()));
}

// 저장 → 재렌더링 뒤 Tab으로 이동한 다음 셀에 편집기를 연다
function applyPendingEditor(genBefore, attempt = 0) {
    if (!pendingEditor) return;
    const table = document.querySelector('.tt-roster[data-gen]');
    const rendered = weekRenderGen > genBefore && table && Number(table.dataset.gen) === weekRenderGen;
    if (rendered) {
        const target = pendingEditor;
        pendingEditor = null;
        const cell = findCell(target.date, target.person);
        if (cell) { selectCell(cell); loadDaySummary(cell.dataset.date); openCellEditor(cell); }
        return;
    }
    if (attempt < 30) requestAnimationFrame(() => applyPendingEditor(genBefore, attempt + 1));
    else pendingEditor = null;
}

function handleWeekKeydown(e) {
    if (!selectedCell || anyModalOpen() || isTypingTarget(document.activeElement)) return;
    const cur = findCell(selectedCell.date, selectedCell.person);
    if (!cur) return;
    const card = selectedCard();

    if (e.key === 'ArrowRight') { e.preventDefault(); moveSelection(0, 1); return; }
    if (e.key === 'ArrowLeft') { e.preventDefault(); moveSelection(0, -1); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); moveSelection(1, 0); return; }
    if (e.key === 'ArrowUp') { e.preventDefault(); moveSelection(-1, 0); return; }
    if (e.key === 'Tab') { e.preventDefault(); moveSelection(0, e.shiftKey ? -1 : 1); return; }
    if (e.key === 'Escape') { selectCell(null); return; }
    if (e.key === 'Enter' || e.key === 'F2') { e.preventDefault(); openCellEditor(cur, card); return; }
    if (e.key === 'Delete' || e.key === 'Backspace') {
        if (card) { e.preventDefault(); deleteSelectedCard(); }
        return;
    }
    // 엑셀처럼 글자를 바로 입력하면 새 항목 편집 시작
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        openCellEditor(cur, null, e.key);
    }
}

async function moveOrCopyEvent(ev, fromPerson, toDate, toPerson, copy) {
    const ep = ev.extendedProps;
    const fromDate = ev.startStr.slice(0, 10);
    let people = (ep.people || []).slice();
    if (fromPerson !== toPerson) {
        people = people.filter(p => p !== fromPerson);
        if (toPerson && !people.includes(toPerson)) people.push(toPerson);
    }
    if (copy) {
        return rosterRequest('/api/roster/entries', 'POST', {
            date: toDate, category: ep.category, title: ep.title || '', people, note: ep.note || '',
        });
    }
    if (fromDate === toDate && fromPerson === toPerson) return false;
    selectedCell = { date: toDate, person: toPerson };
    selectedEventId = ev.id;
    return rosterRequest(`/api/roster/entries/${encodeURIComponent(ep.entry_id)}`, 'PUT', { date: toDate, people });
}

function initWeekDragDrop(calendarEl) {
    const clearDragOver = () => calendarEl.querySelectorAll('.tt-roster-cell.drag-over').forEach(c => c.classList.remove('drag-over'));

    calendarEl.addEventListener('dragstart', (e) => {
        const card = e.target.closest('.tt-roster-card');
        if (!card || card.classList.contains('is-editing')) { e.preventDefault(); return; }
        dragEventId = card.dataset.eventId;
        dragFromPerson = card.closest('.tt-roster-cell').dataset.person;
        e.dataTransfer.effectAllowed = 'copyMove';
        e.dataTransfer.setData('text/plain', dragEventId);
        card.classList.add('is-dragging');
    });
    calendarEl.addEventListener('dragend', () => {
        calendarEl.querySelectorAll('.tt-roster-card.is-dragging').forEach(c => c.classList.remove('is-dragging'));
        clearDragOver();
        dragEventId = null;
    });
    calendarEl.addEventListener('dragover', (e) => {
        const cell = e.target.closest('.tt-roster-cell');
        if (!cell || !dragEventId) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = e.ctrlKey ? 'copy' : 'move';
        if (!cell.classList.contains('drag-over')) { clearDragOver(); cell.classList.add('drag-over'); }
    });
    calendarEl.addEventListener('drop', async (e) => {
        const cell = e.target.closest('.tt-roster-cell');
        if (!cell || !dragEventId) return;
        e.preventDefault();
        const ev = calendar.getEventById(dragEventId);
        const fromPerson = dragFromPerson;
        clearDragOver();
        dragEventId = null;
        if (ev) await moveOrCopyEvent(ev, fromPerson, cell.dataset.date, cell.dataset.person, e.ctrlKey);
    });
}

// === 날짜 요약 ===

async function loadDaySummary(ymd) {
    selectedSummaryDate = ymd;
    document.getElementById('summary-date').textContent = formatKoDate(ymd);
    const el = document.getElementById('summary-content');
    try {
        const res = await fetch(`/api/roster/day?date=${encodeURIComponent(ymd)}`);
        const d = await res.json();
        if (!d.success) throw new Error(d.error);

        const chip = (name) => `<span class="tt-roster-chip" style="background-color:${escapeHtml(employeeColor(name))}">${escapeHtml(name)}</span>`;
        const section = (title, body) => `<div><p class="text-xs font-semibold text-gray-500 mb-1">${title}</p>${body}</div>`;
        const none = '<p class="text-xs text-gray-400">없음</p>';

        let html = section('🏢 사무실 근무', d.office.length ? d.office.map(chip).join(' ') : none);
        html += section('🌴 휴가', d.leave.length ? d.leave.map(chip).join(' ') : none);
        html += section('🚗 외부 일정', d.events.length
            ? '<ul class="space-y-1">' + d.events.map(e =>
                `<li class="text-sm"><span class="font-medium">${escapeHtml(e.title || '(제목 없음)')}</span>
                 <span class="text-gray-500">${escapeHtml((e.people || []).join(', '))}</span>
                 ${e.note ? `<span class="text-xs text-gray-400"> · ${escapeHtml(e.note)}</span>` : ''}</li>`).join('') + '</ul>'
            : none);
        if (d.laptop.length) {
            html += section('💻 노트북 방문', '<ul class="space-y-1">' + d.laptop.map(e =>
                `<li class="text-sm">${escapeHtml(e.note || e.title)}</li>`).join('') + '</ul>');
        }
        if (d.memo.length) {
            html += section('📝 메모', d.memo.map(e => `<p class="text-sm">${escapeHtml(e.title || e.note)}</p>`).join(''));
        }
        html += `<button onclick="openRosterAddModal('${ymd}')" class="mt-2 text-xs text-primary hover:underline">+ 이 날짜에 항목 추가</button>`;
        el.innerHTML = html;
    } catch (err) {
        el.innerHTML = '<p class="text-xs text-red-500">요약을 불러오지 못했습니다.</p>';
    }
}

// === 상세 모달 ===

function showRosterDetail(event) {
    currentEvent = event;
    const ep = event.extendedProps;
    document.getElementById('roster-detail-header').style.backgroundColor = event.backgroundColor || '#4A90D9';
    document.getElementById('roster-detail-title').textContent = event.title;
    document.getElementById('roster-detail-date').textContent = formatKoDate(event.startStr.slice(0, 10));
    document.getElementById('roster-detail-category').textContent = ep.category_label || ep.category;
    document.getElementById('roster-detail-people').textContent = (ep.people || []).join(', ') || '-';
    document.getElementById('roster-detail-note').textContent = ep.note || '-';
    document.getElementById('roster-detail-raw').textContent = ep.raw_text ? `${ep.raw_text}${ep.source_sheet ? ` (시트: ${ep.source_sheet})` : ''}` : '-';
    document.getElementById('roster-detail-modal').classList.remove('hidden');
}

function closeRosterDetailModal() {
    document.getElementById('roster-detail-modal').classList.add('hidden');
}

async function deleteRosterEntry() {
    if (!currentEvent) return;
    const id = currentEvent.extendedProps.entry_id;
    if (!confirm(`'${currentEvent.title}' 항목을 삭제하시겠습니까?`)) return;
    try {
        const res = await fetch(`/api/roster/entries/${encodeURIComponent(id)}`, { method: 'DELETE' });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        showToast(data.message, 'success');
        closeRosterDetailModal();
        await refreshAll();
    } catch (err) {
        showToast(err.message || '삭제에 실패했습니다.', 'error');
    }
}

// === 추가/수정 모달 ===

function openRosterAddModal(dateStr, person) {
    document.getElementById('roster-form-title').textContent = '근무 항목 추가';
    document.getElementById('roster-form-id').value = '';
    document.getElementById('roster-form-date').value = dateStr || selectedSummaryDate || todayYmd();
    document.getElementById('roster-form-category').value = 'event';
    document.getElementById('roster-form-title-input').value = '';
    document.getElementById('roster-form-people').value = person || '';
    document.getElementById('roster-form-note').value = '';
    document.getElementById('roster-form-modal').classList.remove('hidden');
}

function openRosterEditModal() {
    if (!currentEvent) return;
    const ep = currentEvent.extendedProps;
    closeRosterDetailModal();
    document.getElementById('roster-form-title').textContent = '근무 항목 수정';
    document.getElementById('roster-form-id').value = ep.entry_id;
    document.getElementById('roster-form-date').value = currentEvent.startStr.slice(0, 10);
    document.getElementById('roster-form-category').value = ep.category;
    document.getElementById('roster-form-title-input').value = ep.title || '';
    document.getElementById('roster-form-people').value = (ep.people || []).join(', ');
    document.getElementById('roster-form-note').value = ep.note || '';
    document.getElementById('roster-form-modal').classList.remove('hidden');
}

function closeRosterFormModal() {
    document.getElementById('roster-form-modal').classList.add('hidden');
}

async function submitRosterForm() {
    const id = document.getElementById('roster-form-id').value;
    const body = {
        date: document.getElementById('roster-form-date').value,
        category: document.getElementById('roster-form-category').value,
        title: document.getElementById('roster-form-title-input').value.trim(),
        people: document.getElementById('roster-form-people').value,
        note: document.getElementById('roster-form-note').value.trim(),
    };
    if (!body.date) { showToast('날짜를 입력해주세요.', 'error'); return; }
    if (body.category === 'office' && !body.title) body.title = '사무실근무';
    if (body.category === 'laptop' && !body.title) body.title = '노트북방문';
    if (body.category === 'leave' && !body.title) body.title = '휴가';

    try {
        const res = await fetch(id ? `/api/roster/entries/${encodeURIComponent(id)}` : '/api/roster/entries', {
            method: id ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        showToast(data.message, 'success');
        closeRosterFormModal();
        await refreshAll();
    } catch (err) {
        showToast(err.message || '저장에 실패했습니다.', 'error');
    }
}

async function refreshAll() {
    const prev = new Set(activeEmployees);
    const hadAll = prev.size === employees.length;
    await loadEmployees();
    if (!hadAll) {
        activeEmployees = new Set(employees.map(e => e.name).filter(n => prev.has(n)));
        updateEmployeeFilterStates();
    }
    calendar.refetchEvents();
    if (selectedSummaryDate) loadDaySummary(selectedSummaryDate);
}

// === 엑셀 업로드 모달 ===

function openRosterUploadModal() {
    resetUploadModal();
    document.getElementById('roster-upload-modal').classList.remove('hidden');
}

function closeRosterUploadModal() {
    document.getElementById('roster-upload-modal').classList.add('hidden');
}

// === 도움말 모달 ===

function openRosterHelpModal() {
    document.getElementById('roster-help-modal').classList.remove('hidden');
}

function closeRosterHelpModal() {
    document.getElementById('roster-help-modal').classList.add('hidden');
}

document.getElementById('roster-help-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeRosterHelpModal();
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeRosterHelpModal();
});

function resetUploadModal() {
    uploadFilepath = null;
    document.getElementById('roster-file-name').textContent = '';
    document.getElementById('roster-file-input').value = '';
    document.getElementById('roster-sheet-section').classList.add('hidden');
    document.getElementById('roster-sheet-list').innerHTML = '';
    document.getElementById('roster-import-btn').disabled = true;
}

function initUploadModal() {
    const zone = document.getElementById('roster-drop-zone');
    const input = document.getElementById('roster-file-input');
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) handleRosterFile(e.dataTransfer.files[0]);
    });
    input.addEventListener('change', (e) => {
        if (e.target.files.length) handleRosterFile(e.target.files[0]);
    });
}

async function handleRosterFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['xlsx', 'xls'].includes(ext)) { showToast('xlsx 또는 xls 파일만 업로드 가능합니다.', 'error'); return; }
    document.getElementById('roster-file-name').textContent = `${file.name} 분석 중...`;
    const form = new FormData();
    form.append('file', file);
    try {
        const res = await fetch('/api/roster/sheets', { method: 'POST', body: form });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        uploadFilepath = data.filepath;
        document.getElementById('roster-file-name').textContent = file.name;
        renderSheetList(data.sheets);
    } catch (err) {
        document.getElementById('roster-file-name').textContent = '';
        showToast(err.message || '파일을 읽지 못했습니다.', 'error');
    }
}

function renderSheetList(sheets) {
    const list = document.getElementById('roster-sheet-list');
    list.innerHTML = '';
    const thisMonth = todayYmd().slice(0, 7);
    sheets.forEach(s => {
        const ym = s.year && s.month ? `${s.year}-${String(s.month).padStart(2, '0')}` : '';
        const label = ym ? `${s.year}년 ${s.month}월` : '(월 판별 불가)';
        const checked = ym >= thisMonth;   // 이번 달 이후만 기본 선택
        const wrap = document.createElement('label');
        wrap.className = `sheet-checkbox${checked ? ' checked' : ''}`;
        wrap.innerHTML = `<input type="checkbox" value="${escapeHtml(s.name)}" ${checked ? 'checked' : ''} ${ym ? '' : 'disabled'}>
            <span class="text-sm">${escapeHtml(label)}</span><span class="ml-auto text-xs text-gray-400">시트 ${escapeHtml(s.name)}</span>`;
        wrap.querySelector('input').addEventListener('change', (e) => {
            wrap.classList.toggle('checked', e.target.checked);
            updateImportButton();
        });
        list.appendChild(wrap);
    });
    document.getElementById('roster-sheet-section').classList.remove('hidden');
    updateImportButton();
}

function toggleRosterSheets(on) {
    document.querySelectorAll('#roster-sheet-list input:not(:disabled)').forEach(cb => {
        cb.checked = on;
        cb.closest('.sheet-checkbox').classList.toggle('checked', on);
    });
    updateImportButton();
}

function selectedSheetNames() {
    return [...document.querySelectorAll('#roster-sheet-list input:checked')].map(cb => cb.value);
}

function updateImportButton() {
    document.getElementById('roster-import-btn').disabled = !uploadFilepath || selectedSheetNames().length === 0;
}

async function importRoster() {
    const sheets = selectedSheetNames();
    if (!uploadFilepath || !sheets.length) return;
    const labels = [...document.querySelectorAll('#roster-sheet-list input:checked')]
        .map(cb => cb.closest('label').querySelector('span').textContent);
    if (!confirm(`${labels.join(', ')}의 기존 근무표 항목을 모두 교체합니다. 계속할까요?`)) return;

    const btn = document.getElementById('roster-import-btn');
    btn.disabled = true;
    btn.textContent = '가져오는 중...';
    try {
        const res = await fetch('/api/roster/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filepath: uploadFilepath, sheets }),
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        showToast(data.message, 'success');
        closeRosterUploadModal();
        await loadEmployees();
        calendar.refetchEvents();
        if (selectedSummaryDate) loadDaySummary(selectedSummaryDate);
    } catch (err) {
        showToast(err.message || '가져오기에 실패했습니다.', 'error');
    } finally {
        btn.textContent = '가져오기';
        updateImportButton();
    }
}

// === 공통: 모달 닫기 / 토스트 ===

['roster-detail-modal', 'roster-form-modal', 'roster-upload-modal'].forEach(id => {
    document.getElementById(id).addEventListener('click', (e) => {
        if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
    });
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeRosterDetailModal();
        closeRosterFormModal();
        closeRosterUploadModal();
    }
});

function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
