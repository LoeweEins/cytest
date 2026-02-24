"""
requests 库常见用法演示用例
覆盖：GET / POST / 请求头 / 超时 / JSON解析 / Session / 状态码校验 / 文件下载
"""
import requests
from cytest import INFO, STEP, CHECK_POINT


force_tags = ['接口测试', 'requests']


# ──────────────────── GET 请求：获取公开 API 数据 ────────────────────
class c_req_001:
    name = 'GET 请求 - 获取公开API数据 - REQ-001'

    def teststeps(self):
        STEP(1, '发送 GET 请求到 httpbin.org/get')
        resp = requests.get('https://httpbin.org/get', timeout=10)
        INFO(f'状态码: {resp.status_code}')
        CHECK_POINT('状态码应为200', resp.status_code == 200)

        STEP(2, '检查响应 JSON 结构')
        data = resp.json()
        INFO(f'响应URL字段: {data.get("url")}')
        CHECK_POINT('响应 JSON 包含 url 字段', 'url' in data)


# ──────────────────── GET 请求：带查询参数 ────────────────────
class c_req_002:
    name = 'GET 请求 - 带查询参数 - REQ-002'

    def teststeps(self):
        STEP(1, '使用 params 参数发送 GET 请求')
        params = {'page': 2, 'per_page': 5, 'keyword': '测试'}
        resp = requests.get('https://httpbin.org/get', params=params, timeout=10)
        INFO(f'最终URL: {resp.url}')
        CHECK_POINT('状态码应为200', resp.status_code == 200)

        STEP(2, '验证参数已正确编码到 URL 中')
        data = resp.json()
        args = data.get('args', {})
        INFO(f'服务端收到的参数: {args}')
        CHECK_POINT('page 参数正确', args.get('page') == '2')
        CHECK_POINT('per_page 参数正确', args.get('per_page') == '5')


# ──────────────────── POST 请求：发送 JSON 数据 ────────────────────
class c_req_003:
    name = 'POST 请求 - 发送JSON数据 - REQ-003'

    def teststeps(self):
        STEP(1, '发送 JSON 格式的 POST 请求')
        payload = {'username': 'admin', 'password': 'secret123'}
        resp = requests.post('https://httpbin.org/post', json=payload, timeout=10)
        INFO(f'状态码: {resp.status_code}')
        CHECK_POINT('状态码应为200', resp.status_code == 200)

        STEP(2, '验证服务端接收的 JSON 数据')
        data = resp.json()
        received = data.get('json', {})
        INFO(f'服务端收到: {received}')
        CHECK_POINT('username 正确', received.get('username') == 'admin')
        CHECK_POINT('password 正确', received.get('password') == 'secret123')


# ──────────────────── POST 请求：发送表单数据 ────────────────────
class c_req_004:
    name = 'POST 请求 - 发送表单数据 - REQ-004'

    def teststeps(self):
        STEP(1, '使用 data 参数发送表单 POST')
        form_data = {'email': 'test@example.com', 'message': '你好世界'}
        resp = requests.post('https://httpbin.org/post', data=form_data, timeout=10)
        CHECK_POINT('状态码应为200', resp.status_code == 200)

        STEP(2, '验证 Content-Type 为 form-urlencoded')
        data = resp.json()
        content_type = data.get('headers', {}).get('Content-Type', '')
        INFO(f'Content-Type: {content_type}')
        CHECK_POINT('Content-Type 包含 urlencoded', 'urlencoded' in content_type)

        STEP(3, '验证表单数据正确')
        form = data.get('form', {})
        CHECK_POINT('email 正确', form.get('email') == 'test@example.com')


# ──────────────────── 自定义请求头 ────────────────────
class c_req_005:
    name = '自定义请求头 - REQ-005'

    def teststeps(self):
        STEP(1, '携带自定义 Headers 发送请求')
        headers = {
            'Authorization': 'Bearer my_token_abc123',
            'X-Custom-Header': 'cytest-framework',
            'Accept': 'application/json',
        }
        resp = requests.get('https://httpbin.org/headers', headers=headers, timeout=10)
        CHECK_POINT('状态码应为200', resp.status_code == 200)

        STEP(2, '验证服务端收到的自定义 Header')
        received_headers = resp.json().get('headers', {})
        INFO(f'Authorization: {received_headers.get("Authorization")}')
        CHECK_POINT('Authorization 头正确', received_headers.get('Authorization') == 'Bearer my_token_abc123')
        CHECK_POINT('X-Custom-Header 正确', received_headers.get('X-Custom-Header') == 'cytest-framework')


