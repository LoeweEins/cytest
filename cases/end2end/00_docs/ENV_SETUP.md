# ENV_SETUP（对接指定 Saleor 环境，跑通 Auth 用例）

```bash
cd /path/to/saleor-platform
docker compose up
```

> 目标：让 `cases/end2end/10_auth/` 的鉴权用例 **真实可跑通**（`tokenCreate / tokenVerify / tokenRefresh / me`）。  
> 前提：你需要一个“真正的 Saleor GraphQL API Endpoint”（可 `POST /graphql/`）。  
> 注意：很多“storefront demo”页面路径看起来是 `/graphql/`，但可能并不提供可用的 GraphQL API POST（会出现 308/405）。

---

## 1. 你需要准备什么？

### 1.1 必须：Saleor GraphQL API URL

- **环境变量名**：`SALEOR_GRAPHQL_URL`
- **格式**：`https://<your-saleor-domain>/graphql/`
- **要求**：对该 URL 发送 HTTP `POST`（JSON body：`{query, variables}`）必须能返回 GraphQL JSON。

> 如果你使用 Saleor Cloud，域名通常形如：`https://{your_store}.saleor.cloud/graphql/`（以你实际环境为准）。

### 1.2 可选：用于 `tokenCreate` 的测试账号

如果你希望 `AUTH-0002~0005` 全部跑通，需要提供可用的 Email/Password：

- `SALEOR_TEST_EMAIL`
- `SALEOR_TEST_PASSWORD`

如果不提供账号密码：
- `AUTH-0001`（匿名 shop 查询）仍可跑
- 其余用例会在步骤 1 判定“无账号/无 token”后 **跳过但不报错**（用于 Demo 环境也更安全）

---

## 2. 本仓库的 Auth 用例对应 Saleor 文档

Saleor 官方文档（鉴权部分）：
- `tokenCreate`：`https://docs.saleor.io/api-reference/authentication/mutations/token-create`
- `tokenVerify`：`https://docs.saleor.io/api-reference/authentication/mutations/token-verify`
- `tokenRefresh`：`https://docs.saleor.io/api-reference/authentication/mutations/token-refresh`
- `me`：`https://docs.saleor.io/api-reference/users/queries/me`

---

## 3. 一次性配置（推荐）

在终端执行（macOS / zsh）：

```bash
export SALEOR_GRAPHQL_URL="https://<your-saleor-domain>/graphql/"
export SALEOR_TEST_EMAIL="your_test_user@example.com"
export SALEOR_TEST_PASSWORD="your_password"
export E2E_HTTP_TIMEOUT_S="20"
```

### 3.1 常见坑：引号没闭合（会导致套件初始化失败）

如果你看到终端出现 `dquote>`，说明你有一条命令的双引号没有闭合，后续命令会被拼进同一个字符串里。

错误示例（少了结尾的 `"`）：

```bash
export SALEOR_GRAPHQL_URL="http://localhost:8000/graphql/
```

正确示例（一定要成对闭合引号，且不要换行）：

```bash
export SALEOR_GRAPHQL_URL="http://localhost:8000/graphql/"
export SALEOR_TEST_EMAIL="zeen_long@outlook.com"
export SALEOR_TEST_PASSWORD="Zeen111!"
```

---

## 4. 运行命令（只跑 Auth 套件）

在 `z_cytest-main/` 目录下执行：

```bash
python3 -m cytest cases/end2end/10_auth --lang zh
```

期望结果：
- 能看到 5 条用例被收集
- `AUTH-0001` 至少通过（当 URL 正确且可匿名查询 shop）
- 如果提供账号密码：`AUTH-0002~0005` 也能通过

报告输出：
- Vue 报告：`z_cytest-main/log/vue_report_*.html`
- 文本日志：`z_cytest-main/log/testresult.log`

---

## 5. 常见问题（排障）

### 5.1 308 Redirect

现象：对 `SALEOR_GRAPHQL_URL` POST 返回 308，并提示跳转到 `/graphql`（无尾斜杠）。

建议：把 URL 直接写成目标 Location（按你环境实际返回为准），例如：

- `https://<domain>/graphql` 或 `https://<domain>/graphql/`

> 本项目的 `lib/saleor_api.py` 目前对 308 的自动重试还未做（后续可增强），建议你先把 URL 配对。

### 5.2 405 Method Not Allowed

现象：URL 看起来像 `/graphql`，但 POST 直接 405。

原因：你可能指向了 storefront 的路由，而不是 API 服务。

对策：改用真正的 Saleor API endpoint（通常是 Saleor Cloud 实例域名下的 `/graphql/`）。

### 5.3 tokenCreate 返回 errors

常见原因：
- 环境启用了 OIDC/SSO，不支持密码登录
- 账号没有设置密码

对策：
- 确认环境允许 `tokenCreate(email,password)`
- 或把 Auth 用例降级为“匿名查询 + tokenVerify（已有 token）”模式

