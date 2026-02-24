"""
selenium 库常见用法演示用例
由于运行环境不一定有浏览器驱动，使用 unittest.mock 模拟 WebDriver 行为，
覆盖：启动/关闭浏览器、元素定位(8种)、点击/输入/清除、等待、JS执行、
      窗口切换、iframe切换、截图、下拉框、Cookie 操作
"""
from unittest.mock import MagicMock, PropertyMock, patch
from cytest import INFO, STEP, CHECK_POINT

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


force_tags = ['UI测试', 'selenium']


def _mock_driver():
    """创建一个模拟 WebDriver，涵盖常见 API"""
    driver = MagicMock()
    driver.title = '测试页面 - Cytest Demo'
    driver.current_url = 'https://example.com/dashboard'
    driver.page_source = '<html><body><h1>Hello Cytest</h1></body></html>'
    driver.window_handles = ['handle_main', 'handle_popup']
    driver.current_window_handle = 'handle_main'

    element = MagicMock()
    element.text = '提交'
    element.get_attribute.return_value = 'submit-btn'
    element.is_displayed.return_value = True
    element.is_enabled.return_value = True
    element.tag_name = 'button'

    driver.find_element.return_value = element
    driver.find_elements.return_value = [element, MagicMock(), MagicMock()]

    driver.execute_script.return_value = 'js_result_ok'
    driver.get_screenshot_as_file.return_value = True
    driver.get_cookies.return_value = [
        {'name': 'session', 'value': 'abc123', 'domain': '.example.com'}
    ]
    return driver, element


# ──────────────────── 启动和关闭浏览器 ────────────────────
class c_sel_001:
    name = '浏览器启动与关闭 - SEL-001'

    def teststeps(self):
        driver, _ = _mock_driver()

        STEP(1, '打开浏览器并访问页面')
        driver.get('https://example.com')
        driver.get.assert_called_once_with('https://example.com')
        INFO(f'当前页面标题: {driver.title}')
        CHECK_POINT('页面标题正确', driver.title == '测试页面 - Cytest Demo')

        STEP(2, '获取当前 URL')
        INFO(f'当前URL: {driver.current_url}')
        CHECK_POINT('URL 包含 dashboard', 'dashboard' in driver.current_url)

        STEP(3, '关闭浏览器')
        driver.quit()
        driver.quit.assert_called_once()
        CHECK_POINT('quit() 被调用', True)


# ──────────────────── 8 种元素定位方式 ────────────────────
class c_sel_002:
    name = '8种元素定位方式 - SEL-002'

    def teststeps(self):
        driver, elem = _mock_driver()

        locators = [
            (By.ID, 'username', 'ID 定位'),
            (By.NAME, 'password', 'NAME 定位'),
            (By.CLASS_NAME, 'login-btn', 'CLASS_NAME 定位'),
            (By.TAG_NAME, 'input', 'TAG_NAME 定位'),
            (By.LINK_TEXT, '忘记密码', 'LINK_TEXT 定位'),
            (By.PARTIAL_LINK_TEXT, '忘记', 'PARTIAL_LINK_TEXT 定位'),
            (By.CSS_SELECTOR, '#form > .btn', 'CSS_SELECTOR 定位'),
            (By.XPATH, '//button[@type="submit"]', 'XPATH 定位'),
        ]

        for i, (by, value, desc) in enumerate(locators, 1):
            STEP(i, f'{desc}: By.{by}="{value}"')
            el = driver.find_element(by, value)
            INFO(f'找到元素: tag={el.tag_name}, text={el.text}')
            CHECK_POINT(f'{desc} 成功', el is not None)


