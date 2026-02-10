"""
Timetable Dashboard - 교육기관 시간표 통합 캘린더 대시보드
"""
import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from config import Config
from routes import main_bp, api_bp


def create_app():
    """Flask 애플리케이션 팩토리"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # 필수 디렉토리 생성
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    os.makedirs(Config.LOG_DIR, exist_ok=True)

    # Blueprint 등록
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # 보안 헤더
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'"
        )
        return response

    return app


# Azure WebApp 호환을 위한 전역 인스턴스
app = create_app()


def main():
    """메인 실행 함수"""
    print("=" * 50)
    print("  Timetable Dashboard")
    print("=" * 50)
    print(f"  http://localhost:{Config.PORT}/")
    storage = "Azure Cosmos DB" if Config.use_cosmos_db() else "로컬 JSON 파일"
    print(f"  저장소: {storage}")
    print("=" * 50)

    if Config.DEBUG:
        app.run(debug=True, host=Config.HOST, port=Config.PORT)
    else:
        try:
            from waitress import serve
            print(f"Waitress 서버 시작 (포트: {Config.PORT})")
            serve(app, host=Config.HOST, port=Config.PORT)
        except Exception as e:
            print(f"서버 시작 오류: {e}")


if __name__ == '__main__':
    main()
