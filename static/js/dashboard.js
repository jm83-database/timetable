/**
 * Timetable Dashboard - 대시보드 로직
 */

let calendar = null;
let courses = [];
let activeCourses = new Set();

// === XSS 방지 유틸리티 ===

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// === 색상 유틸리티 함수 ===

/**
 * Convert hex color to HSL components.
 * @param {string} hex - e.g. "#4A90D9"
 * @returns {number[]} [h, s, l] where h=0-360, s=0-100, l=0-100
 */
function hexToHsl(hex) {
    hex = hex.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16) / 255;
    const g = parseInt(hex.substring(2, 4), 16) / 255;
    const b = parseInt(hex.substring(4, 6), 16) / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;

    let h = 0;
    let s = 0;
    const l = (max + min) / 2;

    if (delta !== 0) {
        s = l > 0.5 ? delta / (2 - max - min) : delta / (max + min);
        switch (max) {
            case r: h = ((g - b) / delta + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / delta + 2) / 6; break;
            case b: h = ((r - g) / delta + 4) / 6; break;
        }
    }

    return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)];
}

/**
 * Convert HSL components to hex color.
 * @param {number} h - Hue 0-360
 * @param {number} s - Saturation 0-100
 * @param {number} l - Lightness 0-100
 * @returns {string} hex color e.g. "#4a90d9"
 */
function hslToHex(h, s, l) {
    s /= 100;
    l /= 100;

    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h / 60) % 2 - 1));
    const m = l - c / 2;

    let r, g, b;
    if (h < 60)       { r = c; g = x; b = 0; }
    else if (h < 120) { r = x; g = c; b = 0; }
    else if (h < 180) { r = 0; g = c; b = x; }
    else if (h < 240) { r = 0; g = x; b = c; }
    else if (h < 300) { r = x; g = 0; b = c; }
    else              { r = c; g = 0; b = x; }

    const toHex = (v) => {
        const hex = Math.round((v + m) * 255).toString(16);
        return hex.length === 1 ? '0' + hex : hex;
    };

    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

/**
 * Adjust event color based on class hours.
 * 8h = original; >8h = darker/more saturated; <8h = lighter/less saturated.
 * @param {string} hexColor - Base course color, e.g. "#4A90D9"
 * @param {number} hours - Class hours (e.g. 4, 8, 9, 10)
 * @returns {{ bg: string, text: string }} Adjusted background and text colors
 */
function adjustColorForHours(hexColor, hours) {
    if (!hours || hours === 8) {
        return { bg: hexColor, text: '#ffffff' };
    }

    let [h, s, l] = hexToHsl(hexColor);

    if (hours < 8) {
        // 연하게: L을 90%까지, S를 약간 줄임
        const factor = Math.min((8 - hours) / 5, 1);
        l = l + (90 - l) * factor;
        s = s * (1 - factor * 0.15);
    } else {
        // 진하게: L을 20%까지, S를 약간 높임
        const factor = Math.min((hours - 8) / 4, 1);
        l = l - (l - 20) * factor;
        s = Math.min(100, s * (1 + factor * 0.15));
    }

    const textColor = l > 65 ? '#374151' : '#ffffff';
    return { bg: hslToHex(h, s, l), text: textColor };
}

// === 사이드바 높이 동기화 ===

function syncSidebarHeight() {
    const calendarCard = document.querySelector('#calendar').closest('.bg-white');
    const sidebar = document.querySelector('.lg\\:w-80');
    if (calendarCard && sidebar && window.innerWidth >= 1024) {
        sidebar.style.maxHeight = calendarCard.offsetHeight + 'px';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initCalendar();
    loadCourses();
});

