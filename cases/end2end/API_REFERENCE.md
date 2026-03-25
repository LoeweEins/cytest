# 电商平台 API 接口文档整理（面向 cytest 系统测试）
```bash
cd /path/to/saleor-platform
docker compose up
```
> 目的：把电商常见 API 以“系统测试视角”重新分组，形成可直接用于 E2E 用例设计的接口清单与校验点。  
> 数据来源：参考中文电商开源项目的 Swagger/Knife4j 文档形态（见下方链接）。  
> 说明：由于不同开源项目的路由前缀/字段名不完全一致，本文档采用“通用接口契约 + 必测校验点”的方式整理；落地到具体项目时，以 Swagger/Knife4j 实际接口为准进行映射。

---

## 1. 开源项目与文档入口（可追溯，且不需要本地部署）

### 1.1 参考项目（开源电商 + 公开 Demo API）

- **Saleor（GraphQL 电商平台）**
  - 开源仓库：`https://github.com/saleor/saleor`
  - 公开 Demo API（GraphQL Endpoint）：`https://demo.saleor.io/graphql/`
  - Storefront（用于人工对照数据）：`https://demo.saleor.io/graphql/`
  - 官方文档：`https://docs.saleor.io/`

> 说明：本目录的 API 自动化以 `https://demo.saleor.io/graphql/` 为“远程被测系统”。你无需关注其后端部署，只需把 cytest 的请求指向该 Endpoint。

---

## 2. 通用鉴权与调用约定（GraphQL 版本）

### 2.1 GraphQL 调用方式（必须掌握）

- **请求方法**：`POST`
- **请求地址**：`https://demo.saleor.io/graphql/`
- **请求体**：JSON，典型字段：
  - `query`：GraphQL 查询/变更字符串
  - `variables`：变量对象（可选）
- **响应体**：JSON：
  - `data`：成功数据
  - `errors`：GraphQL 错误数组（即使 HTTP 200 也可能存在）

### 2.2 Header 约定（示例）

- `Content-Type: application/json`
- 鉴权（如需要）：
  - `Authorization: Bearer {token}`
  - 或使用 Saleor 的 App Token（取决于实例配置与文档）

### 2.3 全局必测响应约定（GraphQL 场景）

- **HTTP 状态码**：关注 200/4xx/5xx；但 GraphQL 常见“HTTP 200 + errors”
- **GraphQL errors**：如果 `errors` 非空，应视为失败或按预期分类（权限不足/参数校验等）
- **数据字段**：`data` 中关键字段非空、数量/分页/排序符合预期
- **限流/风控**：Demo 环境可能返回 429 或触发防护，需要在测试计划中加入重试与降频策略

---

## 3. 接口分组清单（映射 Saleor 常见 GraphQL 域）

以下按系统测试常用“链路视角”分组。每组给出：
- **典型接口**：你在 Swagger/Knife4j 里应该能找到的接口类型
- **关键校验点**：系统测试必须验证的业务规则
- **常见风险**：容易出事故的点（面试高频）

### 3.1 用户与鉴权（Account）

- **典型能力**
  - 获取当前用户、地址簿、订单列表（需要鉴权）
  - Demo 环境可能限制注册/登录能力；自动化建议优先做“匿名可访问”的浏览与搜索能力
- **关键校验点**
  - 未登录访问受保护字段应返回权限错误（GraphQL errors）

### 3.2 商品/类目/集合（Product / Category / Collection）

- **典型能力（GraphQL）**
  - 类目：查询类目列表/类目详情/子类目
  - 商品：查询商品列表（分页/排序/过滤）、商品详情、变体（variant）、价格区间
  - 集合：按 collection 聚合商品（适合做回归稳定用例）
- **关键校验点**
  - 上下架状态影响可见性与可购买性
  - 价格字段（原价/现价/会员价/活动价）计算一致
- **常见风险**
  - SKU 切换价格/库存展示错乱
  - 搜索/筛选分页的 off-by-one

### 3.3 购物车/结算（Checkout）

