import os
from cytest import INFO, GSTORE

from lib.web_ui import UiBlocked, build_chrome_driver

force_tags = ["WebUI", "UI"]
default_tags = ["冒烟"]

def suite_setup():
    # UI 套件建议用环境变量控制被测页面（默认 dashboard）
    GSTORE.web_base_url = os.getenv("WEB_BASE_URL", "http://localhost:9000/").strip() or "http://localhost:9000/"
    GSTORE.ui_wait_s = int(os.getenv("UI_WAIT_S", "10"))

    INFO(f"[60_web_ui] suite_setup, base_url={GSTORE.web_base_url!r}")

    # 初始化 ChromeDriver
    try:
        driver = build_chrome_driver()
    except UiBlocked as e:
        raise RuntimeError(f"BLOCKED: {e}")

    driver.set_page_load_timeout(int(os.getenv("UI_PAGELOAD_S", "30")))
    driver.implicitly_wait(GSTORE.ui_wait_s)
    GSTORE.driver = driver
    INFO("[60_web_ui] ChromeDriver ready")

def suite_teardown():
    INFO("[60_web_ui] suite_teardown")
    driver = getattr(GSTORE, "driver", None)
    if driver:
        try:
            driver.quit()
        except Exception as e:
            INFO(f"[60_web_ui] driver.quit() 失败：{e}")