# ──────────────────── 元素交互：点击、输入、清除 ────────────────────
class c_sel_003:
    name = '元素交互操作 - SEL-003'

    def teststeps(self):
        driver, elem = _mock_driver()

        STEP(1, '输入文本到输入框')
        elem.send_keys('admin@example.com')
        elem.send_keys.assert_called_with('admin@example.com')
        CHECK_POINT('send_keys 调用成功', True)

        STEP(2, '清除输入框内容')
        elem.clear()
        elem.clear.assert_called_once()
        CHECK_POINT('clear 调用成功', True)

        STEP(3, '点击按钮')
        elem.click()
        elem.click.assert_called_once()
        CHECK_POINT('click 调用成功', True)

        STEP(4, '获取元素属性')
        attr = elem.get_attribute('id')
        INFO(f'元素 id 属性: {attr}')
        CHECK_POINT('get_attribute 返回值正确', attr == 'submit-btn')

        STEP(5, '检查元素状态')
        CHECK_POINT('元素可见', elem.is_displayed())
        CHECK_POINT('元素可用', elem.is_enabled())


# ──────────────────── 显式等待 ────────────────────
class c_sel_004:
    name = '显式等待 WebDriverWait - SEL-004'

    def teststeps(self):
        driver, elem = _mock_driver()

        STEP(1, '使用 WebDriverWait 等待元素可见')
        with patch.object(WebDriverWait, '__init__', return_value=None), \
             patch.object(WebDriverWait, 'until', return_value=elem):
            wait = WebDriverWait(driver, 10)
            result = wait.until(EC.visibility_of_element_located((By.ID, 'result')))
            INFO(f'等待到元素: {result.text}')
            CHECK_POINT('等待成功，元素已出现', result is not None)

        STEP(2, '演示等待超时的场景')
        INFO('实际项目中，若元素在超时时间内未出现，会抛出 TimeoutException')
        INFO('用法: WebDriverWait(driver, 10).until(EC.presence_of_element_located(...))')
        CHECK_POINT('等待机制说明完成', True)


# ──────────────────── JavaScript 执行 ────────────────────
class c_sel_005:
    name = 'JavaScript 执行 - SEL-005'

    def teststeps(self):
        driver, _ = _mock_driver()

        STEP(1, '执行同步 JS 脚本')
        result = driver.execute_script('return document.title;')
        INFO(f'JS 执行结果: {result}')
        CHECK_POINT('execute_script 返回正确', result == 'js_result_ok')

        STEP(2, '通过 JS 滚动页面')
        driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        driver.execute_script.assert_called()
        CHECK_POINT('滚动 JS 已执行', True)

        STEP(3, '通过 JS 修改元素样式')
        driver.execute_script("arguments[0].style.border='3px solid red';", MagicMock())
        CHECK_POINT('样式修改 JS 已执行', True)


# ──────────────────── 多窗口切换 ────────────────────
class c_sel_006:
    name = '多窗口切换 - SEL-006'

    def teststeps(self):
        driver, _ = _mock_driver()

        STEP(1, '获取所有窗口句柄')
        handles = driver.window_handles
        INFO(f'窗口句柄列表: {handles}')
        CHECK_POINT('存在多个窗口', len(handles) >= 2)

        STEP(2, '切换到新窗口')
        driver.switch_to.window(handles[1])
        driver.switch_to.window.assert_called_with('handle_popup')
        CHECK_POINT('切换到弹出窗口成功', True)

        STEP(3, '切换回主窗口')
        driver.switch_to.window(handles[0])
        CHECK_POINT('切换回主窗口成功', True)


# ──────────────────── iframe 切换 ────────────────────
class c_sel_007:
    name = 'iframe 切换 - SEL-007'

    def teststeps(self):
        driver, elem = _mock_driver()

        STEP(1, '切换到 iframe')
        driver.switch_to.frame('my_iframe')
        driver.switch_to.frame.assert_called_with('my_iframe')
        CHECK_POINT('切换到 iframe 成功', True)

        STEP(2, '在 iframe 内操作元素')
        el = driver.find_element(By.ID, 'inner_btn')
        el.click()
        CHECK_POINT('iframe 内元素操作成功', True)

        STEP(3, '切回主文档')
        driver.switch_to.default_content()
        driver.switch_to.default_content.assert_called_once()
        CHECK_POINT('切回主文档成功', True)


