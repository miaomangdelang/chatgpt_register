# ChatGPT 批量自动注册工具

使用 Mailu 邮箱服务器自动批量注册 ChatGPT 账号，支持并发、OAuth 获取 Token、以及上传到 CPA 面板。

## 快速开始（3 步）

1. 安装依赖  
2. 配置 `config.json`  
3. 运行（交互或非交互）

## 1. 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

如果你只想安装主注册脚本的最小依赖，也可以手动执行：

```bash
python3 -m pip install curl_cffi
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
| output_file | 输出账号文件 |
| enable_oauth | 是否启用 OAuth 获取 Token |
| oauth_required | OAuth 失败是否算失败（true 会导致注册失败） |
| oauth_issuer / oauth_client_id / oauth_redirect_uri | OAuth 相关配置 |
| ak_file / rk_file | Access/Refresh Key 输出文件 |
| token_json_dir | OAuth Token JSON 输出目录 |
| upload_api_url / upload_api_token | CPA 面板上传配置（可选） |
| log_file | JSONL 日志文件 |

大多数配置可被环境变量覆盖（如 `MAILU_API_TOKEN`、`TOTAL_ACCOUNTS`、`ENABLE_OAUTH` 等）。

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

### 3.3 通过 WARP 容器运行

如果你希望只让容器内的对外 IP 走 Cloudflare WARP，而宿主机 IP 保持不变，可以使用仓库自带脚本创建独立容器。

首次创建并初始化 WARP 容器：

```bash
./scripts/setup_warp_container.sh
```

默认会创建：

- 容器名：`ubuntu22-warp`
- 镜像：`ubuntu:22.04`
- 挂载：`/home/miaomangdelang/workspace:/workspace`
- 能力：`NET_ADMIN`
- 设备：`/dev/net/tun`

常用 WARP 管理命令：

```bash
./scripts/warp_container.sh status
./scripts/warp_container.sh ensure
./scripts/warp_container.sh rotate
./scripts/warp_container.sh disconnect
```

说明：

- `status`：查看 WARP 状态，并同时输出宿主机与容器的 `cdn-cgi/trace`
- `ensure`：如果未注册或未连接，则自动补齐
- `rotate`：删除当前注册并重新注册，尝试切换容器出口 IP
- `disconnect`：断开容器内的 WARP 连接

在 WARP 容器内启动项目的示例：

```bash
docker exec ubuntu22-warp bash -lc 'cd /workspace/chatgpt_register && PYTHONUNBUFFERED=1 TOTAL_ACCOUNTS=1 MAX_WORKERS=1 ./scripts/batch_register.sh'
```

更多背景说明见 `WARP_CONTAINER_SETUP.md`。

## 4. CPA 面板上传（可选）

设置以下配置即可在注册成功后自动上传 Token：

```bash
export UPLOAD_API_URL="http://127.0.0.1:8317/v0/management/auth-files"
export UPLOAD_API_TOKEN="你的 CPA 面板密码"
```

## 5. 自动任务（定时）

`scripts/auto_register_25.sh` 会读取本地私密配置：
- `.secrets/mailu.env`  
  - `MAILU_API_TOKEN=...`
- `.secrets/telegram.env`（结果通知）
  - `TELEGRAM_BOT_TOKEN=...`
  - `TELEGRAM_CHAT_ID=...`

如需使用 `crontab`，建议调用批量脚本：

```bash
0 */6 * * * /usr/bin/bash -lc 'sleep $((RANDOM%1741+60)); cd /path/to/chatgpt_register && TOTAL_ACCOUNTS=5 MAX_WORKERS=1 ./scripts/batch_register.sh >> ./logs/cron.log 2>&1'
```

## 6. 输出与日志

- `registered_accounts.txt`：注册成功账号
- `ak.txt` / `rk.txt`：Access/Refresh Key
- `codex_tokens/*.json`：OAuth Token JSON
- `logs/register.log`：JSONL 详细日志
- `logs/cron.log`：定时任务输出
## 7. 常见问题

- OTP 等待时间过长：检查 Mailu 发信是否延迟、IMAP 是否可访问  
- OAuth OTP 失败：邮箱验证码可能过期或被多次发送覆盖  
- cron 执行无输出：确认使用 `batch_register.sh`（交互脚本会在 cron 中报 `EOFError`）  

## 目录结构

```
chatgpt_register/
├── chatgpt_register.py      # 主程序
├── config.json              # 配置文件
├── requirements.txt         # Python 依赖
├── README.md                # 本文档
├── WARP_CONTAINER_SETUP.md  # WARP 容器配置说明
├── scripts/
│   ├── batch_register.sh
│   ├── setup_warp_container.sh
│   └── warp_container.sh
├── codex/                   # Codex 协议密钥生成
│   ├── config.json
│   └── protocol_keygen.py
├── registered_accounts.txt  # 输出的账号
├── ak.txt                   # Access Keys
├── rk.txt                   # Refresh Keys
└── logs/                    # 日志目录
```