function initCalendar() {
    const calendarEl = document.getElementById('calendar');
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'ko',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek'
        },
        buttonText: {
            today: '오늘',
            month: '월간',
            week: '주간',
        },
        firstDay: 1, // 월요일 시작
        height: 'auto',
        dayMaxEvents: 6,
        moreLinkText: '+{0}개',
        displayEventTime: false, // 월간 뷰에서 시간 텍스트 숨김 (타이틀에 강사명 포함)
        dateClick: (info) => {
            openAddModal(info.dateStr);
        },
        eventClick: (info) => {
            showEventModal(info.event);
        },
        eventDidMount: (info) => {
            const props = info.event.extendedProps;
            // 공휴일 스타일
            if (props.is_holiday) {
                info.el.style.fontWeight = '600';
                info.el.style.fontSize = '0.7rem';
                return;
            }

            // 수업시간 기반 색상 조정 (8h=기본, >8h=진하게, <8h=연하게)
            const hours = props.hours;
            if (hours && hours !== 8) {
                const baseColor = info.event.backgroundColor;
                const adjusted = adjustColorForHours(baseColor, hours);
                info.el.style.backgroundColor = adjusted.bg;
                info.el.style.borderColor = adjusted.bg;
                info.el.style.color = adjusted.text;
                const titleEl = info.el.querySelector('.fc-event-title');
                if (titleEl) titleEl.style.color = adjusted.text;
            }

            // 일반 수업 툴팁
            let tooltip = info.event.title;
            if (hours) tooltip += ` - ${hours}h`;
            info.el.title = tooltip;
        },
        loading: (isLoading) => {
            const loader = document.getElementById('calendar-loading');
            if (loader) {
                loader.classList.toggle('hidden', !isLoading);
            }
        },
        datesSet: () => {
            // 월 변경 시 사이드바 높이 재동기화
            setTimeout(syncSidebarHeight, 100);
        },
        events: fetchEvents,
    });
    calendar.render();
    // 초기 로딩 완료 후 숨김
    const loader = document.getElementById('calendar-loading');
    if (loader) loader.classList.add('hidden');

    // 사이드바 높이 동기화
    setTimeout(syncSidebarHeight, 300);
    window.addEventListener('resize', syncSidebarHeight);
}

async function fetchEvents(fetchInfo, successCallback, failureCallback) {
    try {
        const res = await fetch('/api/events');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const events = await res.json();

        // 활성화된 과정만 필터
        const filtered = events.filter(e =>
            activeCourses.size === 0 || activeCourses.has(e.extendedProps.course_id)
        );
        successCallback(filtered);
    } catch (err) {
        console.error('이벤트 로딩 실패:', err);
        showToast('이벤트를 불러오지 못했습니다.', 'error');
        failureCallback(err);
    }
}

async function loadCourses() {
    try {
        const res = await fetch('/api/courses');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        courses = data.courses || [];

        if (courses.length === 0) {
            document.getElementById('no-courses').classList.remove('hidden');
        } else {
            document.getElementById('no-courses').classList.add('hidden');
        }

        renderFilters();
        renderCourseList();

        // 모든 과정 활성화
        activeCourses.clear();
        courses.forEach(c => activeCourses.add(c.id));

        // 통계 로드
        loadStats();
    } catch (err) {
        console.error('과정 로딩 실패:', err);
        showToast('과정 목록을 불러오지 못했습니다.', 'error');
    }
}

async function loadStats() {
    const section = document.getElementById('stats-section');
    const content = document.getElementById('stats-content');
    if (!section || !content) return;

    if (courses.length === 0) {
        section.classList.add('hidden');
        return;
    }

    try {
        const res = await fetch('/api/stats');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const stats = data.stats || [];

        if (stats.length === 0) {
            section.classList.add('hidden');
            return;
        }

        content.innerHTML = '';
        stats.forEach(stat => {
            const instructorList = Object.entries(stat.instructors || {})
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(([name, count]) => `${name}(${count})`)
                .join(', ');

            const card = document.createElement('div');
            card.className = 'p-3 rounded-lg border border-gray-100 bg-gray-50';
            card.innerHTML = `
                <div class="flex items-center space-x-2 mb-2">
                    <div class="w-3 h-3 rounded-full flex-shrink-0" style="background-color: ${escapeHtml(stat.color)}"></div>
                    <span class="text-xs font-semibold text-gray-700 truncate">${escapeHtml(stat.course_name)}</span>
                </div>
                <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    <div class="text-gray-500">수업 일수</div>
                    <div class="font-medium text-gray-700 text-right">${stat.total_classes}일</div>
                    <div class="text-gray-500">총 수업시간</div>
                    <div class="font-medium text-gray-700 text-right">${stat.total_hours}시간</div>
                    ${stat.total_holidays > 0 ? `
                    <div class="text-gray-500">휴일</div>
                    <div class="font-medium text-red-500 text-right">${stat.total_holidays}일</div>
                    ` : ''}
                </div>
                ${stat.date_range ? `
                <div class="mt-2 text-xs text-gray-400">${escapeHtml(stat.date_range)}</div>
                ` : ''}
                ${instructorList ? `
                <div class="mt-1.5 text-xs text-gray-500">
                    <span class="text-gray-400">강사:</span> ${escapeHtml(instructorList)}
                </div>
                ` : ''}
            `;
            content.appendChild(card);
        });

        section.classList.remove('hidden');
    } catch (err) {
        console.error('통계 로딩 실패:', err);
        section.classList.add('hidden');
    }
}

