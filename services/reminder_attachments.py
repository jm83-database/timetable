"""Fixed attachments bundled with short-term class reminders."""

import base64
from pathlib import Path


EDUCATION_TYPES = ('regular', 'short_term')
ATTACHMENT_DIR = Path(__file__).resolve().parent / 'attachments'
ATTACHMENT_FILES = (
    ('결과보고서 견본.pdf', 'application/pdf'),
    ('결과보고서_양식.docx',
     'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
)


def load_attachments(education_type: str) -> list[dict[str, str]]:
    if education_type not in EDUCATION_TYPES:
        raise ValueError('지원하지 않는 교육 유형입니다.')
    if education_type == 'regular':
        return []
    attachments = []
    for name, content_type in ATTACHMENT_FILES:
        content = (ATTACHMENT_DIR / name).read_bytes()
        if not content:
            raise ValueError(f'첨부파일이 비어 있습니다: {name}')
        attachments.append({
            '@odata.type': '#microsoft.graph.fileAttachment',
            'name': name,
            'contentType': content_type,
            'contentBytes': base64.b64encode(content).decode('ascii'),
        })
    return attachments
