# FindGoodJob Agent

这是一个面向求职场景的 AI Agent 项目，当前包含：

1. FastAPI 后端：岗位 JD 入库、岗位分析、简历修订。
2. React + Vite 前端：单页工作台，用于联调和演示完整求职流程。

## 阶段 1：岗位列表 CRUD

本阶段已经完成岗位列表的完整 CRUD 能力：

- 新增岗位：创建岗位标题、公司、来源和 JD 内容。
- 查看岗位：列表查看和详情查看。
- 编辑岗位：在列表中点击“编辑”，通过弹窗修改岗位信息。
- 删除岗位：在列表中点击“删除”，通过确认对话框完成删除。
- 实时刷新：前端使用 React Query 在创建、编辑、删除后自动刷新列表和详情。

如果编辑时修改了 `jd_text`，系统会自动清空旧的岗位分析结果，避免继续展示过期分析内容。

## 简历文件导入

简历修订面板支持上传图片或 PDF，并自动提取文本填充到输入框：

- 支持格式：`PDF`、`PNG`、`JPG/JPEG`、`WEBP`、`BMP`、`TIFF`
- 大小限制：单文件不超过 `10MB`
- PDF 解析：使用 `PyMuPDF`
- 图片 OCR：使用 `Tesseract + pytesseract + Pillow`

如果服务端未安装 Tesseract，可继续上传可提取文本的 PDF；图片 OCR 会返回清晰的错误提示。

## 后端启动

```powershell
cd c:\Users\28323\AppData\Local\Packages\Microsoft.VisualStudioCode_8wekyb3d8bbwe\Agent\Findgoodjob
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

如需启用图片 OCR，请确保系统已安装 `Tesseract OCR` 并可在命令行直接执行 `tesseract`。

启动后访问：

- Swagger 文档：`http://127.0.0.1:8000/docs`
- OpenAPI 描述：`http://127.0.0.1:8000/openapi.json`

## 前端启动

前端目录在 [frontend/package.json](/c:/Users/28323/AppData/Local/Packages/Microsoft.VisualStudioCode_8wekyb3d8bbwe/Agent/Findgoodjob/frontend/package.json)。

```powershell
cd c:\Users\28323\AppData\Local\Packages\Microsoft.VisualStudioCode_8wekyb3d8bbwe\Agent\Findgoodjob\frontend
npm install
npm run dev
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

## 主要接口

- `GET /jobs`：岗位列表
- `POST /jobs`：新增岗位
- `GET /jobs/{job_id}`：岗位详情
- `PUT /jobs/{job_id}`：更新岗位
- `DELETE /jobs/{job_id}`：删除岗位
- `POST /jobs/{job_id}/analyze`：分析岗位 JD
- `POST /jobs/{job_id}/revise-resume`：根据岗位修订简历
- `POST /resume/parse-document`：上传图片 / PDF 并提取文本

## 数据库说明

项目默认使用 SQLite。当前配置中已启用：

- FastAPI `Depends(get_db)` 管理数据库会话生命周期。
- SQLAlchemy 会话显式 `commit` / `rollback`。
- SQLite `SERIALIZABLE` 事务隔离级别。
- SQLite `foreign_keys=ON` 与 `busy_timeout=30000`，提升一致性和并发写入稳定性。

## 联调顺序

1. 先启动后端。
2. 再启动前端。
3. 打开前端页面后创建岗位。
4. 在岗位列表中执行查看、编辑、删除操作。
5. 选择岗位并触发分析。
6. 输入简历并生成修订结果。

## 验收标准对应情况

- 用户可以新增岗位。
- 用户可以查看岗位列表与详情。
- 用户可以编辑岗位并实时看到刷新结果。
- 用户可以删除岗位并看到列表即时更新。
- React Query 会在变更后自动刷新相关数据。
