"""
Timetable Dashboard - 데이터 모델
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ClassEntry:
    """단일 수업 일정"""
    date: str                  # "2025-09-16"
    class_name: str            # "AI기본의 이해 및 활용1"
    instructor: str = ""       # "강명호" 또는 "강명호,인선미" (복수 강사)
    hours: int = 8             # 수업시간
    start_time: str = "09:00"
    end_time: str = "18:00"
    is_holiday: bool = False
    id: str = ""               # 개별 엔트리 식별자

    def to_dict(self):
        d = {
            "date": self.date,
            "class_name": self.class_name,
            "instructor": self.instructor,
            "hours": self.hours,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_holiday": self.is_holiday,
        }
        if self.id:
            d["id"] = self.id
        return d


@dataclass
class Course:
    """과정 정보"""
    id: str
    name: str
    color: str = "#4A90D9"
    file_name: str = ""
    uploaded_at: str = ""
    default_start_time: str = "09:00"
    entry_count: int = 0
    entries: List[ClassEntry] = field(default_factory=list)

    def to_dict(self, include_entries=False):
        d = {
            "id": self.id,
            "type": "course",
            "name": self.name,
            "color": self.color,
            "file_name": self.file_name,
            "uploaded_at": self.uploaded_at,
            "default_start_time": self.default_start_time,
            "entry_count": self.entry_count,
        }
        if include_entries:
            d["entries"] = [e.to_dict() for e in self.entries]
        return d