function renderFilters() {
    const container = document.getElementById('course-filters');
    container.innerHTML = '';

    courses.forEach(course => {
        const btn = document.createElement('button');
        btn.className = 'course-filter-btn active';
        btn.style.backgroundColor = course.color;
        btn.innerHTML = `<span class="dot" style="background-color: rgba(255,255,255,0.5)"></span>${escapeHtml(course.name)}`;
        btn.dataset.courseId = course.id;

        btn.addEventListener('click', () => {
            if (activeCourses.has(course.id)) {
                activeCourses.delete(course.id);
                btn.className = 'course-filter-btn inactive';
                btn.style.backgroundColor = '';
                btn.querySelector('.dot').style.backgroundColor = course.color;
            } else {
                activeCourses.add(course.id);
                btn.className = 'course-filter-btn active';
                btn.style.backgroundColor = course.color;
                btn.querySelector('.dot').style.backgroundColor = 'rgba(255,255,255,0.5)';
            }
            calendar.refetchEvents();
        });

        container.appendChild(btn);
    });
}

function renderCourseList() {
    const container = document.getElementById('course-list');
    container.innerHTML = '';

    if (courses.length === 0) {
        container.innerHTML = `
            <div class="text-center py-6">
                <svg class="mx-auto h-10 w-10 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                          d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
                </svg>
                <p class="text-sm text-gray-400 mt-2">등록된 과정이 없습니다</p>
                <a href="/upload" class="text-xs text-primary hover:underline mt-1 inline-block">시간표 업로드하기</a>
            </div>
        `;
        return;
    }

    courses.forEach(course => {
        const uploadDate = course.uploaded_at
            ? new Date(course.uploaded_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
            : '';

        const card = document.createElement('div');
        card.className = 'course-card';
        card.innerHTML = `
            <div class="flex items-center space-x-3 min-w-0">
                <div class="color-dot" style="background-color: ${escapeHtml(course.color)}"></div>
                <div class="min-w-0">
                    <p class="text-sm font-medium text-gray-800 truncate">${escapeHtml(course.name)}</p>
                    <p class="text-xs text-gray-500">${course.entry_count || 0}개 수업${uploadDate ? ` · ${escapeHtml(uploadDate)} 등록` : ''}</p>
                </div>
            </div>
            <button class="delete-course-btn text-gray-400 hover:text-red-500 transition-colors p-1 flex-shrink-0"
                    data-course-id="${escapeHtml(course.id)}" data-course-name="${escapeHtml(course.name)}"
                    title="과정 삭제">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
            </button>
        `;

        card.querySelector('.delete-course-btn').addEventListener('click', (e) => {
            const id = e.currentTarget.dataset.courseId;
            const name = e.currentTarget.dataset.courseName;
            deleteCourse(id, name);
        });

        container.appendChild(card);
    });
}

async function deleteCourse(courseId, courseName) {
    if (!confirm(`'${courseName}' 과정을 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.`)) return;

    try {
        const res = await fetch(`/api/courses/${courseId}`, { method: 'DELETE' });
        const data = await res.json();

        if (data.success) {
            showToast(`'${courseName}' 과정이 삭제되었습니다.`, 'success');
            activeCourses.delete(courseId);
            await loadCourses();
            calendar.refetchEvents();
        } else {
            showToast(data.error || '삭제에 실패했습니다.', 'error');
        }
    } catch (err) {
        showToast('삭제 중 오류가 발생했습니다.', 'error');
    }
}

function showEventModal(event) {
    const modal = document.getElementById('event-modal');
    const props = event.extendedProps;
    const deleteBtn = document.getElementById('modal-delete-btn');

    // 삭제용 ID 저장
    modal.dataset.courseId = props.course_id || '';
    modal.dataset.entryId = props.entry_id || '';

    // 삭제 버튼 표시/숨김 (entry_id가 있을 때만 삭제 가능)
    if (deleteBtn) {
        deleteBtn.classList.toggle('hidden', !props.entry_id);
    }

    // 공휴일인 경우
    if (props.is_holiday) {
        document.getElementById('modal-header').style.backgroundColor = '#ef4444';
        document.getElementById('modal-title').textContent = event.title;
        document.getElementById('modal-instructor').textContent = '-';
        document.getElementById('modal-course').textContent = props.course_name || '';

        const start = event.start;
        const dateStr = start.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' });
        document.getElementById('modal-date').textContent = dateStr;
        document.getElementById('modal-time').textContent = '휴일 (수업 없음)';

        modal.classList.remove('hidden');
        return;
    }

    document.getElementById('modal-header').style.backgroundColor = event.backgroundColor;
    document.getElementById('modal-title').textContent = event.title;
    document.getElementById('modal-instructor').textContent =
        (props.instructor || '미정').replace(/,/g, ', ');
    document.getElementById('modal-course').textContent = props.course_name || '';

    const start = event.start;
    const hours = props.hours || 0;
    const startStr = start.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' });
    document.getElementById('modal-date').textContent = startStr;

    const startTime = start.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
    const endTime = event.end ? event.end.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false }) : '';
    document.getElementById('modal-time').textContent = `${startTime} ~ ${endTime} (${hours}시간)`;

    modal.classList.remove('hidden');
}

