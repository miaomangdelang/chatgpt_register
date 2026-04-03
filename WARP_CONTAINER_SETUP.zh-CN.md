# WARP 容器配置说明

## 目标

提供一个 Docker 容器，让容器内的出站流量可以走 Cloudflare WARP，同时不改变宿主机的对外 IP，并保持项目工作目录继续挂载在容器内。

## 初始排查结果

- 原来的 `ubuntu22` 容器将 `/home/miaomangdelang/workspace` 挂载到了 `/workspace`。
- 该容器运行在普通的 Docker `bridge` 网络模式下。
- 创建该容器时没有附加 `NET_ADMIN`。
- 创建该容器时没有挂载 `/dev/net/tun`。

这两个条件都缺失，意味着 Cloudflare WARP 不能在现有容器里直接启用，必须通过重新创建容器来解决。

## 为什么新建了一个容器

目标要求是只改变容器的出口 IP，而不能影响宿主机。

如果把 WARP 直接跑在宿主机上，就会改动宿主机网络路径，这和目标冲突。由于原来的容器既没有所需网络能力，也没有 TUN 设备，因此改为创建一个新的容器：

- 容器名：`ubuntu22-warp`
- 镜像：`ubuntu:22.04`
- 挂载：`/home/miaomangdelang/workspace:/workspace`
- 额外能力：`NET_ADMIN`
- 设备透传：`/dev/net/tun`

这样可以把宿主机网络和容器网络隔离开，同时允许 WARP 只接管该容器自己的出站流量。

## 在 WARP 容器中安装的包

首先安装了基础系统包：

- `ca-certificates`
- `curl`
- `gnupg`
- `iproute2`
- `procps`
- `lsb-release`
- `python3-pip`

随后添加了 Cloudflare 官方 apt 源，并安装了 `cloudflare-warp`。

由于这个容器镜像里没有使用 `systemctl`，所以 WARP 守护进程是通过 `warp-svc` 手动启动的。

## 仓库中新增的文件

- `requirements.txt`
  - 声明当前项目入口脚本所需的 Python 依赖。
- `scripts/setup_warp_container.sh`
  - 创建支持 WARP 的 Docker 容器，并执行首次初始化。
- `scripts/warp_container.sh`
  - 用于检查 WARP 状态和容器出口状态的辅助脚本。
- `WARP_CONTAINER_SETUP.md`
  - 英文版说明文档。
- `WARP_CONTAINER_SETUP.zh-CN.md`
  - 中文版说明文档。

## 已执行的验证

### WARP 连通性验证

`ubuntu22-warp` 容器已经成功完成 WARP 注册并建立连接。

验证时使用了：

- `warp-cli status`
- `https://www.cloudflare.com/cdn-cgi/trace`

观察到的结果：

- 宿主机保持 `warp=off`
- WARP 容器显示 `warp=on`

这说明宿主机的出站路径没有被修改，而容器已经通过 WARP 出口访问外网。

### 容器与宿主机出口隔离验证

分别对宿主机和容器执行了 Cloudflare trace 检查。

宿主机仍然使用自己的公网 IP，而 WARP 容器使用的是不同的 IP，并且状态显示为 `warp=on`。

这说明网络变更被限制在容器内部，没有外溢到宿主机。

### WARP 容器内的项目运行验证

在 `ubuntu22-warp` 内部做了以下操作：

1. 安装 `python3-pip`
2. 使用 `pip` 安装 `requirements.txt`
3. 从 `/workspace/chatgpt_register` 目录执行项目

随后进行了一个最小化的单账号验证运行，用来确认：

- workspace 挂载可用
- Python 依赖已满足
- 出站请求确实经过 WARP 容器
- 应用可以从容器内部访问 Mailu 和 OpenAI 端点

## 当前运行限制

当前容器环境已经可用，但注册流程仍然被远端服务阻断，失败点在：

- `POST https://auth.openai.com/api/accounts/user/register`

验证运行中观察到的响应为：

- HTTP `400`
- 消息：`Failed to create account. Please try again.`

这说明当前瓶颈已经不是容器配置问题，不是 Python 依赖问题，也不是 WARP 连通性问题。剩余问题在于远端注册接口本身，或者该接口当前要求的请求参数与流程。

## 关于仓库现有状态的说明

在本次 WARP 相关工作开始之前，这个仓库中已经存在一些无关的未提交改动。为了避免混入无关内容，WARP 相关提交最初只包含本次新增的文件，没有把那些原有改动一起纳入。
