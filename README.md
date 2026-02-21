# StreamRecorder Auto Downloader

streamrecorder.io から最新の録画動画を自動でダウンロードする Python スクリプトです。
ヘッドレス Chrome を使ったブラウザ自動操作により、ログインからダウンロードまでを無人で実行します。

## 機能

- ヘッドレス Chrome による自動ログイン・ダウンロード
- ダッシュボードから最新動画を自動検出
- 720p 画質での自動ダウンロード
- 履歴ファイルによる二重ダウンロード防止
- ダウンロード完了の自動検知とファイルリネーム

## 動作環境

- Python 3.10+
- Google Chrome
- OS: Ubuntu（推奨）/ macOS / Windows

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/your-username/streamrecoder-auto-downloader.git
cd streamrecoder-auto-downloader
```

### 2. 仮想環境の作成と有効化

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. 認証情報の設定

`index.py` 内の以下の項目を自分のアカウント情報に書き換えてください。

```python
USER_NAME = "あなたのユーザーID"
PASSWORD = "あなたのパスワード"
```

> **注意**: 認証情報がソースコードに直接記載される形式です。公開リポジトリにプッシュしないよう注意してください。

## 使い方

```bash
python index.py
```

実行すると以下の処理が自動で行われます：

1. streamrecorder.io にログイン
2. ダッシュボードから最新の録画動画を取得
3. 720p でダウンロードを開始
4. ダウンロード完了後、`downloads/` フォルダに `{動画ID}.mp4` として保存
5. 履歴ファイル（`download_history.txt`）に記録し、次回以降の重複を防止

既にダウンロード済みの動画はスキップされます。

### 定期実行（cron）

cron で定期的にチェック・ダウンロードを行う場合の設定例：

```bash
# 毎時0分に実行
0 * * * * cd /path/to/streamrecoder-auto-downloader && /path/to/venv/bin/python index.py >> cron.log 2>&1
```

## ファイル構成

```
streamrecoder-auto-downloader/
├── index.py                 # メインスクリプト
├── requirements.txt         # Python 依存パッケージ
├── downloads/               # ダウンロードされた動画の保存先（自動作成）
├── download_history.txt     # ダウンロード済み動画IDの履歴（自動作成）
└── README.md
```

## 依存パッケージ

| パッケージ | 用途 |
|-----------|------|
| selenium | ブラウザ自動操作 |
| webdriver-manager | ChromeDriver の自動管理 |

## 注意事項

- 初回実行時に ChromeDriver が自動でダウンロードされます
- 大容量動画の場合、ダウンロード完了まで時間がかかります
- streamrecorder.io の UI 変更により動作しなくなる可能性があります
- 認証情報の取り扱いには十分注意してください
