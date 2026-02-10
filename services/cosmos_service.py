"""
데이터 저장 서비스 - Azure Cosmos DB 또는 로컬 JSON fallback
"""
import os
import json
import uuid
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

_storage_instance = None


def _generate_entry_id():
    """고유 엔트리 ID 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"entry_{timestamp}_{unique_id}"


def get_storage():
    """저장소 싱글턴 인스턴스 반환"""
    global _storage_instance
    if _storage_instance is None:
        if Config.use_cosmos_db():
            _storage_instance = CosmosStorage()
        else:
            _storage_instance = LocalJsonStorage()
    return _storage_instance


class LocalJsonStorage:
    """로컬 JSON 파일 기반 저장소 (개발용 fallback)"""

    def __init__(self):
        self.filepath = Config.COURSES_FILE
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            self._save_data({"courses": []})
        logger.info("로컬 JSON 저장소 초기화 완료")

    def _load_data(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"courses": []}

    def _save_data(self, data):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _ensure_entry_ids(self, data):
        """기존 엔트리에 ID가 없으면 자동 할당 (lazy migration)"""
        modified = False
        for course in data.get('courses', []):
            for entry in course.get('entries', []):
                if not entry.get('id'):
                    entry['id'] = _generate_entry_id()
                    modified = True
        if modified:
            self._save_data(data)
        return data

    def get_all_courses(self):
        """전체 과정 목록 반환"""
        data = self._load_data()
        data = self._ensure_entry_ids(data)
        return data.get("courses", [])

    def save_course(self, course, entries):
        """과정과 수업 일정 저장"""
        data = self._load_data()
        for entry in entries:
            if not entry.get('id'):
                entry['id'] = _generate_entry_id()
        course['entries'] = entries
        data['courses'].append(course)
        self._save_data(data)
        logger.info(f"과정 저장: {course['name']} ({len(entries)}개 일정)")

    def delete_course(self, course_id):
        """과정 삭제"""
        data = self._load_data()
        original_len = len(data['courses'])
        data['courses'] = [c for c in data['courses'] if c.get('id') != course_id]
        if len(data['courses']) < original_len:
            self._save_data(data)
            logger.info(f"과정 삭제: {course_id}")
            return True
        return False

    def update_course(self, course_id, updates):
        """과정 정보 수정"""
        data = self._load_data()
        for course in data['courses']:
            if course.get('id') == course_id:
                for key in ['name', 'color', 'default_start_time']:
                    if key in updates:
                        course[key] = updates[key]
                self._save_data(data)
                logger.info(f"과정 수정: {course_id}")
                return True
        return False

    def create_course(self, course):
        """과정 메타데이터만 생성 (엑셀 업로드 없이)"""
        data = self._load_data()
        course['entries'] = []
        data['courses'].append(course)
        self._save_data(data)
        logger.info(f"과정 생성: {course['name']}")
        return course['id']

    def add_entry(self, course_id, entry):
        """과정에 개별 수업 일정 추가"""
        data = self._load_data()
        for course in data['courses']:
            if course.get('id') == course_id:
                if not entry.get('id'):
                    entry['id'] = _generate_entry_id()
                course.setdefault('entries', []).append(entry)
                course['entry_count'] = len(course['entries'])
                self._save_data(data)
                logger.info(f"수업 일정 추가: {course_id} / {entry.get('class_name')}")
                return entry['id']
        return None

    def delete_entry(self, course_id, entry_id):
        """과정에서 개별 수업 일정 삭제"""
        data = self._load_data()
        for course in data['courses']:
            if course.get('id') == course_id:
                original_len = len(course.get('entries', []))
                course['entries'] = [
                    e for e in course.get('entries', [])
                    if e.get('id') != entry_id
                ]
                if len(course['entries']) < original_len:
                    course['entry_count'] = len(course['entries'])
                    self._save_data(data)
                    logger.info(f"수업 일정 삭제: {course_id} / {entry_id}")
                    return True
        return False


class CosmosStorage:
    """Azure Cosmos DB 기반 저장소"""

    def __init__(self):
        from azure.cosmos import CosmosClient, PartitionKey
        self.client = CosmosClient(Config.COSMOS_DB_ENDPOINT, Config.COSMOS_DB_KEY)
        self.database = self.client.create_database_if_not_exists(id=Config.COSMOS_DATABASE_NAME)
        self.container = self.database.create_container_if_not_exists(
            id=Config.COSMOS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/type")
        )
        logger.info("Azure Cosmos DB 저장소 초기화 완료")

    def _generate_id(self, doc_type):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{doc_type}_{timestamp}_{unique_id}"

    def get_all_courses(self):
        """전체 과정 목록 (entries 포함) 반환"""
        query = "SELECT * FROM c WHERE c.type = 'course' ORDER BY c.uploaded_at DESC"
        courses = list(self.container.query_items(
            query=query, enable_cross_partition_query=True
        ))

        for course in courses:
            entry_query = "SELECT * FROM c WHERE c.type = 'entry' AND c.course_id = @course_id"
            entries = list(self.container.query_items(
                query=entry_query,
                parameters=[{"name": "@course_id", "value": course['id']}],
                enable_cross_partition_query=True
            ))
            course['entries'] = entries

        return courses

    def save_course(self, course, entries):
        """과정과 수업 일정 저장"""
        self.container.create_item(body=course)
        logger.info(f"과정 문서 저장: {course['name']}")

        for entry in entries:
            entry_doc = {
                "id": self._generate_id("entry"),
                "type": "entry",
                "course_id": course['id'],
                **entry
            }
            self.container.create_item(body=entry_doc)

        logger.info(f"수업 일정 {len(entries)}개 저장 완료")

    def delete_course(self, course_id):
        """과정 및 관련 일정 삭제"""
        try:
            # 과정 삭제
            self.container.delete_item(item=course_id, partition_key='course')

            # 관련 일정 삭제
            entry_query = "SELECT c.id FROM c WHERE c.type = 'entry' AND c.course_id = @course_id"
            entries = list(self.container.query_items(
                query=entry_query,
                parameters=[{"name": "@course_id", "value": course_id}],
                enable_cross_partition_query=True
            ))
            for entry in entries:
                self.container.delete_item(item=entry['id'], partition_key='entry')

            logger.info(f"과정 삭제: {course_id} ({len(entries)}개 일정 포함)")
            return True
        except Exception as e:
            logger.error(f"과정 삭제 실패: {e}")
            return False

    def update_course(self, course_id, updates):
        """과정 정보 수정"""
        try:
            query = "SELECT * FROM c WHERE c.type = 'course' AND c.id = @course_id"
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@course_id", "value": course_id}],
                enable_cross_partition_query=True
            ))
            if not items:
                return False

            course = items[0]
            for key in ['name', 'color', 'default_start_time']:
                if key in updates:
                    course[key] = updates[key]

            self.container.replace_item(item=course['id'], body=course)
            logger.info(f"과정 수정: {course_id}")
            return True
        except Exception as e:
            logger.error(f"과정 수정 실패: {e}")
            return False

    def create_course(self, course):
        """과정 메타데이터만 생성 (엑셀 업로드 없이)"""
        try:
            self.container.create_item(body=course)
            logger.info(f"과정 생성: {course['name']}")
            return course['id']
        except Exception as e:
            logger.error(f"과정 생성 실패: {e}")
            return None

    def add_entry(self, course_id, entry):
        """과정에 개별 수업 일정 추가"""
        try:
            # 과정 존재 확인
            course_query = "SELECT * FROM c WHERE c.type = 'course' AND c.id = @course_id"
            course_docs = list(self.container.query_items(
                query=course_query,
                parameters=[{"name": "@course_id", "value": course_id}],
                enable_cross_partition_query=True
            ))
            if not course_docs:
                return None

            entry_id = entry.get('id') or self._generate_id("entry")
            entry_doc = {
                "id": entry_id,
                "type": "entry",
                "course_id": course_id,
                **{k: v for k, v in entry.items() if k != 'id'}
            }
            self.container.create_item(body=entry_doc)

            # entry_count 갱신
            course_doc = course_docs[0]
            course_doc['entry_count'] = course_doc.get('entry_count', 0) + 1
            self.container.replace_item(item=course_doc['id'], body=course_doc)

            logger.info(f"수업 일정 추가: {course_id} / {entry.get('class_name')}")
            return entry_id
        except Exception as e:
            logger.error(f"엔트리 추가 실패: {e}")
            return None

    def delete_entry(self, course_id, entry_id):
        """개별 수업 일정 삭제"""
        try:
            self.container.delete_item(item=entry_id, partition_key='entry')

            # entry_count 갱신
            course_query = "SELECT * FROM c WHERE c.type = 'course' AND c.id = @course_id"
            course_docs = list(self.container.query_items(
                query=course_query,
                parameters=[{"name": "@course_id", "value": course_id}],
                enable_cross_partition_query=True
            ))
            if course_docs:
                course_doc = course_docs[0]
                course_doc['entry_count'] = max(0, course_doc.get('entry_count', 1) - 1)
                self.container.replace_item(item=course_doc['id'], body=course_doc)

            logger.info(f"수업 일정 삭제: {course_id} / {entry_id}")
            return True
        except Exception as e:
            logger.error(f"엔트리 삭제 실패: {e}")
            return False
