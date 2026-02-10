import os
from datetime import timedelta

class Config:
    """애플리케이션 설정"""

    # 보안
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'timetable-dashboard-secret-key'

    # 파일 업로드
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

    # 로컬 JSON 저장 (Cosmos DB fallback)
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    COURSES_FILE = os.path.join(DATA_DIR, 'courses.json')

    # Azure Cosmos DB
    COSMOS_DB_ENDPOINT = os.environ.get('COSMOS_DB_ENDPOINT')
    COSMOS_DB_KEY = os.environ.get('COSMOS_DB_KEY')
    COSMOS_DATABASE_NAME = 'TimetableDashboardDB'
    COSMOS_CONTAINER_NAME = 'ScheduleData'

    # 시간표 기본값
    DEFAULT_START_TIME = '09:00'
    DEFAULT_CLASS_HOURS = 8

    # 시간대
    TIMEZONE_OFFSET = timedelta(hours=9)  # KST

    # 과정 색상 프리셋
    COURSE_COLORS = [
        '#4A90D9',  # Blue
        '#E85D75',  # Rose
        '#50C878',  # Emerald
        '#F5A623',  # Amber
        '#9B59B6',  # Purple
        '#1ABC9C',  # Teal
        '#E74C3C',  # Red
        '#34495E',  # Dark Slate
        '#3498DB',  # Sky Blue
        '#E67E22',  # Orange
        '#2ECC71',  # Green
        '#E91E63',  # Pink
    ]

    # 로그
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    LOG_LEVEL = 'INFO'

    # 서버
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

    @classmethod
    def use_cosmos_db(cls):
        """Cosmos DB 사용 여부 판단"""
        return bool(cls.COSMOS_DB_ENDPOINT and cls.COSMOS_DB_KEY)
