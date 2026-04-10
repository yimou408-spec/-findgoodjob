# FindGoodJob Agent

这是一个用于求职场景的 AI Agent 项目，当前包含：

1. FastAPI 后端：岗位 JD 入库、岗位分析、简历修订
2. React + Vite 前端：单页工作台，用于联调和演示完整求职流程

## 后端启动

```powershell
cd c:\Users\28323\AppData\Local\Packages\Microsoft.VisualStudioCode_8wekyb3d8bbwe\Agent\Findgoodjob
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

启动后访问：

- Swagger 文档：`http://127.0.0.1:8000/docs`
- OpenAPI 描述：`http://127.0.0.1:8000/openapi.json`

## 前端启动

前端目录在 [frontend/package.json](/c:/Users/28323/AppData/Local/Packages/Microsoft.VisualStudioCode_8wekyb3d8bbwe/Agent/Findgoodjob/frontend/package.json)。

```powershell
cd c:\Users\28323\AppData\Local\Packages\Microsoft.VisualStudioCode_8wekyb3d8bbwe\Agent\Findgoodjob\frontend
npm install
copy .env.example .env
npm run dev
```

默认前端地址：

- `http://127.0.0.1:5173`

默认后端地址：

- `http://127.0.0.1:8000`

## 当前前端能力

- 展示数据库中的真实岗位列表
- 新增岗位 JD
- 查看岗位详情
- 调用岗位分析接口
- 调用简历修订接口
- 显示 API 健康状态
- 复制分析结果和简历修订结果

## 联调顺序

1. 先启动后端
2. 再启动前端
3. 打开前端页面后创建岗位
4. 选择岗位并触发分析
5. 输入简历并生成修订结果
