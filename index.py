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
# 録画ページ（2026-11 UI刷新: トークンで個別ページを開く）
RECORDING_BASE = getattr(config, "RECORDING_BASE", "https://streamrecorder.io/userrecordings/recording/")
NAS_MOUNT_DIR = getattr(config, "NAS_MOUNT_DIR", "/mnt/nas_video")
PREFERRED_QUALITY = getattr(config, "PREFERRED_QUALITY", "720p")
CHECK_LATEST_N = getattr(config, "CHECK_LATEST_N", 4)
MAX_DOWNLOADS_PER_RUN = getattr(config, "MAX_DOWNLOADS_PER_RUN", 20)
PER_VIDEO_TIMEOUT = getattr(config, "PER_VIDEO_TIMEOUT", 3 * 60 * 60)

HISTORY_FILE = "download_history.txt"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


# --- 履歴管理用関数 ---
def get_downloaded_ids():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f)


def save_downloaded_id(video_id):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{video_id}\n")


def clean_partial_downloads():
    """中断で残った .crdownload / 余計な html を掃除（ディスク詰まり・誤検知の防止）"""
    for pat in ("*.crdownload", "*.html", "*.htm"):
        for p in glob.glob(os.path.join(DOWNLOAD_DIR, pat)):
            try:
                os.remove(p)
                print(f"  掃除: {os.path.basename(p)}")
            except Exception as e:
                print(f"  掃除失敗: {e}")


# --- Chrome設定 ---
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

prefs = {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "directory_upgrade": True,
    "safebrowsing.enabled": True,
}
chrome_options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
driver.set_page_load_timeout(180)
driver.execute_cdp_cmd("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": DOWNLOAD_DIR,
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


def open_dashboard():
    driver.get(DASHBOARD_URL)
    wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".recordings-grid .recording-card")))


def download_one(video_id, token):
    """トークンの録画ページを開いてDL → NAS転送 → 履歴保存。成功でTrue"""
    clean_partial_downloads()

    # 録画ページを直接開く（新UI: /userrecordings/recording/<token>）
    driver.get(RECORDING_BASE + token)

    # ダウンロードボタン（新プレイヤー srp2）
    dl_btn = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "button.srp2-dl-btn")))
    driver.execute_script("arguments[0].click();", dl_btn)
    time.sleep(1)

    # ダウンロード用の行（画質ごとの直リンク a.srp2-dlrow）
    rows = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "a.srp2-dlrow")))

    def row_label(r):
        return (r.get_attribute("aria-label") or r.text or "").replace("\n", " ").strip()

    want = PREFERRED_QUALITY.rstrip("p")  # "720p" -> "720"
    chosen = None
    for r in rows:
        if want in row_label(r):
            chosen = r
            break
    if chosen is None:
        chosen = rows[0]
        print(f"  希望画質({PREFERRED_QUALITY})なし → 先頭にフォールバック")
    available = " / ".join(row_label(r) for r in rows)
    print(f"  画質候補: [{available}] → 選択 {row_label(chosen)}")

    driver.execute_script("arguments[0].click();", chosen)
    print("  ダウンロード開始...")

    # ダウンロードが実際に開始したか確認
    start_deadline = time.time() + 60
    while time.time() < start_deadline:
        files = os.listdir(DOWNLOAD_DIR)
        if any(f.endswith(".crdownload") or f.endswith(".mp4") for f in files):
            break
        time.sleep(2)
    else:
        raise RuntimeError("ダウンロードが開始されませんでした")

    # 完了待ち（上限つき）
    deadline = time.time() + PER_VIDEO_TIMEOUT
    while time.time() < deadline:
        files = os.listdir(DOWNLOAD_DIR)
        if not any(f.endswith(".crdownload") for f in files):
            mp4_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.mp4"))
            if mp4_files:
                time.sleep(20)  # 書き込み完了の猶予
                latest_file = max(mp4_files, key=os.path.getctime)
                print(f"  ローカル完了: {os.path.basename(latest_file)}")

                # NAS転送 → ローカル削除 → 履歴
                if not os.path.ismount(NAS_MOUNT_DIR):
                    raise RuntimeError(f"NAS未マウント({NAS_MOUNT_DIR})のため転送中止")
                nas_path = os.path.join(NAS_MOUNT_DIR, os.path.basename(latest_file))
                print(f"  NAS転送: {nas_path}")
                shutil.copy2(latest_file, nas_path)
                if not os.path.exists(nas_path):
                    raise RuntimeError("NAS上にファイルが見当たりません")
                os.remove(latest_file)
                save_downloaded_id(video_id)
                print("  完了（履歴記録）")
                return True
        time.sleep(15)

    raise RuntimeError("ダウンロードが時間内に完了しませんでした")


try:
    # 1. ログイン
    print("ログインページにアクセス中...")
    driver.get(LOGIN_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(USER_NAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    driver.execute_script("arguments[0].click();", login_btn)
    print("ログイン成功")
    time.sleep(5)

    # 2. ダッシュボードの表示中カードから (ID, token) を収集（新しい順）
    open_dashboard()
    time.sleep(1)
    cards = driver.find_elements(By.CSS_SELECTOR, ".recordings-grid .recording-card")
    pairs = []
    for c in cards:
        vid = c.get_attribute("data-sr-mmclick-id")
        tok = c.get_attribute("data-sr-mmclick-token")
        if vid and tok:
            pairs.append((vid, tok))
    target = pairs[:CHECK_LATEST_N]

    downloaded = get_downloaded_ids()
    # 未取得のみ・古い順（数値昇順）
    todo = sorted((p for p in target if p[0] not in downloaded), key=lambda p: int(p[0]))

    # テスト用: SR_ONLY=<id> で1本だけ処理（本番運用では未設定）
    _only = os.environ.get("SR_ONLY")
    if _only:
        todo = [p for p in pairs if p[0] == _only] or todo
        todo = todo[:1]
        print(f"[TESTモード] SR_ONLY={_only}")

    print(f"表示{len(pairs)}件 / 確認対象{len(target)}件(最新{CHECK_LATEST_N}) / 未取得{len(todo)}件")
    if not todo:
        print("新規動画はありません（すべて取得済み）。")
    else:
        if len(todo) > MAX_DOWNLOADS_PER_RUN:
            print(f"※ 上限{MAX_DOWNLOADS_PER_RUN}本まで。残りは次回実行で継続します。")
            todo = todo[:MAX_DOWNLOADS_PER_RUN]

        ok, ng = 0, 0
        for idx, (vid, tok) in enumerate(todo, start=1):
            print(f"===== [{idx}/{len(todo)}] ID={vid} =====")
            try:
                download_one(vid, tok)
                ok += 1
            except Exception as e:
                ng += 1
                print(f"  失敗: {type(e).__name__}: {e}")
                try:
                    dump_debug(f"vid{vid}")
                except Exception:
                    pass
                clean_partial_downloads()
        print(f"===== 完了: 成功{ok}本 / 失敗{ng}本 =====")

except Exception as e:
    print(f"エラーが発生しました: {type(e).__name__}: {e}")
    traceback.print_exc()
    try:
        dump_debug("fatal")
    except Exception:
        pass

finally:
    driver.quit()
    print("スクリプトの全工程を終了しました。")
