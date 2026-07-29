import os

# --- 設定項目 ---
LOGIN_URL = "https://streamrecorder.io/login"
DASHBOARD_URL = "https://streamrecorder.io/userdashboard"
USER_NAME = "USER_ID"
PASSWORD = "PASSWORD"  # ここを実際のパスワードに書き換えてください
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")

# NAS（Ubuntu側マウントポイント）へ完了後に転送する。転送成功後ローカルは削除。
NAS_MOUNT_DIR = "/mnt/nas_video"
# 希望画質。プレイヤーに無ければ最高画質へ自動フォールバック。
PREFERRED_QUALITY = "720p"
