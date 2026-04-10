import { type FormEvent, useState } from "react";

import { Button } from "../../../shared/ui/Button";
import { Field } from "../../../shared/ui/Field";
import type { JobCreateInput } from "../types";

type JobCreateModalProps = {
  open: boolean;
  submitting: boolean;
  onClose: () => void;
  onSubmit: (input: JobCreateInput) => Promise<void>;
};

const INITIAL_FORM: JobCreateInput = {
  title: "AI 产品经理",
  company: "某 AI 应用科技公司",
  source: "Boss直聘",
  jd_text:
    "岗位职责：1. 负责 AI 产品的需求分析、功能设计和版本规划，围绕智能助手、知识库问答、内容生成等场景推动产品落地；2. 与算法、工程、设计、运营团队协作，推动大模型能力在实际业务中的应用，包括 Prompt 设计、工作流编排、RAG 检索增强等方向；3. 负责用户研究、竞品分析、数据复盘与指标优化，持续提升产品转化率、留存率和用户满意度。任职要求：1. 3 年及以上互联网产品经理经验，有 AI 产品、AIGC 产品或智能工具类产品经验优先；2. 理解大模型、Prompt、Agent、RAG 等基础概念，能够与算法和工程团队高效沟通；3. 具备良好的需求拆解能力、跨团队推进能力和数据分析能力。加分项：有企业服务产品、知识库产品、效率工具或智能客服相关经验者优先。",
};

export function JobCreateModal({ open, submitting, onClose, onSubmit }: JobCreateModalProps) {
  // 默认示例 JD 让页面打开后就能直接联调后端，不需要先手写岗位内容。
  const [form, setForm] = useState<JobCreateInput>(INITIAL_FORM);

  if (!open) {
    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(form);
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="card-title">新增岗位 JD</h2>
            <p className="card-subtitle">填写岗位基础信息后，立即进入分析和简历修订流程。</p>
          </div>
          <Button variant="ghost" onClick={onClose}>
            关闭
          </Button>
        </div>

        <form className="modal-grid" onSubmit={handleSubmit}>
          <div className="split-fields">
            <Field label="岗位名称" htmlFor="job-title">
              <input
                id="job-title"
                className="text-input"
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
              />
            </Field>
            <Field label="公司名称" htmlFor="job-company">
              <input
                id="job-company"
                className="text-input"
                value={form.company}
                onChange={(event) => setForm((prev) => ({ ...prev, company: event.target.value }))}
              />
            </Field>
          </div>

          <Field label="岗位来源" htmlFor="job-source">
            <input
              id="job-source"
              className="text-input"
              value={form.source ?? ""}
              onChange={(event) => setForm((prev) => ({ ...prev, source: event.target.value }))}
            />
          </Field>

          <Field label="岗位 JD" hint="建议直接粘贴完整 JD 文本">
            <textarea
              className="text-area"
              value={form.jd_text}
              onChange={(event) => setForm((prev) => ({ ...prev, jd_text: event.target.value }))}
            />
          </Field>

          <div className="inline-actions">
            <Button type="submit" disabled={submitting}>
              {submitting ? "创建中..." : "创建岗位"}
            </Button>
            <Button type="button" variant="secondary" onClick={() => setForm(INITIAL_FORM)}>
              恢复示例
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
