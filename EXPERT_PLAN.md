# chatgpt_register 重构与借鉴专家方案

## 1. 结论

当前建议不是把 `codexRegister` 直接迁移到 `chatgpt_register`，而是把 `chatgpt_register` 升级成一个“多后端注册框架”。

核心判断如下：

- `chatgpt_register` 已经掌握主链路，尤其是协议注册和 Codex OAuth，这部分价值最高。
- `codexRegister` 的核心价值不在业务逻辑本身，而在“远程浏览器执行 backend”与“分阶段编排”的思路。
- 因此最优路线不是整体合并，而是让 `codexRegister` 贡献能力模型，由 `chatgpt_register` 继续做主系统。

## 2. 现状判断

### 2.1 chatgpt_register 已有能力

当前 Python 项目已经覆盖了完整主流程：

- Mailu 建邮箱
- IMAP 拉取验证码
- ChatGPT 注册
- OTP 校验
- 账号资料创建
- 回调处理
- Codex OAuth 协议登录
- OAuth 阶段邮箱 OTP
- workspace / organization 选择
- `/oauth/token` 交换
- Token 保存与上传

这意味着当前项目已经拥有完整的“协议主路径”。

### 2.2 codexRegister 的核心价值

`codexRegister` 更像一个“远程浏览器自动执行器”，主要特点是：

- 使用 Browserbase/Gemini 远程浏览器会话
- 用 Agent goal 驱动网页交互
- 通过 CDP 和 URL 变化判断阶段完成
- 将注册阶段和 OAuth 阶段拆开

因此它更适合作为“浏览器 fallback backend”的参考，而不是主系统模板。

## 3. 总体设计原则

### 3.1 保留 Python 为唯一主控

建议由 Python 负责：

- 任务编排
- 状态管理
- 配置读取
- 日志写入
- Token 持久化
- 通知
- 失败重试

不建议形成 Python + Node 双主控结构，否则后续一定会出现：

- 状态不一致
- 日志口径不统一
- 输出目录不统一
- 排障链路割裂

### 3.2 浏览器能力作为可选后端

建议把浏览器执行能力定义成可选 backend，而不是新的主流程。

默认执行路径：

- `HTTP 注册 + HTTP OAuth`

兜底执行路径：

- `Remote Browser 注册`
- `Remote Browser OAuth`

### 3.3 单一状态源

无论未来接入多少执行后端，都必须保证：

- 任务状态只由 orchestrator 决定
- 文件输出只由主控统一写入
- 后端只返回结构化结果，不直接写核心产物

## 4. 目标架构

建议将项目拆成以下 6 层。

### 4.1 orchestrator

职责：

- 任务生命周期管理
- 阶段切换
- backend 选择
- fallback 决策
- 重试控制

### 4.2 email_provider

职责：

- 创建邮箱
- 获取邮箱登录凭据
- 轮询验证码

初期保留：

- `MailuProvider`

后续可扩展：

- `DDGProvider`

### 4.3 register_backend

职责：

- 执行 ChatGPT 注册阶段

建议拆成：

- `HttpRegisterBackend`
- `RemoteBrowserRegisterBackend`

### 4.4 oauth_backend

职责：

- 执行 Codex OAuth 阶段

建议拆成：

- `HttpOAuthBackend`
- `RemoteBrowserOAuthBackend`

### 4.5 risk_engine

职责：

- 识别风控
- 判断是否重试
- 判断是否切换 backend
- 判断是否应该停当天任务

### 4.6 artifact_store

职责：

- 保存账号结果
- 保存 token
- 保存失败证据
- 保存阶段快照
- 统一落盘日志

## 5. 推荐目录结构

建议把当前大单文件逐步拆成下面这种结构：

```text
chatgpt_register/
├── app.py
├── config/
│   ├── settings.py
│   └── schema.py
├── core/
│   ├── orchestrator.py
│   ├── models.py
│   ├── state_machine.py
│   └── risk_engine.py
├── providers/
│   ├── mailu_provider.py
│   ├── imap_client.py
│   └── ddg_provider.py
├── backends/
│   ├── http_register_backend.py
│   ├── http_oauth_backend.py
│   ├── remote_browser_backend.py
│   └── browserbase_client.py
├── services/
│   ├── token_store.py
│   ├── uploader.py
│   ├── notifier.py
│   └── proxy_policy.py
├── logs/
├── scripts/
└── tests/
```

说明：

- 这是目标结构，不要求一次性改完。
- 第一阶段可以先拆最核心的 provider、backend、service。

## 6. 建议的执行策略

### 6.1 主路径

默认使用：

- `HTTP 注册`
- `HTTP OAuth`