# ──────────────────── 请求超时处理 ────────────────────
class c_req_006:
    name = '请求超时处理 - REQ-006'

    def teststeps(self):
        STEP(1, '发送一个会延迟2秒的请求（设置3秒超时）')
        resp = requests.get('https://httpbin.org/delay/2', timeout=5)
        CHECK_POINT('请求成功（未超时）', resp.status_code == 200)

        STEP(2, '模拟超时：给一个极短的超时时间')
        timed_out = False
        try:
            requests.get('https://httpbin.org/delay/5', timeout=0.5)
        except requests.exceptions.Timeout:
            timed_out = True
            INFO('捕获到 Timeout 异常 ✓')
        except requests.exceptions.ConnectionError:
            timed_out = True
            INFO('捕获到 ConnectionError（超时导致）✓')
        CHECK_POINT('超时异常被正确捕获', timed_out)


# ──────────────────── Session 会话保持（Cookie） ────────────────────
class c_req_007:
    name = 'Session 会话保持 - REQ-007'

    def teststeps(self):
        STEP(1, '使用 Session 设置 Cookie')
        session = requests.Session()
        session.get('https://httpbin.org/cookies/set/session_id/abc123', timeout=10, allow_redirects=True)

        STEP(2, '后续请求自动携带 Cookie')
        resp = session.get('https://httpbin.org/cookies', timeout=10)
        cookies = resp.json().get('cookies', {})
        INFO(f'Session 中的 Cookies: {cookies}')
        CHECK_POINT('Cookie session_id 存在', 'session_id' in cookies)
        CHECK_POINT('Cookie 值正确', cookies.get('session_id') == 'abc123')

        session.close()


# ──────────────────── 响应状态码判断 ────────────────────
class c_req_008:
    name = '响应状态码判断 - REQ-008'

    def teststeps(self):
        STEP(1, '请求 200 OK')
        resp = requests.get('https://httpbin.org/status/200', timeout=10)
        CHECK_POINT('200 状态码', resp.status_code == 200)

        STEP(2, '请求 404 Not Found')
        resp = requests.get('https://httpbin.org/status/404', timeout=10)
        INFO(f'实际状态码: {resp.status_code}')
        CHECK_POINT('404 状态码', resp.status_code == 404)

        STEP(3, '请求 500 Server Error')
        resp = requests.get('https://httpbin.org/status/500', timeout=10)
        CHECK_POINT('500 状态码', resp.status_code == 500)

        STEP(4, '使用 raise_for_status 捕获异常')
        caught = False
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            caught = True
            INFO(f'捕获到 HTTPError: {type(e).__name__}')
        CHECK_POINT('raise_for_status 抛出 HTTPError', caught)


# ──────────────── 数据驱动：批量接口验证 ────────────────
class c_req_ddt:
    ddt_cases = [
        {'name': '批量验证 - /get 返回200 - REQ-DDT-01', 'para': ['get', 200]},
        {'name': '批量验证 - /post 返回200 - REQ-DDT-02', 'para': ['post', 200]},
        {'name': '批量验证 - /status/418 返回418 - REQ-DDT-03', 'para': ['status/418', 418]},
    ]

    def teststeps(self):
        endpoint, expected_code = self.para
        url = f'https://httpbin.org/{endpoint}'
        STEP(1, f'请求 {url}')

        if 'post' in endpoint:
            resp = requests.post(url, timeout=10)
        else:
            resp = requests.get(url, timeout=10)

        INFO(f'实际状态码: {resp.status_code}，期望: {expected_code}')
        CHECK_POINT(f'状态码应为 {expected_code}', resp.status_code == expected_code)
