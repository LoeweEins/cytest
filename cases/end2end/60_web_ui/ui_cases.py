from cytest import STEP, INFO, CHECK_POINT, GSTORE, SELENIUM_LOG_SCREEN


class cUI0001:
    name = "UI-0001-打开 Dashboard 登录页"
    tags = ["UI", "冒烟"]

    def teststeps(self):
        STEP(1, "检查 driver 与 WEB_BASE_URL")
        driver = getattr(GSTORE, "driver", None)
        url = getattr(GSTORE, "web_base_url", "") or ""
        CHECK_POINT("driver 已初始化", driver is not None)
        CHECK_POINT("web_base_url 非空", bool(url))

        STEP(2, "打开 dashboard 页面并检查标题包含 Saleor")
        try:
            driver.get(url)
        except Exception as e:
            INFO(f"打开页面失败：{e}")
            SELENIUM_LOG_SCREEN(driver)
            CHECK_POINT("页面应能打开", False)
            return

        title = driver.title or ""
        CHECK_POINT("页面 title 非空", bool(title), failStop=False)
        CHECK_POINT("title 包含 Saleor（常见）", ("saleor" in title.lower()) or ("dashboard" in title.lower()), failStop=False)


class cUI0002:
    name = "UI-0002-登录（若已配置账号密码）"
    tags = ["UI", "回归"]

    def teststeps(self):
        driver = getattr(GSTORE, "driver", None)
        base = getattr(GSTORE, "web_base_url", "") or ""
        CHECK_POINT("driver 已初始化", driver is not None)
        CHECK_POINT("web_base_url 非空", bool(base))

        # 复用本地私有配置（与 API 用例一致）
        try:
            from lib.local_secrets import SALEOR_TEST_EMAIL as email, SALEOR_TEST_PASSWORD as pwd  # type: ignore
        except Exception:
            email, pwd = "", ""

        email = (email or "").strip()
        pwd = (pwd or "").strip()
        if not (email and pwd):
            raise RuntimeError("BLOCKED: 未配置测试账号密码（lib/local_secrets.py）")

        STEP(1, "打开登录页")
        driver.get(base)

        STEP(2, "填写邮箱和密码并提交")
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
        except Exception as e:
            raise RuntimeError(f"BLOCKED: selenium 组件不可用：{e}")

        wait_s = int(getattr(GSTORE, "ui_wait_s", 10))
        try:
            email_el = WebDriverWait(driver, wait_s).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']")))
            pwd_el = driver.find_element(By.CSS_SELECTOR, "input[type='password'], input[name='password']")
            email_el.clear()
            email_el.send_keys(email)
            pwd_el.clear()
            pwd_el.send_keys(pwd)

            # Dashboard 登录按钮通常是 submit
            btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            btn.click()
        except Exception as e:
            INFO(f"登录表单操作失败：{e}")
            SELENIUM_LOG_SCREEN(driver)
            CHECK_POINT("能定位登录表单并提交", False)
            return

        STEP(3, "等待登录后页面稳定（URL 或标题变化）")
        try:
            WebDriverWait(driver, wait_s).until(lambda d: "login" not in (d.current_url or "").lower())
        except Exception:
            # 可能仍在 login（密码错误/权限问题）
            SELENIUM_LOG_SCREEN(driver)
            CHECK_POINT("登录后应离开 login 页面", False)
            return

        CHECK_POINT("登录后 URL 非空", bool(driver.current_url), failStop=False)

