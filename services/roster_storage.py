"""
직원근무표 저장소 - Azure Cosmos DB 또는 로컬 JSON fallback
"""
import os
import json
import uuid
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

_roster_storage = None
ENTRY_FIELDS = ('date', 'category', 'title', 'people', 'note', 'raw_text', 'source_sheet')


def _generate_id():
    return f"roster_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def get_roster_storage():
    """저장소 싱글턴 인스턴스 반환"""
    global _roster_storage
    if _roster_storage is None:
        _roster_storage = CosmosRosterStorage() if Config.use_cosmos_db() else LocalJsonRosterStorage()
    return _roster_storage


def _month_prefixes(months):
    return [f"{y:04d}-{m:02d}" for y, m in months]


class LocalJsonRosterStorage:
    """로컬 JSON 파일 (data/roster.json)"""

    def __init__(self):
        self.filepath = Config.ROSTER_FILE
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            self._save({"entries": [], "uploads": []})
        logger.info("로컬 JSON 근무표 저장소 초기화 완료")

    def _load(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"entries": [], "uploads": []}

    def _save(self, data):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_entries(self, start=None, end=None):
        """[start, end) 범위의 항목 (YYYY-MM-DD 문자열 비교)"""
        entries = self._load().get('entries', [])
        if start:
            entries = [e for e in entries if e.get('date', '') >= start]
        if end:
            entries = [e for e in entries if e.get('date', '') < end]
        return sorted(entries, key=lambda e: e.get('date', ''))

    def replace_months(self, entries, months, file_name=''):
        """업로드한 월의 기존 항목을 모두 지우고 새 항목으로 교체"""
        data = self._load()
        prefixes = _month_prefixes(months)
        kept = [e for e in data.get('entries', []) if e.get('date', '')[:7] not in prefixes]
        removed = len(data.get('entries', [])) - len(kept)
        for e in entries:
            e.setdefault('id', _generate_id())
        data['entries'] = kept + entries
        data.setdefault('uploads', []).append({
            "file_name": file_name,
            "uploaded_at": datetime.now().isoformat(),
            "months": prefixes,
            "entry_count": len(entries),
        })
        self._save(data)
        logger.info(f"근무표 교체: {prefixes} (삭제 {removed}, 추가 {len(entries)})")
        return removed

    def get_uploads(self):
        return self._load().get('uploads', [])

    def add_entry(self, entry):
        data = self._load()
        entry['id'] = entry.get('id') or _generate_id()
        data.setdefault('entries', []).append(entry)
        self._save(data)
        return entry['id']

    def update_entry(self, entry_id, updates):
        data = self._load()
        for e in data.get('entries', []):
            if e.get('id') == entry_id:
                for k in ENTRY_FIELDS:
                    if k in updates:
                        e[k] = updates[k]
                self._save(data)
                return True
        return False

    def delete_entry(self, entry_id):
        data = self._load()
        before = len(data.get('entries', []))
        data['entries'] = [e for e in data.get('entries', []) if e.get('id') != entry_id]
        if len(data['entries']) < before:
            self._save(data)
            return True
        return False


class CosmosRosterStorage:
    """Azure Cosmos DB (기존 컨테이너, type='roster_entry' / 'roster_upload')"""

    def __init__(self):
        from azure.cosmos import CosmosClient, PartitionKey
        self.client = CosmosClient(Config.COSMOS_DB_ENDPOINT, Config.COSMOS_DB_KEY)
        self.database = self.client.create_database_if_not_exists(id=Config.COSMOS_DATABASE_NAME)
        self.container = self.database.create_container_if_not_exists(
            id=Config.COSMOS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/type")
        )
        logger.info("Azure Cosmos DB 근무표 저장소 초기화 완료")

    def _query(self, query, params=None):
        return list(self.container.query_items(
            query=query, parameters=params or [], partition_key='roster_entry'))

    def get_entries(self, start=None, end=None):
        query = "SELECT * FROM c WHERE c.type = 'roster_entry'"
        params = []
        if start:
            query += " AND c.date >= @start"
            params.append({"name": "@start", "value": start})
        if end:
            query += " AND c.date < @end"
            params.append({"name": "@end", "value": end})
        query += " ORDER BY c.date"
        return self._query(query, params)

    def replace_months(self, entries, months, file_name=''):
        removed = 0
        for prefix in _month_prefixes(months):
            olds = self._query(
                "SELECT c.id FROM c WHERE c.type = 'roster_entry' AND STARTSWITH(c.date, @p)",
                [{"name": "@p", "value": prefix}])
            for o in olds:
                self.container.delete_item(item=o['id'], partition_key='roster_entry')
            removed += len(olds)
        for e in entries:
            doc = {"id": e.get('id') or _generate_id(), "type": "roster_entry",
                   **{k: v for k, v in e.items() if k != 'id'}}
            self.container.create_item(body=doc)
        self.container.create_item(body={
            "id": f"roster_upload_{uuid.uuid4().hex[:12]}",
            "type": "roster_upload",
            "file_name": file_name,
            "uploaded_at": datetime.now().isoformat(),
            "months": _month_prefixes(months),
            "entry_count": len(entries),
        })
        logger.info(f"근무표 교체: {months} (삭제 {removed}, 추가 {len(entries)})")
        return removed

    def get_uploads(self):
        return list(self.container.query_items(
            query="SELECT * FROM c WHERE c.type = 'roster_upload' ORDER BY c.uploaded_at",
            partition_key='roster_upload'))

    def add_entry(self, entry):
        entry_id = entry.get('id') or _generate_id()
        doc = {"id": entry_id, "type": "roster_entry", **{k: v for k, v in entry.items() if k != 'id'}}
        self.container.create_item(body=doc)
        return entry_id

    def update_entry(self, entry_id, updates):
        try:
            doc = self.container.read_item(item=entry_id, partition_key='roster_entry')
        except Exception:
            return False
        for k in ENTRY_FIELDS:
            if k in updates:
                doc[k] = updates[k]
        self.container.replace_item(item=entry_id, body=doc)
        return True

    def delete_entry(self, entry_id):
        try:
            self.container.delete_item(item=entry_id, partition_key='roster_entry')
            return True
        except Exception as e:
            logger.error(f"근무표 항목 삭제 실패: {e}")
            return False
