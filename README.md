# GLaDOS/Railgun 自动签到 + 仓库保活

基于 GitHub Actions 的全自动签到工具。支持 GLaDOS 与 Railgun 双平台签到、积分自动兑换、PushDeer 推送通知，并内置**仓库保活机制**防止因 60 天不活跃导致定时任务被 GitHub 暂停。

## 功能特点

- 自动签到 [GLaDOS](https://glados.cloud) 和 [Railgun](https://railgun.info) 双平台
- 多账号支持（Cookie 之间用 `&` 分隔）
- 自动兑换积分（支持 plan100 / plan200 / plan500 三种策略）
- PushDeer 手机推送通知（可选）
- **仓库保活**：每月自动产生一次虚拟提交，确保仓库长期活跃
- 自动清理 7 天前的工作流运行记录
- **无需 Personal Access Token**，所有操作仅使用 GitHub 自动提供的 `GITHUB_TOKEN`

## 使用方法

### 1. 创建仓库

点击右上角 **Use this template** → **Create a new repository**，或直接 Fork 本仓库。

### 2. 获取 Cookie

1. 用浏览器登录 [GLaDOS](https://glados.space) 或 [Railgun](https://railgun.info)
2. 按 `F12` 打开开发者工具，切换到 **Network（网络）** 标签
3. 刷新页面，点击第一个请求
4. 在 **Request Headers** 中找到 `Cookie` 字段，复制完整值

> 参考格式：`koa:sess=eyJ1c2...; koa:sess.sig=xJkO...`

多账号时将多个 Cookie 用 `&` 连接即可（例如：`cookie1&cookie2&cookie3`）。

### 3. 添加 Secrets

进入仓库 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 名称 | 是否必填 | 说明 |
|------------|---------|------|
| `GLADOS_COOKIES` | **必填** | GLaDOS/Railgun 的 Cookie，多账号用 `&` 分隔 |
| `PUSHDEER_SENDKEY` | 可选 | [PushDeer](https://www.pushdeer.com) 推送密钥，用于手机接收签到结果 |
| `GLADOS_EXCHANGE_PLAN` | 可选 | 积分兑换计划，可选 `plan100` / `plan200` / `plan500`，默认 `plan500` |
| `GLADOS_VERBOSE` | 可选 | 详细日志输出，设为 `true` 开启，默认 `false` |

### 4. 启用 Actions

进入仓库 **Actions** 页面，点击 **I understand my workflows, go ahead and enable them** 启用工作流。

### 5. 验证运行

进入 Actions → **GLaDOS/Railgun 自动签到** → **Run workflow** 手动触发一次，查看日志确认签到是否正常。

## 定时运行

| 工作流 | 触发时间 | 说明 |
|--------|---------|------|
| 自动签到 | 每天 UTC 04:00 / 10:00（北京时间 12:00 / 18:00） | 执行签到 + 积分兑换 + 推送通知 |
| 仓库保活 | 每月 15 日 UTC 00:00 | 创建虚拟提交，保持仓库活跃 |

## 积分兑换策略

| 兑换计划 | 所需积分 | 兑换天数 |
|---------|---------|---------|
| `plan100` | 100 | 10 天 |
| `plan200` | 200 | 30 天 |
| `plan500` | 500 | 100 天（默认） |

不配置 `GLADOS_EXCHANGE_PLAN` 时默认使用 `plan500`。

## 仓库保活机制

GitHub 会在仓库 **连续 60 天没有新提交** 后自动暂停所有定时工作流。本项目的 `keepalive.yml` 每月 15 日自动向仓库推送一次保活提交（更新 `.keepalive` 时间戳文件），确保仓库始终保持活跃状态。

保活提交信息中包含 `[skip ci]` 标记，不会触发签到工作流，避免无效运行。

**无需任何额外配置或 Personal Access Token**，所有操作均使用 GitHub 自动提供的 `GITHUB_TOKEN`。

## 文件结构

```
├── .github/
│   └── workflows/
│       ├── checkin.yml          # 每日签到工作流
│       └── keepalive.yml        # 每月保活工作流
├── checkin.py                   # 签到脚本
├── logging_config.py            # 日志配置（北京时间）
├── .gitignore
├── LICENSE
└── README.md
```

## 问题排查

1. 进入仓库 **Actions** 页面
2. 点击最近的 `GLaDOS/Railgun 自动签到` 运行记录
3. 展开 **执行签到** 步骤查看详细日志
4. 常见问题：
   - **签到失败**：Cookie 可能已过期，重新获取并更新 `GLADOS_COOKIES`
   - **推送未收到**：检查 `PUSHDEER_SENDKEY` 是否正确配置
   - **兑换失败**：积分不足，可调整 `GLADOS_EXCHANGE_PLAN` 为更低档位

## 免责声明

本项目仅供学习交流使用。使用本工具产生的任何后果由使用者自行承担。请遵守相关服务的使用条款。

## 许可证

[GNU General Public License v3.0](LICENSE)
