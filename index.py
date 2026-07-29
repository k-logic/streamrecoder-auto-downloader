import time
import os
import glob
import shutil
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import config
from config import LOGIN_URL, DASHBOARD_URL, USER_NAME, PASSWORD, DOWNLOAD_DIR

# config.py に無ければデフォルトを使う（後方互換）
NAS_MOUNT_DIR = getattr(config, "NAS_MOUNT_DIR", "/mnt/nas_video")
PREFERRED_QUALITY = getattr(config, "PREFERRED_QUALITY", "720p")

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

driver.set_page_load_timeout(180)

# ヘッドレスモードでのダウンロード許可設定
driver.execute_cdp_cmd("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": DOWNLOAD_DIR
})

wait = WebDriverWait(driver, 120)


def dump_debug(tag):
    """失敗時にスクショとHTMLを保存し、後から原因を追えるようにする"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    try:
        driver.save_screenshot(f"debug_{tag}_{ts}.png")
        print(f"  デバッグ用スクショ: debug_{tag}_{ts}.png")
    except Exception as e:
        print(f"  スクショ保存失敗: {e}")
    try:
        with open(f"debug_{tag}_{ts}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"  デバッグ用HTML: debug_{tag}_{ts}.html (url={driver.current_url})")
    except Exception as e:
        print(f"  HTML保存失敗: {e}")


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

        # 5. ダウンロード実行
        #    ※ streamrecorder.io のプレイヤーが Video.js 化され、DOM構造が変わっている：
        #      旧: button.fa-download（雲アイコンが button 自身に付与）
        #      新: button.vjs-download-modal-button（fa-download は中の <i> アイコン）
        #      クリックでダウンロード用モーダルが開き、画質は button.dl-card で選ぶ
        download_menu_btn = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "button.vjs-download-modal-button")
        ))
        driver.execute_script("arguments[0].click();", download_menu_btn)
        time.sleep(1)

        # モーダル内の画質カードを取得（例: 1080p / 720p ...）
        quality_cards = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "button.dl-card")
        ))

        def card_label(c):
            return (c.get_attribute("innerText") or "").replace("\n", " ").strip()

        # 希望画質があれば優先、無ければ先頭（＝最高画質）にフォールバック
        want = PREFERRED_QUALITY.rstrip("p")  # "720p" -> "720"
        chosen = None
        for c in quality_cards:
            if want in card_label(c):
                chosen = c
                break
        if chosen is None:
            chosen = quality_cards[0]
            print(f"希望画質({PREFERRED_QUALITY})が見つからないため、最高画質にフォールバックします。")

        available = " / ".join(card_label(c).split(" ")[0] for c in quality_cards)
        print(f"選択可能な画質: [{available}] → 選択: {card_label(chosen)}")

        driver.execute_script("arguments[0].click();", chosen)
        print("ダウンロードを開始しました...")

        # ダウンロードが実際に開始したか確認（.crdownload / .mp4 の出現を待つ）
        start_deadline = time.time() + 60
        while time.time() < start_deadline:
            files = os.listdir(DOWNLOAD_DIR)
            if any(f.endswith(".crdownload") or f.endswith(".mp4") for f in files):
                print("ダウンロード開始を確認しました。")
                break
            time.sleep(2)
        else:
            raise RuntimeError("ダウンロードが開始されませんでした（.crdownload が生成されません）")

        # 6. ダウンロード完了検知
        print("ファイルの保存完了を待機中（大容量のため時間がかかります）...")
        while True:
            # .crdownloadファイルがある間はループ
            files = os.listdir(DOWNLOAD_DIR)
            if not any(".crdownload" in f for f in files):
                # mp4ファイルがフォルダにあるか最終確認
                mp4_files = glob.glob(os.path.join(DOWNLOAD_DIR, '*.mp4'))
                if mp4_files:
                    time.sleep(20)  # 書き込み完了の猶予
                    latest_file = max(mp4_files, key=os.path.getctime)
                    print(f"ローカルでの処理完了：{os.path.basename(latest_file)}")

                    # 7. NASへ転送 → ローカル削除 → 履歴保存
                    if os.path.ismount(NAS_MOUNT_DIR):
                        try:
                            nas_path = os.path.join(NAS_MOUNT_DIR, os.path.basename(latest_file))
                            print(f"NASへの転送を開始します: {nas_path}")

                            # NASへコピー（shutil.copy2はメタデータも維持します）
                            shutil.copy2(latest_file, nas_path)

                            # 転送成功を確認してからローカルを削除
                            if os.path.exists(nas_path):
                                print("NASへの転送成功を確認。ローカルファイルを削除します。")
                                os.remove(latest_file)
                                # 全ての工程が成功してから履歴に保存
                                save_downloaded_id(video_id)
                                print("完了しました。")
                            else:
                                print("エラー：NAS上にファイルが見当たりません。")
                        except Exception as e:
                            print(f"NAS転送中にエラーが発生しました: {e}")
                    else:
                        print(f"エラー：NASが {NAS_MOUNT_DIR} にマウントされていません。転送を中止します。")
                    break

            time.sleep(15)

except Exception as e:
    # 例外の種類が分からないと原因調査ができないので、型名・トレースバック・画面状態を残す
    print(f"エラーが発生しました: {type(e).__name__}: {e}")
    traceback.print_exc()
    try:
        dump_debug("error")
    except Exception:
        pass

finally:
    driver.quit()
    print("スクリプトの全工程を終了しました。")
