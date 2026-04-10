# job-agent

基于 **FastAPI + SQLAlchemy + LangChain(DeepSeek)** 的求职 Agent 后端。

## 已实现能力
1. 添加岗位 JD 到数据库。
2. 调用 LLM 对 JD 分析（摘要/技能/风险）。
3. 调用 LLM 对简历做针对 JD 的改写，并保存修订结果。

## 快速启动
```bash
cd job-agent
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

接口文档：`http://127.0.0.1:8000/docs`