因为这是当前已经被实现且掌握程度最高的链路。

### 6.2 fallback 触发条件

建议只有在满足以下条件之一时才切到浏览器 backend：

- 协议阶段连续出现 `401 / 403 / 429`
- 出现 `invalid_auth_step`
- `login_session` 无法稳定建立
- sentinel token 获取异常
- 同代理下连续多次 OTP 阶段失败
- 当日风险计数持续升高，但仍允许少量兜底尝试

### 6.3 backend 切换规则

建议明确约束：

- 注册阶段 fallback 独立于 OAuth 阶段 fallback
- 不要一次失败就切浏览器
- 每个账号最多进行一次 backend 切换
- 每次阶段执行都记录 `backend=http|browser`

## 7. 从 codexRegister 值得借鉴的内容

### 7.1 应该借鉴

- 分阶段编排思路
- 浏览器会话抽象方式
- CDP / URL 变化监控机制
- 浏览器任务与 token 交换分离
- 随机身份生成模块化

### 7.2 不建议直接照搬

- Node 主控入口
- DDG 邮箱链路直接替换 Mailu
- 用浏览器流程覆盖当前协议 OAuth 主路径
- 把 prompt 驱动逻辑直接塞进主程序核心流程

## 8. 分期实施方案

### 第一期：无行为变更重构

目标：

- 不改变现有功能
- 只拆结构，不改核心行为

任务：

- 拆出配置模块
- 拆出 Mailu provider
- 拆出 IMAP client
- 拆出 HTTP register backend
- 拆出 HTTP OAuth backend
- 拆出 notifier / uploader / token store
- 保持当前入口可运行

输出标准：

- 原脚本功能不退化
- 配置与日志行为保持一致

### 第二期：引入浏览器注册 fallback

目标：

- 先只接注册阶段 fallback

任务：

- 定义 `RemoteBrowserRegisterBackend`
- 包装 Browserbase/Gemini 能力
- 增加 URL 完成态判断
- 让 orchestrator 能在注册阶段切 backend

输出标准：

- 浏览器 backend 只返回结构化注册结果
- 不直接写 token 文件

### 第三期：引入浏览器 OAuth fallback

目标：

- 协议 OAuth 失败时有备用路径

任务：

- 定义 `RemoteBrowserOAuthBackend`
- 浏览器完成 OAuth 页面交互
- 回调 URL 由主控统一解析
- Token 持久化仍由主控写入

输出标准：

- OAuth fallback 仅在主路径失败后触发
- 不改变主路径默认行为

### 第四期：补充运维与证据能力

目标：

- 提升排障和复盘能力

任务：

- 每次运行生成 run id
- 记录最后 step、最后 URL、backend 类型
- 保存失败快照
- 增加代理质量评分
- 支持失败重放

### 第五期：补工程质量

目标：

- 让项目进入可维护状态

任务：

- 配置脱敏
- 测试夹具
- 回归测试
- 健康检查脚本
- 文档补全

## 9. 关键工程原则

整个改造过程中，必须坚持以下原则：

- 单一主控语言：Python
- 单一状态源：orchestrator
- 单一输出口：账号、token、日志统一由主控写
- backend 可替换，但业务状态不可分叉
- 浏览器 backend 是兜底，不是主路径

## 10. 当前风险点

### 10.1 明文敏感配置

当前配置中已有明文敏感信息，后续重构前建议优先处理：

- Mailu API Token
- Telegram Bot Token
- 上传接口 Token

建议改为：

- 环境变量
- `.secrets/*.env`
- 本地私密配置文件，不入库

### 10.2 双主控风险

如果未来让 Python 和 Node 同时主控流程，会造成：

- 状态不一致
- 失败难以归因
- 产物写入冲突

### 10.3 未先拆状态机就接浏览器 backend

如果现在直接把 Browserbase 接进现有单文件逻辑，会导致：

- 流程判断更混乱
- 重试逻辑更难维护
- 排障成本进一步上升

## 11. 推荐最终路线

最终建议路线如下：

1. `chatgpt_register` 继续作为主系统。
2. `codexRegister` 只提供“浏览器执行能力”和“分阶段设计思路”。
3. 不做整体迁移，不做整体合并。
4. 先重构，再接 fallback。
5. 默认保留协议主路径，浏览器只做兜底。

## 12. 一句话总结

最优解不是“借鉴代码”，而是“借鉴能力模型”：

- 用 `chatgpt_register` 继续做主系统
- 用 `codexRegister` 提供浏览器 fallback 思路
- 先把现有大单文件重构成可扩展框架
- 再逐步接入远程浏览器能力
