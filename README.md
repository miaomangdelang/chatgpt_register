# ChatGPT 批量自动注册工具

> 使用 Mailu 邮箱服务器，并发自动注册 ChatGPT 账号

## 功能

- 📨 自动创建邮箱账号 (Mailu API)
- 📥 通过 IMAP 自动获取 OTP 验证码
- ⚡ 支持并发注册多个账号
- 🔄 自动处理 OAuth 登录
- ☁️ 支持代理配置
- 📤 支持上传账号到 Codex / CPA 面板

## 环境

```bash
pip install curl_cffi
```

## 配置 (config.json)

```json
{
  "total_accounts": 5,
  "mailu_base_url": "https://mail.oracle.311200.xyz",
  "mailu_api_token": "你的 Mailu API Token",
  "mail_domain": "oracle.311200.xyz",
  "mailbox_quota_bytes": 1073741824,
  "imap_host": "mail.oracle.311200.xyz",
  "imap_port": 993,
  "imap_ssl": true,
  "imap_folder": "INBOX",
  "imap_timeout": 20,
  "proxy": "http://127.0.0.1:7890",
  "output_file": "registered_accounts.txt",
  "enable_oauth": true,
  "oauth_redirect_uri": "http://localhost:1455/auth/callback",
  "ak_file": "ak.txt",
  "rk_file": "rk.txt"
}
```

| 配置项 | 说明 |
|--------|------|
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
| proxy | 代理地址 (可选) |
| output_file | 输出账号文件 |
| enable_oauth | 启用 OAuth 登录 |
| ak_file | Access Key 文件 |
| rk_file | Refresh Key 文件 |

## CPA 面板集成

注册完成后，可以自动上传账号到 CPA 面板：

| 配置项 | 说明 | 参考 |
|--------|------|------|
| upload_api_url | CPA 面板上传 API 地址 | https://help.router-for.me/cn/ |
| upload_api_token | CPA 面板登录密码 | 你的 CPA 面板密码 |

> CPA 面板仓库: https://github.com/dongshuyan/CPA-Dashboard

## 使用

```bash
python chatgpt_register.py
```

程序会直接使用代码内硬编码代理：`http://192.168.1.101:7890`，不再读取 `config.json` 或环境变量，也不再交互询问。

## 批量脚本（非交互）

```bash
export MAILU_API_TOKEN="你的 Mailu API Token"
TOTAL_ACCOUNTS=10 MAX_WORKERS=3 ./scripts/batch_register.sh
```

## 自动任务（定时）

`scripts/auto_register_25.sh` 会读取本地私密配置：

- `.secrets/mailu.env`  
  - `MAILU_API_TOKEN=...`
- `.secrets/telegram.env`（用于结果通知）
  - `TELEGRAM_BOT_TOKEN=...`
  - `TELEGRAM_CHAT_ID=...`
  - `TELEGRAM_PROXY_URL=...`（可选）

脚本内置运行锁，避免多次定时任务重叠执行。

`scripts/cpa_upload_daily.sh` 用于每天 06:00 上传过去 24 小时创建的账号到 CPA（从 codex_tokens），注册后不再即时上传。


## 输出

注册成功的账号会保存到 `registered_accounts.txt`

## 目录结构

```
chatgpt_register/
├── chatgpt_register.py    # 主程序
├── config.json             # 配置文件
├── README.md               # 本文档
├── codex/                  # Codex 协议密钥生成
│   ├── config.json
│   └── protocol_keygen.py
├── registered_accounts.txt # 输出的账号
├── ak.txt                  # Access Keys
└── rk.txt                 # Refresh Keys
```

## 注意事项

- 需要有效的代理才能注册成功
- Mailu API Token 需在你的 Mailu 管理端创建
- 确保 IMAP(993) 可访问
- 建议使用代理避免 IP 被封
- 使用 CPA 面板需要先部署面板服务
