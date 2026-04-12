# 面试经验知识库使用说明

这份说明面向当前 `Findgoodjob` 项目的“小红书面试经验知识库”功能，目标是告诉你怎样把数据写入数据库，以及写入之后如何验证是否成功。

## 1. 先做一次数据库迁移

如果你刚拉最新代码，先执行：

```powershell
cd c:\Users\28323\AppData\Local\Packages\Microsoft.VisualStudioCode_8wekyb3d8bbwe\Agent\Findgoodjob
D:\anaconda\python.exe -m alembic upgrade head
```

迁移完成后，相关表会自动创建，包括：

- `knowledge_sources`
- `knowledge_documents`
- `knowledge_chunks`
- `retrieval_logs`

## 2. 启动后端服务

确保后端已经启动，例如：

```powershell
cd c:\Users\28323\AppData\Local\Packages\Microsoft.VisualStudioCode_8wekyb3d8bbwe\Agent\Findgoodjob
D:\anaconda\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

正常会返回：

```json
{"status":"ok"}
```

## 3. 有三种写入数据库的方式

### 方式 A：手工整理内容导入

适合：

- 你已经人工整理好了面经
- 你拿到的是授权内容
- 你想自己控制结构化字段

接口：

```http
POST /knowledge/import/manual
```

请求体示例：

```json
{
  "items": [
    {
      "source_id": "note-001",
      "url": "https://www.xiaohongshu.com/explore/note-001",
      "title": "美团产品经理一面面经",
      "author_name": "候选人A",
      "published_at": "2026-04-10T10:00:00+08:00",
      "company": "美团",
      "role": "产品经理",
      "interview_stage": "一面",
      "city": "北京",
      "tags": ["产品经理", "面经", "校招"],
      "quality_score": 85,
      "content_raw": "美团产品经理一面主要问用户增长、需求拆解、竞品分析，还会要求候选人做反问。",
      "content_summary": "美团产品经理一面重点考察用户增长、需求拆解和竞品分析。",
      "metadata": {
        "collector": "manual",
        "remark": "人工整理"
      }
    }
  ]
}
```

PowerShell 调用示例：

```powershell
$body = @'
{
  "items": [
    {
      "source_id": "note-001",
      "url": "https://www.xiaohongshu.com/explore/note-001",
      "title": "美团产品经理一面面经",
      "author_name": "候选人A",
      "company": "美团",
      "role": "产品经理",
      "interview_stage": "一面",
      "city": "北京",
      "tags": ["产品经理", "面经"],
      "content_raw": "美团产品经理一面主要问用户增长、需求拆解、竞品分析，还会要求候选人做反问。"
    }
  ]
}
'@

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/knowledge/import/manual" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### 方式 B：研究数据导入

适合：

- 你已经通过研究方式拿到了公开内容
- 你想把这些内容按 `public_research` 方式入库

接口：

```http
POST /knowledge/import/xiaohongshu-research
```

请求体格式和手工导入一样，只是语义不同。系统会把这批数据标记为研究用途。

PowerShell 示例：

```powershell
$body = @'
{
  "items": [
    {
      "source_id": "note-002",
      "url": "https://www.xiaohongshu.com/explore/note-002",
      "title": "字节算法岗 HR 面经验",
      "company": "字节",
      "role": "算法工程师",
      "interview_stage": "HR 面",
      "city": "上海",
      "tags": ["算法", "HR面"],
      "content_raw": "字节算法岗 HR 面主要聊实习经历、转正意愿、薪资预期和城市选择。"
    }
  ]
}
'@

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/knowledge/import/xiaohongshu-research" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### 方式 C：只给小红书链接，自动编译入库

适合：

- 你只有小红书公开链接
- 你希望系统自动抓公开页、抽正文、生成摘要并入库

接口：

```http
POST /knowledge/compile-links/xiaohongshu
```

请求体示例：

```json
{
  "links": [
    "https://www.xiaohongshu.com/explore/note-001",
    "https://www.xiaohongshu.com/explore/note-002"
  ],
  "default_company": "美团",
  "default_role": "产品经理",
  "default_city": "北京"
}
```

PowerShell 调用示例：

```powershell
$body = @'
{
  "links": [
    "https://www.xiaohongshu.com/explore/note-001"
  ],
  "default_company": "美团",
  "default_role": "产品经理",
  "default_city": "北京"
}
'@

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/knowledge/compile-links/xiaohongshu" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

