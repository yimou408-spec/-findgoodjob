# 前后端启动与联调运行手册

这份文档用于沉淀 `Findgoodjob` 项目的前后端启动经验、常见阻碍和排查方法。

以后每次需要拉起前后端并做联调时，先阅读这份文档，再执行启动操作。
如果后续又遇到新的报错、阻碍点或更稳的启动方式，应继续追加到本文档中，而不是把经验留在临时聊天记录里。

## 当前结论

本项目在当前 Windows 环境下，前后端是否真的启动成功，不能只看终端日志里是否出现了 `ready`、`started`、`running` 之类的字样。

真正有效的判断标准必须同时满足：

1. 目标端口已经监听
2. 对应 HTTP 探活请求能成功返回

推荐探活目标：

- 前端：`http://127.0.0.1:5173/`
- 后端健康检查：`http://127.0.0.1:8000/health`

## 已验证的经验教训

### 1. 不要只相信“启动成功”的日志

这次联调里，前后端都出现过“日志显示启动成功，但进程很快退出”的情况。

典型表现：

- Vite 日志里出现 `ready in xxx ms`
- Uvicorn 日志里出现 `Application startup complete`
- 但实际端口没有监听
- `Invoke-WebRequest` 无法连接

因此每次启动后都要立刻补两步：

- 用 `netstat -ano | Select-String ':5173|:8000'` 检查端口
- 用 HTTP 请求检查服务是否真的响应

### 2. 前端 Vite 在 Windows 下更稳的启动方式是直接用 Node 调 Vite 入口

在当前环境里，`npm run dev` 有时会出现以下问题：

- 日志写了启动成功
- 但 dev server 实际没有常驻
- 或者 `npm.cmd` / 包装壳退出后，前端也跟着退出

更稳的启动方式是直接调用：

```powershell
node node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173
```

优先使用这个方式启动前端。

### 3. 后端 Python 启动尽量用明确解释器，不要依赖模糊命令解析

`python` 命令在当前机器上可能指向多个位置：

- `D:\anaconda\python.exe`
- `C:\Users\...\WindowsApps\python.exe`

如果只写 `python`，可能会受到 PATH、壳环境或代理解析影响。

更稳妥的做法是：

- 先用 `where.exe python` 找出真实解释器
- 启动时优先用明确路径

当前环境中已确认可用的解释器路径：

```text
D:\anaconda\python.exe
```

### 4. 前后端启动后都要做探活，不能跳过

推荐的最小探活命令：

```powershell
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173'
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health'
```

成功标准：

- 前端返回 `200`
- 后端返回 `{"status":"ok"}`

### 5. 端口冲突要先确认，不要盲目重试

此前出现过：

- `5173` 被占用，Vite 自动切到 `5174`
- 用户还在访问旧端口，误以为前端没启动

所以如果访问失败，先检查：

```powershell
netstat -ano | Select-String ':5173|:5174|:8000'
```

如果端口被占用：

- 明确当前服务实际跑在哪个端口
- 或先停掉旧进程，再固定回目标端口启动

## 推荐启动顺序

### 启动后端

在项目根目录运行：

```powershell
D:\anaconda\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 启动前端

在 `frontend` 目录运行：

```powershell
node node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173
```

### 启动后立即验证

```powershell
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health'
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173'
```

## 联调前检查清单

每次做功能联调前，至少确认以下几点：

- 后端 `8000` 端口在监听
- 前端 `5173` 端口在监听
- 后端 `/health` 返回正常
- 前端首页可访问
- 当前模型配置已就绪，例如 `DEEPSEEK_API_KEY`

如果联调涉及求职助手页，还要额外确认：

- 数据库迁移已经应用
- 当前岗位存在
- 岗位分析或简历修订链路至少能跑通一条

## 已记录的阻碍点

### 阻碍点 1

- 现象：Vite 日志显示 `ready`，但前端页面打不开
- 原因：dev server 进程没有真正常驻，日志成功不等于端口监听
- 解决：改为直接使用 `node node_modules\vite\bin\vite.js` 启动，并用 HTTP 探活确认

### 阻碍点 2

- 现象：后端日志显示 `Application startup complete`，但 `/health` 无法访问
- 原因：启动日志存在，但 Python 进程没有稳定驻留
- 解决：不要只看日志，要结合端口监听和 `/health` 探活判断；必要时使用明确解释器路径启动

### 阻碍点 3

- 现象：前端访问地址混乱，`5173` 和 `5174` 来回切换
- 原因：旧进程占用端口，Vite 自动换端口
- 解决：先查监听端口，再决定是继续访问当前端口，还是清理旧进程后重启

## 后续维护约定

以后每次遇到新的启动报错或联调阻碍时，按下面格式追加：

```md
### 阻碍点 N

- 现象：
- 原因：
- 解决：
- 是否已验证：
```

这份文档的目标不是写成“操作说明书”，而是积累真正踩过的坑，减少下次重复排查成本。

## 2026-04-12 新增记录

### 阻碍点 4

- 现象：简历修订流式过程中已经返回了大量内容，但在结束时突然报错 `DeepSeek 简历修订流式输出失败: 保存简历修订记录失败`
- 原因：模型流式生成本身成功，但数据库没有跑到最新迁移，缺少 `resume_revisions` 等新表，导致“流式结束后落库”这一步失败
- 解决：先执行 `D:\anaconda\python.exe -m alembic upgrade head`，再重新验证 `/jobs/{job_id}/revise-resume` 和 `/jobs/{job_id}/assistant/thread`
- 是否已验证：已验证。迁移完成后，简历修订记录可正常保存，助手线程也能读到最新修订结果
