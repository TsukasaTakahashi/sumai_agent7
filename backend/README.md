# 住まいエージェント バックエンド

## セットアップ手順

### 1. Python 仮想環境の作成と有効化

```bash
python -m venv venv
source venv/bin/activate  # Windows の場合: venv\Scripts\activate
```

### 2. パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. 環境設定ファイルの作成

```bash
cp .env.example .env
```

`.env` ファイルを編集して、必要に応じて設定値を変更してください：

```
API_KEY=your_api_key_here
DB_PATH=./data/props.db
TZ=Asia/Tokyo
```

## 起動方法

```bash
uvicorn app.main:app --reload
```

サーバーは http://127.0.0.1:8000 で起動します。

## 疎通確認

以下のコマンドでヘルスチェックを実行できます：

```bash
curl http://127.0.0.1:8000/health
```

期待される応答：
```json
{"status":"ok"}
```

## データベース

`DB_PATH` で指定されたパス（デフォルト: `./data/props.db`）に不動産物件データベースを配置してください。
現在は空のプレースホルダーファイルですが、後で実際のデータベースファイルに置き換える予定です。

## 開発時の注意

- CORS は開発用に全オリジンからのアクセスを許可しています
- プロダクション環境では適切な CORS 設定に変更してください