function closeModal() {
    document.getElementById('event-modal').classList.add('hidden');
}

// 모달 바깥 클릭으로 닫기
document.getElementById('event-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
});
document.getElementById('add-event-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeAddModal();
});
document.getElementById('help-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeHelpModal();
});

// ESC 키로 모달 닫기
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeAddModal();
        closeHelpModal();
    }
});

// === 수업 추가 모달 ===

// 과정 색상 프리셋
const COURSE_COLORS = [
    '#4A90D9', '#E85D75', '#50C878', '#F5A623',
    '#9B59B6', '#1ABC9C', '#E74C3C', '#34495E',
    '#3498DB', '#E67E22', '#2ECC71', '#E91E63',
];

function openAddModal(dateStr) {
    const modal = document.getElementById('add-event-modal');
    const select = document.getElementById('add-course-select');

    // 과정 드롭다운 생성
    select.innerHTML = '<option value="">과정을 선택하세요</option>';
    courses.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = c.name;
        select.appendChild(opt);
    });
    // "새 과정 만들기" 옵션 추가
    const newOpt = document.createElement('option');
    newOpt.value = '__new__';
    newOpt.textContent = '+ 새 과정 만들기';
    select.appendChild(newOpt);

    // 과정이 1개면 자동 선택
    if (courses.length === 1) {
        select.value = courses[0].id;
    }

    // 새 과정 필드 초기화 & 숨김
    document.getElementById('new-course-fields').classList.add('hidden');
    document.getElementById('add-new-course-name').value = '';
    document.getElementById('add-new-course-color').value = '#4A90D9';
    initColorPicker();

    // 날짜 프리필 (dateClick에서 전달)
    document.getElementById('add-date').value = dateStr || '';

    // 나머지 필드 초기화
    document.getElementById('add-class-name').value = '';
    document.getElementById('add-instructor').value = '';
    document.getElementById('add-hours').value = '8';
    document.getElementById('add-start-time').value = '09:00';
    document.getElementById('add-is-holiday').checked = false;

    modal.classList.remove('hidden');
}

function onCourseSelectChange() {
    const select = document.getElementById('add-course-select');
    const newFields = document.getElementById('new-course-fields');
    if (select.value === '__new__') {
        newFields.classList.remove('hidden');
        document.getElementById('add-new-course-name').focus();
    } else {
        newFields.classList.add('hidden');
    }
}

