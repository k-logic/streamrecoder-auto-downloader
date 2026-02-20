# StreamRecorder Auto Downloader

streamrecorder.io から最新の動画を自動でダウンロードし、NAS（Ubuntuマウント環境）へ保存するPythonスクリプトです。

## 機能
- ヘッドレスモードでの自動ログイン・ダウンロード
- 二重ダウンロード防止機能（履歴管理）
- ローカルへの一時保存後のNASへの自動転送
- 転送完了後のローカルファイル自動削除

## 動作環境
- OS: Ubuntu (推奨)
- Python 3.10+
- Google Chrome & ChromeDriver
- Synology NAS (SMBマウント済みであること)

## セットアップ

1. リポジトリをクローン:
   ```bash
   git clone [https://github.com/あなたのユーザー名/リポジトリ名.git](https://github.com/あなたのユーザー名/リポジトリ名.git)
   cd リポジトリ名# auto-dl-streamrecoder
   
## Python依存モジュールのインストール
pip install -r requirements.txt