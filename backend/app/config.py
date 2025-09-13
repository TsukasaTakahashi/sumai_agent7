import os
import logging
from typing import Optional
from dotenv import load_dotenv

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env ファイルの読み込み（存在しなければ .env.example を使用）
env_file = ".env"
if not os.path.exists(env_file):
    env_file = ".env.example"
    logger.info(f"Using fallback config file: {env_file}")

load_dotenv(env_file)

# 設定値
API_KEY: Optional[str] = os.getenv("API_KEY")
DB_PATH: str = os.getenv("DB_PATH", "./data/props.db")
TZ: str = os.getenv("TZ", "Asia/Tokyo")

# 設定ログ出力（API_KEYは伏せる）
logger.info("Configuration loaded:")
logger.info(f"  API_KEY: {'***' if API_KEY else 'Not set'}")
logger.info(f"  DB_PATH: {DB_PATH}")
logger.info(f"  TZ: {TZ}")