# ──────────────────── 浏览器截图 ────────────────────
class c_sel_008:
    name = '浏览器截图 - SEL-008'

    def teststeps(self):
        driver, _ = _mock_driver()

        STEP(1, '保存全屏截图')
        result = driver.get_screenshot_as_file('/tmp/screenshot.png')
        INFO(f'截图保存结果: {result}')
        CHECK_POINT('截图保存成功', result is True)

        STEP(2, '获取截图 base64（用于日志嵌入）')
        driver.get_screenshot_as_base64.return_value = 'iVBORw0KGgo...'
        b64 = driver.get_screenshot_as_base64()
        INFO(f'Base64 前20字符: {b64[:20]}')
        CHECK_POINT('Base64 截图获取成功', len(b64) > 0)


# ──────────────────── Cookie 操作 ────────────────────
class c_sel_009:
    name = 'Cookie 操作 - SEL-009'

    def teststeps(self):
        driver, _ = _mock_driver()

        STEP(1, '获取所有 Cookie')
        cookies = driver.get_cookies()
        INFO(f'当前 Cookies: {cookies}')
        CHECK_POINT('Cookie 列表非空', len(cookies) > 0)

        STEP(2, '添加 Cookie')
        driver.add_cookie({'name': 'token', 'value': 'xyz789'})
        driver.add_cookie.assert_called_with({'name': 'token', 'value': 'xyz789'})
        CHECK_POINT('Cookie 添加成功', True)

        STEP(3, '删除指定 Cookie')
        driver.delete_cookie('token')
        driver.delete_cookie.assert_called_with('token')
        CHECK_POINT('Cookie 删除成功', True)

        STEP(4, '清空所有 Cookie')
        driver.delete_all_cookies()
        driver.delete_all_cookies.assert_called_once()
        CHECK_POINT('所有 Cookie 已清空', True)


# ──────────────────── 查找多个元素 + 断言数量 ────────────────────
class c_sel_010:
    name = '查找多个元素 - SEL-010'

    def teststeps(self):
        driver, _ = _mock_driver()

        STEP(1, '使用 find_elements 查找多个元素')
        elements = driver.find_elements(By.CLASS_NAME, 'list-item')
        INFO(f'找到 {len(elements)} 个元素')
        CHECK_POINT('找到的元素数量 >= 2', len(elements) >= 2)

        STEP(2, '遍历元素并操作')
        for i, el in enumerate(elements):
            INFO(f'  第 {i+1} 个元素: tag={el.tag_name}')
        CHECK_POINT('遍历完成', True)


# ──────────────────── 数据驱动：多浏览器配置验证 ────────────────────
class c_sel_ddt:
    ddt_cases = [
        {'name': '浏览器配置验证 - Chrome - SEL-DDT-01',
         'para': {'browser': 'Chrome', 'headless': True, 'window_size': (1920, 1080)}},
        {'name': '浏览器配置验证 - Firefox - SEL-DDT-02',
         'para': {'browser': 'Firefox', 'headless': False, 'window_size': (1280, 720)}},
        {'name': '浏览器配置验证 - Edge - SEL-DDT-03',
         'para': {'browser': 'Edge', 'headless': True, 'window_size': (1440, 900)}},
    ]

    def teststeps(self):
        config = self.para
        STEP(1, f'验证 {config["browser"]} 浏览器配置')
        INFO(f'浏览器: {config["browser"]}')
        INFO(f'无头模式: {config["headless"]}')
        INFO(f'窗口尺寸: {config["window_size"]}')

        CHECK_POINT('浏览器名称非空', len(config['browser']) > 0)
        CHECK_POINT('窗口宽度 > 0', config['window_size'][0] > 0)
        CHECK_POINT('窗口高度 > 0', config['window_size'][1] > 0)
