import logging
from functools import wraps
from flask import jsonify

logger = logging.getLogger(__name__)


def handle_errors(f):
    """API 엔드포인트 에러 핸들링 데코레이터"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except FileNotFoundError as e:
            logger.warning(f"파일을 찾을 수 없음: {e}")
            return jsonify({"success": False, "error": "파일을 찾을 수 없습니다."}), 404
        except ValueError as e:
            logger.warning(f"잘못된 값: {e}")
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as e:
            logger.error(f"서버 오류: {e}", exc_info=True)
            return jsonify({"success": False, "error": "서버 내부 오류가 발생했습니다."}), 500
    return decorated
