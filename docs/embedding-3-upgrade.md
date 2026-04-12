# 智谱 Embedding-3 配置与重建说明

当前项目已经从伪向量检索升级为真正的智谱向量检索：

- 岗位工作台知识库使用 `embedding-3`
- 面经知识库使用 `embedding-3`
- 默认维度为 `1024`
- 向量继续存储在 `knowledge_chunks.embedding_vector`

## 本地配置

不要把真实密钥写进仓库中的 `.env`。  
请把真实密钥只写进本地 `.env.local`。

推荐配置：

```env
ZHIPU_API_KEY=your-real-key
ZHIPU_EMBEDDING_MODEL=embedding-3
ZHIPU_EMBEDDING_DIMENSIONS=1024
ZHIPU_EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4/embeddings
ZHIPU_EMBEDDING_TIMEOUT_SECONDS=60
```

项目现在会按这个顺序读取配置：

1. `.env`
2. `.env.local`

所以你可以把本地敏感配置放进 `.env.local` 覆盖公共默认值。

## 首次升级后要做什么

如果你的数据库里已经有历史知识库数据，升级后要重建向量：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/knowledge/reindex" -Method Post
Invoke-RestMethod -Uri "http://127.0.0.1:8000/jobs/14/knowledge/reindex" -Method Post
```

说明：

- `/knowledge/reindex`：重建历史面经知识库的真实向量
- `/jobs/{job_id}/knowledge/reindex`：重建单个岗位工作台知识库的真实向量

## 什么时候必须重建

以下情况都必须重建全部向量：

- 更换 `ZHIPU_EMBEDDING_MODEL`
- 更换 `ZHIPU_EMBEDDING_DIMENSIONS`
- 从旧的伪向量版本升级到当前版本

## 安全提醒

如果真实 API Key 曾经出现在聊天、截图、日志或提交记录里，应尽快在智谱平台轮换该密钥，再更新本地 `.env.local`。
