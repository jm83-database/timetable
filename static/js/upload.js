/**
 * Timetable Dashboard - 업로드 페이지 로직
 */

const COURSE_COLORS = [
    '#4A90D9', '#E85D75', '#50C878', '#F5A623',
    '#9B59B6', '#1ABC9C', '#E74C3C', '#34495E',
    '#3498DB', '#E67E22', '#2ECC71', '#E91E63',
];

let uploadedFilepath = null;
let selectedSheets = [];
let selectedColor = COURSE_COLORS[0];

document.addEventListener('DOMContentLoaded', () => {
    initDropZone();
    initColorPicker();
    initButtons();
});

function initDropZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    document.getElementById('remove-file').addEventListener('click', resetUpload);
}

function initColorPicker() {
    const picker = document.getElementById('color-picker');
    COURSE_COLORS.forEach((color, i) => {
        const el = document.createElement('div');
        el.className = `color-option ${i === 0 ? 'selected' : ''}`;
        el.style.backgroundColor = color;
        el.dataset.color = color;
        el.addEventListener('click', () => {
            picker.querySelectorAll('.color-option, .color-custom').forEach(o => o.classList.remove('selected'));
            el.classList.add('selected');
            selectedColor = color;
        });
        picker.appendChild(el);
    });

    // 커스텀 컬러피커 버튼
    const customBtn = document.createElement('div');
    customBtn.className = 'color-custom';
    customBtn.title = '직접 선택';
    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.value = '#FF6B6B';
    colorInput.addEventListener('input', (e) => {
        picker.querySelectorAll('.color-option, .color-custom').forEach(o => o.classList.remove('selected'));
        customBtn.classList.add('selected');
        customBtn.style.background = e.target.value;
        selectedColor = e.target.value;
    });
    customBtn.appendChild(colorInput);
    picker.appendChild(customBtn);
}

function initButtons() {
    document.getElementById('select-all').addEventListener('click', () => {
        document.querySelectorAll('#sheet-list .sheet-checkbox input').forEach(cb => {
            cb.checked = true;
            cb.closest('.sheet-checkbox').classList.add('checked');
        });
        updateSelectedSheets();
    });

    document.getElementById('deselect-all').addEventListener('click', () => {
        document.querySelectorAll('#sheet-list .sheet-checkbox input').forEach(cb => {
            cb.checked = false;
            cb.closest('.sheet-checkbox').classList.remove('checked');
        });
        updateSelectedSheets();
    });

    document.getElementById('import-btn').addEventListener('click', importTimetable);
}

async function handleFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['xlsx', 'xls'].includes(ext)) {
        showResult('xlsx 또는 xls 파일만 업로드 가능합니다.', false);
        return;
    }

    // 파일 정보 표시
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-info').classList.remove('hidden');

    // 프로그레스 표시
    const progress = document.getElementById('upload-progress');
    const bar = document.getElementById('progress-bar');
    const text = document.getElementById('progress-text');
    progress.classList.remove('hidden');
    bar.style.width = '30%';
    text.textContent = '파일 업로드 중...';

    // 파일 업로드 → 시트 목록 요청
    const formData = new FormData();
    formData.append('file', file);

    try {
        bar.style.width = '60%';
        const res = await fetch('/api/sheets', { method: 'POST', body: formData });
        const data = await res.json();

        bar.style.width = '100%';
        text.textContent = '완료!';

        if (data.success) {
            uploadedFilepath = data.filepath;
            showSheetSelection(data.sheets);
            setTimeout(() => progress.classList.add('hidden'), 500);
        } else {
            showResult(data.error, false);
            progress.classList.add('hidden');
        }
    } catch (err) {
        showResult('파일 업로드 중 오류가 발생했습니다.', false);
        progress.classList.add('hidden');
    }
}

function showSheetSelection(sheets) {
    const list = document.getElementById('sheet-list');
    list.innerHTML = '';

    sheets.forEach(name => {
        const label = document.createElement('label');
        label.className = 'sheet-checkbox';
        label.innerHTML = `
            <input type="checkbox" value="${name}" checked>
            <span class="text-sm font-medium text-gray-700">${name}월</span>
        `;
        label.querySelector('input').addEventListener('change', (e) => {
            if (e.target.checked) {
                label.classList.add('checked');
            } else {
                label.classList.remove('checked');
            }
            updateSelectedSheets();
        });
        label.classList.add('checked');
        list.appendChild(label);
    });

    document.getElementById('step2').classList.remove('hidden');
    document.getElementById('step3').classList.remove('hidden');
    document.getElementById('import-section').classList.remove('hidden');

    updateSelectedSheets();
}

function updateSelectedSheets() {
    selectedSheets = [];
    document.querySelectorAll('#sheet-list .sheet-checkbox input:checked').forEach(cb => {
        selectedSheets.push(cb.value);
    });

    const importBtn = document.getElementById('import-btn');
    const courseName = document.getElementById('course-name').value.trim();
    importBtn.disabled = selectedSheets.length === 0 || !courseName;

    // 과정명 입력 리스너 추가
    document.getElementById('course-name').addEventListener('input', () => {
        const name = document.getElementById('course-name').value.trim();
        importBtn.disabled = selectedSheets.length === 0 || !name;
    });
}

async function importTimetable() {
    const btn = document.getElementById('import-btn');
    const courseName = document.getElementById('course-name').value.trim();
    const startTime = document.getElementById('start-time').value;

    if (!courseName) {
        showResult('과정명을 입력해주세요.', false);
        return;
    }

    btn.disabled = true;
    btn.textContent = '가져오는 중...';

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filepath: uploadedFilepath,
                sheets: selectedSheets,
                course_name: courseName,
                color: selectedColor,
                start_time: startTime,
            })
        });
        const data = await res.json();

        if (data.success) {
            showResult(data.message, true);
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
        } else {
            showResult(data.error, false);
            btn.disabled = false;
            btn.textContent = '시간표 가져오기';
        }
    } catch (err) {
        showResult('서버 오류가 발생했습니다.', false);
        btn.disabled = false;
        btn.textContent = '시간표 가져오기';
    }
}

function showResult(message, success) {
    const el = document.getElementById('result-message');
    const text = document.getElementById('result-text');
    el.className = `mt-4 p-4 rounded-lg ${success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`;
    text.textContent = message;
    el.classList.remove('hidden');
}

function resetUpload() {
    document.getElementById('file-input').value = '';
    document.getElementById('file-info').classList.add('hidden');
    document.getElementById('upload-progress').classList.add('hidden');
    document.getElementById('step2').classList.add('hidden');
    document.getElementById('step3').classList.add('hidden');
    document.getElementById('import-section').classList.add('hidden');
    document.getElementById('result-message').classList.add('hidden');
    uploadedFilepath = null;
    selectedSheets = [];
}