这个接口会自动完成：

- 校验是不是小红书公开链接
- 抓取公开页 HTML
- 提取标题、正文、作者、发布时间
- 判断是不是面试经验
- 生成摘要
- 切 chunk
- 写入知识库

## 4. 最少要提供什么内容

如果你走“手工导入”或“研究导入”，最少建议提供这些字段：

- `url`
- `title`
- `company`
- `role`
- `interview_stage`
- `content_raw`

其中最重要的是：

- `content_raw`

因为真正入库和检索的基础就是它。系统会在后端自动做清洗、脱敏、摘要和切片。

## 5. 写入数据库后，系统会自动做什么

当你调用导入接口后，后端会自动完成这些步骤：

1. 清洗文本噪音
2. 脱敏手机号、微信号、群号等内容
3. 判断是不是有效面试经验
4. 提取公司、岗位、轮次等字段
5. 生成摘要
6. 切分成知识片段
7. 生成伪向量
8. 写入数据库

对应的数据库写入位置是：

- `knowledge_sources`
  - 保存来源信息、结构化字段、清洗后正文、摘要
- `knowledge_documents`
  - 保存知识文档级内容
- `knowledge_chunks`
  - 保存切片和伪向量
- `retrieval_logs`
  - 在你后续搜索时记录检索日志

## 6. 如何确认已经写入成功

### 方法 A：看导入接口返回值

正常情况下会返回类似：

```json
{
  "imported_count": 1,
  "source_platform": "xiaohongshu",
  "compliance_status": "manual",
  "sources": [...]
}
```

如果是链接自动编译接口，会返回：

```json
{
  "requested_count": 1,
  "compiled_count": 1,
  "imported_count": 1,
  "failed_count": 0,
  "results": [...]
}
```

### 方法 B：直接搜索知识库

接口：

```http
GET /knowledge/search
```

PowerShell 示例：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/knowledge/search?query=美团产品经理一面问什么&company=美团&role=产品经理"
```

如果返回 `result_count >= 1`，说明已经成功入库并能被检索。

### 方法 C：给助手走 RAG 检索

接口：

```http
POST /assistant/rag/search
```

示例：

```powershell
$body = @'
{
  "message": "美团产品经理一面常问什么",
  "company": "美团",
  "role": "产品经理",
  "interview_stage": "一面",
  "top_k": 4
}
'@

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/assistant/rag/search" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

如果能返回结果和上下文，说明这条记录已经进入助手可检索范围。

## 7. 常见失败原因

### `invalid_domain`

原因：

- 传入的不是小红书链接

### `http_forbidden`

原因：

- 小红书公开页返回 403
- 当前链接无法直接公开抓取

### `http_not_found`

原因：

- 链接失效
- 帖子不存在

### `content_unavailable`

原因：

- 页面抓到了，但没能抽出正文

### `not_interview_experience`

原因：

- 内容不像有效面试经验
- 更像普通生活帖、广告帖或无关内容

### `import_failed`

原因：

- 编译成功了，但最终写库阶段失败

这种情况优先检查：

- 数据库迁移是否执行
- 后端日志是否有 SQLAlchemy 报错

## 8. 推荐使用顺序

如果你是第一次用，建议按这个顺序：

1. 先跑迁移
2. 先用 `POST /knowledge/import/manual` 导入 1 条最小样例
3. 用 `GET /knowledge/search` 验证检索
4. 再尝试 `POST /knowledge/compile-links/xiaohongshu`
5. 最后用 `POST /assistant/rag/search` 验证助手上下文

这样最稳，排错也最快。

## 9. 一句话总结

如果你已经有整理好的文本，用：

- `POST /knowledge/import/manual`

如果你有研究采集结果，用：

- `POST /knowledge/import/xiaohongshu-research`

如果你只有小红书公开链接，用：

- `POST /knowledge/compile-links/xiaohongshu`
