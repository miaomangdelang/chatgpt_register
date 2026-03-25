# ChatGPT 批量自动注册工具

使用 Mailu 邮箱服务器自动批量注册 ChatGPT 账号，支持并发、代理、OAuth 获取 Token、以及上传到 CPA 面板。

## 快速开始（3 步）

1. 安装依赖  
2. 配置 `config.json`  
3. 运行（交互或非交互）

## 1. 安装依赖

```bash
pip install curl_cffi
```

## 2. 配置（config.json）

示例：

```json
{
  "total_accounts": 5,
  "mailu_base_url": "https://mail.example.com",
  "mailu_api_token": "你的 Mailu API Token",
  "mail_domain": "example.com",
  "mailbox_quota_bytes": 1073741824,
  "imap_host": "mail.example.com",
  "imap_port": 993,
  "imap_ssl": true,
  "imap_folder": "INBOX",
  "imap_timeout": 20,
  "proxy": "http://127.0.0.1:7890",
  "output_file": "registered_accounts.txt",
  "enable_oauth": true,
  "oauth_required": true,
  "oauth_issuer": "https://auth.openai.com",
  "oauth_client_id": "app_xxx",
  "oauth_redirect_uri": "http://localhost:1455/auth/callback",
  "ak_file": "ak.txt",
  "rk_file": "rk.txt",
  "token_json_dir": "codex_tokens",
  "upload_api_url": "http://127.0.0.1:8317/v0/management/auth-files",
  "upload_api_token": "你的 CPA 面板密码",
  "log_file": "logs/register.log"
}
```

常用字段说明：

| 字段 | 说明 |
|---|---|
| total_accounts | 注册账号数量 |
| mailu_base_url | Mailu API 地址 |
| mailu_api_token | Mailu API Token |
| mail_domain | 邮箱域名 |
| mailbox_quota_bytes | 邮箱容量（字节） |
| imap_host | IMAP 主机 |
| imap_port | IMAP 端口 |
| imap_ssl | 是否启用 IMAP SSL |
| imap_folder | IMAP 文件夹（默认 INBOX） |
| imap_timeout | IMAP 超时（秒） |
| proxy | 代理地址（可选） |
| output_file | 输出账号文件 |
| enable_oauth | 是否启用 OAuth 获取 Token |
| oauth_required | OAuth 失败是否算失败（true 会导致注册失败） |
| oauth_issuer / oauth_client_id / oauth_redirect_uri | OAuth 相关配置 |
| ak_file / rk_file | Access/Refresh Key 输出文件 |
| token_json_dir | OAuth Token JSON 输出目录 |
| upload_api_url / upload_api_token | CPA 面板上传配置（可选） |
| log_file | JSONL 日志文件 |

大多数配置可被环境变量覆盖（如 `MAILU_API_TOKEN`、`PROXY`、`TOTAL_ACCOUNTS`、`ENABLE_OAUTH` 等）。

## 3. 运行方式

### 3.1 交互运行（手动输入数量/并发）

```bash
python3 chatgpt_register.py
```

程序会提示输入：
1. 注册账号数量  
2. 并发数  

### 3.2 非交互批量（推荐用于 cron）

```bash
export MAILU_API_TOKEN="你的 Mailu API Token"
TOTAL_ACCOUNTS=5 MAX_WORKERS=1 ./scripts/batch_register.sh
```

说明：
- `scripts/batch_register.sh` 会优先读取环境变量中的 `MAILU_API_TOKEN`  
- 如果未设置，会自动从 `config.json` 读取 `mailu_api_token`

## 4. 代理策略（非常重要）

默认固定代理（代码内置）：
```
http://192.168.1.137:7890
```

代理选择优先级：
1. 固定代理（`USE_FIXED_PROXY=1` 且 `FIXED_PROXY` 非空）
2. 环境变量 `PROXY` / `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`
3. `config.json` 的 `proxy`

如需使用环境代理或 `config.json` 的代理：

```bash
export USE_FIXED_PROXY=0
```

可选：为 OpenAI 单独指定代理
```bash
export OPENAI_PROXY="http://127.0.0.1:7890"
export OPENAI_PROXY_MODE=inherit   # inherit / force
```

## 5. CPA 面板上传（可选）

设置以下配置即可在注册成功后自动上传 Token：

```bash
export UPLOAD_API_URL="http://127.0.0.1:8317/v0/management/auth-files"
export UPLOAD_API_TOKEN="你的 CPA 面板密码"
```

说明：
- 若 `UPLOAD_API_URL` 指向 `localhost/127.0.0.1`，上传默认直连（不走代理）
- 如需强制上传走代理，可设置 `UPLOAD_PROXY`

## 6. 与 proxy-rotator 串联（建议）

方式 A（直接调用 proxy-rotator）：
```bash
export USE_FIXED_PROXY=0
TOTAL_ACCOUNTS=10 MAX_WORKERS=3 \
  ../proxy-rotator/run_with_selected_proxy.sh --config ../proxy-rotator/config.yaml --refresh -- \
  ./scripts/batch_register.sh
```

方式 B（封装脚本）：
```bash
./scripts/run_with_proxy_rotator.sh --config ../proxy-rotator/config.yaml --total 10 --workers 3
```

封装脚本支持：
- `CLI_PROXY_API_URL` / `CLI_PROXY_API_KEY` 自动映射到上传配置  
- 自动记录日志 `logs/run_YYYYmmdd_HHMMSS.log`
- 失败后自动重试（可配置重试次数）

## 7. 自动任务（定时）

`scripts/auto_register_25.sh` 会读取本地私密配置：
- `.secrets/mailu.env`  
  - `MAILU_API_TOKEN=...`
- `.secrets/telegram.env`（结果通知）
  - `TELEGRAM_BOT_TOKEN=...`
  - `TELEGRAM_CHAT_ID=...`
  - `TELEGRAM_PROXY_URL=...`（可选）

如需使用 `crontab`，建议调用批量脚本：

```bash
0 */6 * * * /usr/bin/bash -lc 'sleep $((RANDOM%1741+60)); cd /path/to/chatgpt_register && TOTAL_ACCOUNTS=5 MAX_WORKERS=1 ./scripts/batch_register.sh >> ./logs/cron.log 2>&1'
```

## 8. 输出与日志

- `registered_accounts.txt`：注册成功账号
- `ak.txt` / `rk.txt`：Access/Refresh Key
- `codex_tokens/*.json`：OAuth Token JSON
- `logs/register.log`：JSONL 详细日志
- `logs/cron.log`：定时任务输出
- `logs/run_*.log`：proxy-rotator 封装脚本日志

## 9. 常见问题

- OTP 等待时间过长：检查 Mailu 发信是否延迟、IMAP 是否可访问  
- OAuth OTP 失败：邮箱验证码可能过期或被多次发送覆盖  
- cron 执行无输出：确认使用 `batch_register.sh`（交互脚本会在 cron 中报 `EOFError`）  

## 目录结构

```
chatgpt_register/
├── chatgpt_register.py      # 主程序
├── config.json              # 配置文件
├── README.md                # 本文档
├── scripts/
│   ├── batch_register.sh
│   └── run_with_proxy_rotator.sh
├── codex/                   # Codex 协议密钥生成
│   ├── config.json
│   └── protocol_keygen.py
├── registered_accounts.txt  # 输出的账号
├── ak.txt                   # Access Keys
├── rk.txt                   # Refresh Keys
└── logs/                    # 日志目录
```
