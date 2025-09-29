import os
import logging
from typing import Optional
from dotenv import load_dotenv

# ログ設定
logging.basicConfig(level=logging.INFO)
# property_agentのログレベルをDEBUGに設定
logging.getLogger('app.property_agent').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

# .env ファイルの読み込み（存在しなければ .env.example を使用）
# 絶対パスを使用して確実に読み込み
base_dir = os.path.dirname(os.path.dirname(__file__))  # backend/
env_path = os.path.join(base_dir, ".env")
env_example_path = os.path.join(base_dir, ".env.example")

if os.path.exists(env_path):
    env_file = env_path
    logger.info("Using .env file")
else:
    env_file = env_example_path
    logger.info(f"Using fallback config file: {env_file}")

load_dotenv(env_file)

# 設定値
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
DB_PATH: str = os.getenv("DB_PATH", "./data/properties_with_geocoding.db")
TZ: str = os.getenv("TZ", "Asia/Tokyo")

# 設定ログ出力（API_KEYは伏せる）
logger.info("Configuration loaded:")
logger.info(f"  OPENAI_API_KEY: {'***' if OPENAI_API_KEY else 'Not set'}")
logger.info(f"  DB_PATH: {DB_PATH}")
logger.info(f"  TZ: {TZ}")