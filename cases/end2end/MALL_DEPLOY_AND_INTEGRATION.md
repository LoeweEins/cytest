# 远程开源电商 Demo API 接入指南（E2E）
```bash
cd /path/to/saleor-platform
docker compose up
```
> 本文解决两个问题：  
> 1) 选择一个**不需要本地部署**、可直接用于 API 自动化的开源电商 Demo  
> 2) cytest 端到端用例如何接入该远程服务（Base URL、鉴权、冒烟验证）

---

## 1. 选型：为什么不本地部署，直接用远程 Demo？

当你的目标是“写 API 自动化作品/面试展示”，最省成本的方式是选择：

- **开源**（可追溯、可解释架构）
- **公开可访问 Demo API**（无需部署）
- **接口稳定**（至少支持只读查询与分页/过滤）

本目录统一采用 **Saleor Demo GraphQL API** 作为远程被测系统。

---

## 2. 远程被测系统（推荐：Saleor Demo）

### 2.1 开源与 Demo 地址

- 开源仓库：`https://github.com/saleor/saleor`
- 远程 GraphQL API Endpoint：`https://demo.saleor.io/graphql/`
- Storefront（用于人工对照数据）：`https://demo.saleor.io/graphql/`
- 官方文档：`https://docs.saleor.io/`

### 2.2 这类远程 Demo 的“系统测试约束”

- **数据不可控**：商品、价格、库存可能随时变化或重置
- **写入受限**：创建订单/支付等 mutation 可能需要账号或被限制
- **限流/风控**：频繁请求可能触发 429 或验证码（若有）

因此：API 自动化的主战场应优先选择 **只读查询 + 分页/过滤/排序**；写入链路做可选专项。

---

## 3. cytest 如何接入远程 Saleor Demo（你真正要的部分）

cytest 的接入核心是三件事：

1) **GraphQL Endpoint**：`https://demo.saleor.io/graphql/`  
2) **鉴权（可选）**：匿名查询通常可用；需要 mutation 时再考虑登录/令牌  
3) **测试数据**：从 API 实时查询得到 `categoryId/productId/variantId`（避免写死）

### 3.1 建议的 cytest 套件初始化位置

在 `cases/end2end/__st__.py` 做全局准备（你后续写自动化用例时推荐按这个结构落地）：

- `suite_setup()`
  - 写入 `GSTORE.graphql_url = "https://demo.saleor.io/graphql/"`
  - 预查询一个 channel / collection / category（写入 GSTORE，供后续用例复用）
- `suite_teardown()`
  - 一般不需要（Demo 环境尽量少写入）

### 3.2 配置项建议（不绑定具体实现）

建议你用环境变量管理（便于在 CI/面试机器上直接跑）：

- `SALEOR_GRAPHQL_URL`：默认 `https://demo.saleor.io/graphql/`
- （可选）`SALEOR_TOKEN`：如果你拿到了可用 token（通常 Demo 不公开）

### 3.3 最小冒烟接入验证（推荐先做 API 冒烟）

目标：确认 “服务可达 + 登录可用 + token 可用 + 取到商品/订单能力”。

建议按以下 3 步设计冒烟（远程 Demo 友好）：

- **Step 1：查询 channel / collections / categories**（确认服务可用）
- **Step 2：查询商品列表（分页）**（确认分页与排序字段可用）
- **Step 3：查询商品详情（含 variants/priceRange）**（确认关键字段稳定存在）

### 3.4 UI 接入建议（可选）

如果你要做 UI E2E（例如前台浏览/搜索/加购 UI 验证）：

- UI Base URL：`https://demo.saleor.io/graphql/`（Storefront）
- Selenium driver 在 `suite_setup` 初始化，并在失败检查点调用 `SELENIUM_LOG_SCREEN(driver)`，Vue 报告会展示步骤与截图（你的 cytest 已支持）。

---

## 4. 接入时的现实取舍（面试可讲）

- **为什么选择远程 Demo？**
  - 面试/作品集场景下，远程 Demo 能“零部署成本”快速展示你的自动化能力；缺点是数据不可控、写入受限，所以测试计划要把重心放在只读查询与稳定断言上。
- **先 API 后 UI**
  - 系统测试要保证稳定性与效率：核心交易链路优先用 API 跑通，UI 只覆盖关键路径与集成验证。

