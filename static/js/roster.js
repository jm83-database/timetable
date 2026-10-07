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
        const card = e.target.closest('.tt-roster-card');
        if (card) {
            const ev = calendar.getEventById(card.dataset.eventId);
            if (ev) showRosterDetail(ev);
            return;
        }
        const cell = e.target.closest('.tt-roster-cell');
        if (cell) {
            loadDaySummary(cell.dataset.date);
            if (e.detail === 2) openRosterAddModal(cell.dataset.date, cell.dataset.person || '');
        }
    });
}

async function fetchRosterEvents(fetchInfo, successCallback, failureCallback) {
    try {
        const params = new URLSearchParams({ start: fetchInfo.startStr, end: fetchInfo.endStr });
        const res = await fetch(`/api/roster/entries?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const events = await res.json();
        successCallback(events.filter(e => eventVisible(e.extendedProps)));
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
    return `<div class="tt-roster-card is-${escapeHtml(ep.category)}" data-event-id="${escapeHtml(def.publicId)}"
         style="background-color:${escapeHtml(color)}" title="${escapeHtml(def.title)}">
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

    if (order.length === 0 && !hasUnassigned) {
        return { html: '<div class="tt-week-empty">이번 주에 표시할 근무 항목이 없습니다.</div>' };
    }

    let html = '<div class="tt-week-wrap"><table class="tt-week tt-roster"><thead><tr><th class="tt-week-corner">직원</th>';
    for (const day of days) {
        html += `<th class="tt-week-dayhead${day.ymd === today ? ' is-today' : ''}">${day.label}</th>`;
    }
    html += '</tr></thead><tbody>';

    const renderRow = (name, color, byDay) => {
        html += `<tr><th class="tt-week-rowhead">
            <span class="tt-week-dot" style="background-color:${escapeHtml(color)}"></span>
            <span class="tt-week-coursename" title="${escapeHtml(name)}">${escapeHtml(name)}</span></th>`;
        for (const day of days) {
            const list = (byDay[day.ymd] || []);
            html += `<td class="tt-week-cell tt-roster-cell${day.ymd === today ? ' is-today' : ''}" data-date="${day.ymd}" data-person="${escapeHtml(name === '담당자 없음' ? '' : name)}">`;
            for (const seg of list) html += renderRosterCard(seg);
            html += '</td>';
        }
        html += '</tr>';
    };

    for (const name of order) renderRow(name, employeeColor(name), rows.get(name) || {});
    if (hasUnassigned) renderRow('담당자 없음', '#9CA3AF', unassigned);

    html += '</tbody></table></div>';
    return { html };
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