- **典型能力（GraphQL）**
  - 创建 checkout（匿名可用的概率较高）
  - 添加/更新 checkout lines（相当于加购/改数量）
  - 计算运费/税费/总价（用于价格一致性校验）
- **关键校验点**
  - 超库存加购限制
  - 登录前后购物车合并（如有）
- **常见风险**
  - 并发修改导致数量错乱
  - 购物车价格不随商品改价更新（规则需明确）

### 3.4 地址（Address）

- **典型接口**
  - 新增/编辑/删除：`POST /address/*`
  - 列表：`GET /address/list`
  - 设置默认：`POST /address/default`
- **关键校验点**
  - 默认地址唯一性
  - 省市区/邮编/手机号校验

### 3.5 订单（Order）

- **典型接口**
  - 确认订单：`POST /order/confirm`
  - 创建订单：`POST /order/create`
  - 订单详情：`GET /order/{id}`
  - 订单列表：`GET /order/list`
  - 取消订单：`POST /order/cancel`
- **关键校验点**
  - 价格三段一致：商品价 → 结算价 → 下单价
  - 状态机正确（待支付/已取消/已支付/已发货/已完成）
  - 重复提交下单的幂等（可用“下单 token/幂等键”）
- **常见风险**
  - 订单重复创建
  - 并发下单超卖（扣减库存策略）

### 3.6 支付（Payment）

- **说明（Demo 环境取舍）**
  - Demo 环境通常不会开放真实支付渠道；API 自动化建议把重点放在：
    - checkout 金额计算一致性
    - “提交订单/完成 checkout”这一步若受限，则降级为只验证 checkout 侧的业务规则

### 3.7 履约与物流（Delivery / Logistics）

- **典型接口**
  - 发货（管理端）：`POST /admin/order/ship`
  - 物流查询：`GET /logistics/track`
  - 确认收货：`POST /order/confirmReceive`
- **关键校验点**
  - 发货后用户可见物流单号
  - 收货后状态变更、进入可售后窗口（规则需明确）

### 3.8 售后（AfterSale / Refund / Return）

- **典型接口**
  - 申请仅退款：`POST /aftersale/refund/apply`
  - 申请退货退款：`POST /aftersale/return/apply`
  - 售后详情：`GET /aftersale/{id}`
  - 审核（管理端）：`POST /admin/aftersale/audit`
  - 退款结果：`GET /aftersale/refund/status`
- **关键校验点**
  - 售后时效、状态机（申请中/待寄回/已退款/拒绝）
  - 库存与财务的一致性（按业务规则）

### 3.9 优惠券与营销（Coupon / Promotion）

- **典型接口**
  - 券列表/领取：`GET /coupon/list`，`POST /coupon/receive`
  - 下单使用券：在 `order/confirm` 或 `order/create` 中体现
  - 活动信息：`GET /promotion/*`
- **关键校验点**
  - 门槛券、范围券（类目/品牌/商品）校验
  - 不可叠加规则

### 3.10 库存（Inventory）— 横切校验点

- **典型接口**
  - 查询库存：`GET /stock/{skuId}`
  - 预扣/扣减/释放：可能内置在下单/取消/退款流程，也可能是独立接口
- **关键校验点**
  - 下单扣减、取消释放、退款回补的幂等与一致性

---

## 4. 面向远程 Demo 的“最小接口集”（冒烟集）

用于每天 CI 跑一次，5~10 分钟内给出可信结论：

- 查询类目/集合（确认服务可用）
- 查询商品列表（分页/排序/过滤）
- 查询商品详情（带变体/价格）
- （可选）创建 checkout + 添加 line（验证价格计算与库存约束）

---

## 5. 如何把本文档映射到 cytest 用例（建议）

- 每个业务域在 `cases/end2end/{domain}/` 下建立套件目录
- 用例类只需实现 `teststeps()`，并用 `STEP` + `CHECK_POINT` 写清业务动作与断言
- 用 `GSTORE` 保存跨步骤/跨用例共享的关键 ID（`channel`、`categoryId`、`productId`、`variantId`、`checkoutId`）
- 高风险链路建议加上标签：`高风险`、`支付`、`库存`、`幂等`

