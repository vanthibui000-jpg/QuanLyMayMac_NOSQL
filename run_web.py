"""Chạy giao diện web: python run_web.py  rồi mở http://127.0.0.1:5000

Biến môi trường tùy chọn (xem .env.example):
  FLASK_SECRET_KEY  khóa cho flash message (bắt buộc đổi khi dùng ngoài máy demo)
  FLASK_DEBUG       1 để bật debug, 0 để tắt (mặc định 1 cho môi trường demo)
"""
import os

from dotenv import load_dotenv

from app.web import create_app

load_dotenv()
app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG", "1") == "1")
