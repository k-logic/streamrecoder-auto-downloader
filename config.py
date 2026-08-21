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

# 最新N件方式：ダッシュボードの新しい方から何件を確認対象にするか
# （同じ日に複数配信があっても取りこぼさないよう複数本を確認）
CHECK_LATEST_N = 4
# 1回の実行で落とす最大本数（暴走防止）
MAX_DOWNLOADS_PER_RUN = 20
