import os
from typing import Optional


class UiBlocked(RuntimeError):
    pass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default


def build_chrome_driver():
    """
    创建 Chrome WebDriver（支持 headless / driver path）。

    环境变量：
    - CHROMEDRIVER_PATH: chromedriver 路径（可选；不设则要求在 PATH 中）
    - CHROME_HEADLESS: yes/no（默认 yes）
    - CHROME_WINDOW_SIZE: 例如 1440,900
    - CHROME_BINARY: Chrome 可执行文件路径（可选）
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except Exception as e:
        raise UiBlocked(f"未安装 selenium 或导入失败：{e}")

    headless = _env_bool("CHROME_HEADLESS", True)
    window_size = os.getenv("CHROME_WINDOW_SIZE", "1440,900").strip() or "1440,900"
    chrome_binary = os.getenv("CHROME_BINARY", "").strip()
    driver_path = os.getenv("CHROMEDRIVER_PATH", "").strip()

    options = Options()
    if headless:
        # Selenium4 推荐用 --headless=new
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={window_size}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=zh-CN")

    if chrome_binary:
        options.binary_location = chrome_binary

    service: Optional[Service] = None
    if driver_path:
        service = Service(executable_path=driver_path)

    try:
        if service:
            return webdriver.Chrome(service=service, options=options)
        return webdriver.Chrome(options=options)
    except Exception as e:
        hint = "请确认：Chrome 已安装、chromedriver 可用（PATH 或 CHROMEDRIVER_PATH）、版本匹配。"
        raise UiBlocked(f"启动 ChromeDriver 失败：{e}. {hint}")

