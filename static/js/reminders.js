let reminderPath = null;

async function reminderRequest(path, options) {
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || '요청에 실패했습니다.');
    return data;
}

function closeContactsModal() {
    document.getElementById('contacts-modal').classList.add('hidden');
}

async function openContactsModal() {
    document.getElementById('contacts-modal').classList.remove('hidden');
    await renderContacts();
    document.getElementById('contact-name').focus();
}

async function renderContacts() {
    const list = document.getElementById('contacts-list');
    list.textContent = '불러오는 중...';
    try {
        const { contacts } = await reminderRequest('/api/reminders/contacts');
        list.replaceChildren();
        if (!contacts.length) list.textContent = '등록된 수신자가 없습니다.';
        contacts.forEach(contact => {
            const row = document.createElement('div');
            row.className = 'py-3 flex items-center justify-between gap-3';
            const details = document.createElement('div');
            details.className = 'min-w-0 text-sm';
            const name = document.createElement('p');
            name.className = 'font-medium text-gray-800 break-words';
            name.textContent = contact.name;
            const email = document.createElement('p');
            email.className = 'text-gray-500 break-all';
            email.textContent = contact.email;
            details.append(name, email);
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'text-xs text-red-600 shrink-0';
            remove.textContent = '삭제';
            remove.setAttribute('aria-label', `${contact.name} 삭제`);
            remove.onclick = async () => {
                if (!confirm(`${contact.name} 수신자를 삭제하시겠습니까?`)) return;
                try {
                    await reminderRequest(`/api/reminders/contacts/${encodeURIComponent(contact.id)}`, { method: 'DELETE' });
                    await renderContacts();
                } catch (error) { showToast(error.message, 'error'); }
            };
            row.append(details, remove);
            list.append(row);
        });
    } catch (error) {
        list.textContent = '수신자 목록을 불러오지 못했습니다.';
        showToast(error.message, 'error');
    }
}

document.getElementById('contact-form').addEventListener('submit', async event => {
    event.preventDefault();
    const name = document.getElementById('contact-name');
    const email = document.getElementById('contact-email');
    try {
        await reminderRequest('/api/reminders/contacts', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name.value, email: email.value }),
        });
        name.value = '';
        email.value = '';
        await renderContacts();
        name.focus();
    } catch (error) { showToast(error.message, 'error'); }
});

async function openReminderModal() {
    if (!currentEvent) return;
    const { course_id: courseId, entry_id: entryId } = currentEvent.extendedProps;
    if (!courseId || !entryId) return;
    reminderPath = `/api/reminders/courses/${encodeURIComponent(courseId)}/entries/${encodeURIComponent(entryId)}`;
    document.getElementById('reminder-class').textContent = currentEvent.title;
    const list = document.getElementById('reminder-contacts');
    const history = document.getElementById('reminder-history');
    const save = document.getElementById('reminder-save');
    const educationType = document.getElementById('reminder-education-type');
    educationType.value = 'regular';
    educationType.disabled = true;
    updateReminderAttachments();
    list.textContent = '불러오는 중...';
    history.replaceChildren();
    save.disabled = true;
    closeModal();
    document.getElementById('reminder-modal').classList.remove('hidden');
    try {
        const [contactData, assignment] = await Promise.all([
            reminderRequest('/api/reminders/contacts'), reminderRequest(reminderPath),
        ]);
        educationType.value = assignment.education_type;
        updateReminderAttachments();
        educationType.disabled = false;
        list.replaceChildren();
        if (!contactData.contacts.length) list.textContent = '등록된 수신자가 없습니다.';
        contactData.contacts.forEach(contact => {
            const label = document.createElement('label');
            label.className = 'py-3 flex items-center gap-3 text-sm';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = contact.id;
            checkbox.checked = assignment.recipients.includes(contact.id);
            checkbox.className = 'accent-primary shrink-0';
            const text = document.createElement('span');
            text.className = 'min-w-0 break-all';
            text.textContent = `${contact.name} (${contact.email})`;
            label.append(checkbox, text);
            list.append(label);
        });
        if (assignment.deliveries.length) {
            const title = document.createElement('p');
            title.className = 'font-semibold text-gray-700 mb-2';
            title.textContent = '발송 이력';
            history.append(title);
            const names = new Map(contactData.contacts.map(contact => [contact.id, contact.name]));
            const states = { accepted: '발송 접수', failed: '실패', uncertain: '확인 필요', sending: '확인 필요' };
            assignment.deliveries.sort((left, right) => right.attempted_at.localeCompare(left.attempted_at))
                .slice(0, 20).forEach(delivery => {
                    const row = document.createElement('p');
                    row.className = 'py-1 break-words';
                    row.textContent = `${delivery.class_date} · D-${delivery.offset} · ${names.get(delivery.contact_id) || '삭제된 수신자'} · ${states[delivery.status] || '확인 필요'}`;
                    history.append(row);
                });
        }
        save.disabled = false;
    } catch (error) {
        list.textContent = '알림 설정을 불러오지 못했습니다.';
        showToast(error.message, 'error');
    }
}

function closeReminderModal() {
    document.getElementById('reminder-modal').classList.add('hidden');
}

function updateReminderAttachments() {
    const shortTerm = document.getElementById('reminder-education-type').value === 'short_term';
    document.getElementById('reminder-no-attachments').classList.toggle('hidden', shortTerm);
    document.getElementById('reminder-attachment-files').classList.toggle('hidden', !shortTerm);
}

document.getElementById('reminder-education-type').addEventListener('change', updateReminderAttachments);

async function saveReminderRecipients() {
    const recipients = Array.from(document.querySelectorAll('#reminder-contacts input:checked'), input => input.value);
    const educationType = document.getElementById('reminder-education-type').value;
    const button = document.getElementById('reminder-save');
    button.disabled = true;
    try {
        await reminderRequest(reminderPath, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipients, education_type: educationType }),
        });
        closeReminderModal();
        showToast('메일 알림 설정을 저장했습니다.', 'success');
    } catch (error) { showToast(error.message, 'error'); }
    finally { button.disabled = false; }
}

document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
        closeContactsModal();
        closeReminderModal();
    }
});