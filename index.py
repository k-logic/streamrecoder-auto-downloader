import time
import os
import glob
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- 設定項目 ---
LOGIN_URL = "https://streamrecorder.io/login"
DASHBOARD_URL = "https://streamrecorder.io/userdashboard"
USER_NAME = "USER_ID"
PASSWORD = "PASSWORD"  # ここを実際のパスワードに書き換えてください
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
HISTORY_FILE = "download_history.txt"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# --- 履歴管理用関数 ---
def get_downloaded_ids():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_downloaded_id(video_id):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{video_id}\n")

# --- Chrome設定 ---
chrome_options = Options()
chrome_options.add_argument("--headless=new")  # ヘッドレスモード
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")  # 画面サイズ固定

prefs = {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "directory_upgrade": True,
    "safebrowsing.enabled": True
}
chrome_options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# ヘッドレスモードでのダウンロード許可設定
driver.execute_cdp_cmd("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": DOWNLOAD_DIR
})

wait = WebDriverWait(driver, 30)

try:
    # 1. ログイン処理
    print("ログインページにアクセス中...")
    driver.get(LOGIN_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(USER_NAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    
    login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    driver.execute_script("arguments[0].click();", login_btn)
    print("ログイン成功")
    
    # 2. ダッシュボードへ移動
    time.sleep(5)
    driver.get(DASHBOARD_URL)
    print("ダッシュボード読み込み完了")

    # 3. 最新動画のカード特定とID取得
    first_card = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".recordings-grid .recording-card:first-of-type")
    ))
    video_id = first_card.get_attribute("data-sr-mmclick-id")
    
    # 重複チェック
    if video_id in get_downloaded_ids():
        print(f"スキップ：ID {video_id} はすでに履歴に存在します。")
    else:
        print(f"新規動画（ID: {video_id}）の処理を開始します。")

        # 4. プレイヤー起動（JavaScriptで強制クリック）
        thumb = first_card.find_element(By.CSS_SELECTOR, ".recording-thumbnail-wrapper")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", thumb)
        time.sleep(2)
        driver.execute_script("arguments[0].click();", thumb)
        print("プレイヤーを起動しました。")

        # 5. ダウンロードボタン（雲のアイコン）の操作
        download_menu_btn = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "button.fa-download")
        ))
        driver.execute_script("arguments[0].click();", download_menu_btn)
        time.sleep(1)

        # 画質（720p）を選択してクリック
        quality_option = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//li//span[contains(text(), '720p')]")
        ))
        driver.execute_script("arguments[0].click();", quality_option)
        print("ダウンロードを開始しました...")

        # 6. ダウンロード完了検知
        print("ファイルの保存完了を待機中（大容量のため時間がかかります）...")
        time.sleep(20) # ダウンロード開始までの猶予
        
        while True:
            # .crdownloadファイルがある間はループ
            files = os.listdir(DOWNLOAD_DIR)
            if not any(".crdownload" in f for f in files):
                # mp4ファイルがフォルダにあるか最終確認
                mp4_files = glob.glob(os.path.join(DOWNLOAD_DIR, '*.mp4'))
                if mp4_files:
                    # 最新のファイルを特定
                    latest_file = max(mp4_files, key=os.path.getctime)
                    
                    # 7. リネームと履歴保存
                    new_filename = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
                    os.rename(latest_file, new_filename)
                    save_downloaded_id(video_id)
                    
                    print(f"ダウンロード完了：{os.path.basename(new_filename)}")
                    break
            
            time.sleep(15)

except Exception as e:
    print(f"エラーが発生しました: {e}")

finally:
    driver.quit()
    print("スクリプトの全工程を終了しました。")