function initColorPicker() {
    const container = document.getElementById('add-new-course-colors');
    const hiddenInput = document.getElementById('add-new-course-color');
    container.innerHTML = '';

    // 이미 사용 중인 색상 찾기
    const usedColors = new Set(courses.map(c => c.color));
    // 기본값: 사용되지 않은 첫 번째 색상
    let defaultColor = COURSE_COLORS.find(c => !usedColors.has(c)) || COURSE_COLORS[0];
    hiddenInput.value = defaultColor;

    COURSE_COLORS.forEach(color => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'color-option' + (color === defaultColor ? ' selected' : '');
        btn.style.backgroundColor = color;
        btn.title = color;
        btn.addEventListener('click', () => {
            container.querySelectorAll('.color-option, .color-custom').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            hiddenInput.value = color;
        });
        container.appendChild(btn);
    });

    // 커스텀 컬러피커 버튼
    const customBtn = document.createElement('div');
    customBtn.className = 'color-custom';
    customBtn.title = '직접 선택';
    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.value = '#FF6B6B';
    colorInput.addEventListener('input', (e) => {
        container.querySelectorAll('.color-option, .color-custom').forEach(b => b.classList.remove('selected'));
        customBtn.classList.add('selected');
        customBtn.style.background = e.target.value;
        hiddenInput.value = e.target.value;
    });
    customBtn.appendChild(colorInput);
    container.appendChild(customBtn);
}

function closeAddModal() {
    document.getElementById('add-event-modal').classList.add('hidden');
}

async function submitAddEntry() {
    let courseId = document.getElementById('add-course-select').value;
    const date = document.getElementById('add-date').value;
    const className = document.getElementById('add-class-name').value.trim();
    const instructor = document.getElementById('add-instructor').value.trim();
    const hours = parseInt(document.getElementById('add-hours').value) || 8;
    const startTime = document.getElementById('add-start-time').value || '09:00';
    const isHoliday = document.getElementById('add-is-holiday').checked;

    // 클라이언트 검증
    if (!courseId) { showToast('과정을 선택해주세요.', 'error'); return; }
    if (!date) { showToast('날짜를 선택해주세요.', 'error'); return; }
    if (!className) { showToast('수업명을 입력해주세요.', 'error'); return; }

    // 새 과정 생성이 필요한 경우
    if (courseId === '__new__') {
        const newCourseName = document.getElementById('add-new-course-name').value.trim();
        const newCourseColor = document.getElementById('add-new-course-color').value;

        if (!newCourseName) { showToast('새 과정명을 입력해주세요.', 'error'); return; }
        if (newCourseName.length < 2) { showToast('과정명은 2자 이상 입력해주세요.', 'error'); return; }

        try {
            const createRes = await fetch('/api/courses/quick', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    course_name: newCourseName,
                    color: newCourseColor,
                    start_time: startTime,
                })
            });
            const createData = await createRes.json();
            if (!createData.success) {
                showToast(createData.error || '과정 생성에 실패했습니다.', 'error');
                return;
            }
            courseId = createData.course_id;
        } catch (err) {
            showToast('과정 생성 중 오류가 발생했습니다.', 'error');
            return;
        }
    }

    try {
        const res = await fetch(`/api/courses/${courseId}/entries`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                date,
                class_name: className,
                instructor,
                hours,
                start_time: startTime,
                is_holiday: isHoliday,
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeAddModal();
            calendar.refetchEvents();
            loadCourses();
        } else {
            showToast(data.error || '추가에 실패했습니다.', 'error');
        }
    } catch (err) {
        showToast('수업 추가 중 오류가 발생했습니다.', 'error');
    }
}

// === 이벤트 삭제 ===

async function deleteEventFromModal() {
    const modal = document.getElementById('event-modal');
    const courseId = modal.dataset.courseId;
    const entryId = modal.dataset.entryId;

    if (!courseId || !entryId) {
        showToast('삭제할 수 없는 일정입니다.', 'error');
        return;
    }

    if (!confirm('이 수업 일정을 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.')) return;

    try {
        const res = await fetch(`/api/courses/${courseId}/entries/${entryId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            closeModal();
            calendar.refetchEvents();
            loadCourses();
        } else {
            showToast(data.error || '삭제에 실패했습니다.', 'error');
        }
    } catch (err) {
        showToast('삭제 중 오류가 발생했습니다.', 'error');
    }
}

// === 도움말 모달 ===

function openHelpModal() {
    document.getElementById('help-modal').classList.remove('hidden');
}

function closeHelpModal() {
    document.getElementById('help-modal').classList.add('hidden');
}

// === 토스트 ===

function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
