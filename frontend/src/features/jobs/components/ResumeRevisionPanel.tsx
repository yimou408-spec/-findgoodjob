import { useEffect, useState } from "react";

import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Field } from "../../../shared/ui/Field";
import { copyText } from "../../../shared/utils/clipboard";
import type { JobResponse } from "../types";

type ResumeRevisionPanelProps = {
  job: JobResponse | null;
  revising: boolean;
  result: string;
  onRevise: (resumeText: string) => Promise<void>;
};

const EXAMPLE_RESUME =
  "4 年互联网产品经理经验，负责过内容平台和效率工具产品的需求分析、原型设计与版本迭代。曾与算法和工程团队合作推进智能问答、内容推荐和文本生成相关功能上线，熟悉用户调研、竞品分析、A/B 测试和数据复盘。具备跨部门沟通和项目推进能力，能够围绕用户体验和业务指标持续优化产品方案。";

export function ResumeRevisionPanel({ job, revising, result, onRevise }: ResumeRevisionPanelProps) {
  // 简历输入和修订结果只属于右侧面板状态，不需要提升到全局 store。
  const [resumeText, setResumeText] = useState(EXAMPLE_RESUME);

  useEffect(() => {
    if (!job) {
      setResumeText(EXAMPLE_RESUME);
    }
  }, [job]);

  return (
    <Card title="简历修订" subtitle="基于当前岗位和岗位分析结果，对原始简历进行定向优化。">
      {!job ? (
        <EmptyState title="等待岗位" description="先创建或选择一条岗位，再输入简历文本进行修订。" />
      ) : (
        <div className="stack">
          <Field label="原始简历" hint="建议粘贴完整简历文本">
            <textarea className="text-area" value={resumeText} onChange={(event) => setResumeText(event.target.value)} />
          </Field>

          <div className="inline-actions">
            <Button onClick={() => onRevise(resumeText)} disabled={revising}>
              {revising ? "修订中..." : "修订简历"}
            </Button>
            <Button variant="secondary" onClick={() => setResumeText(EXAMPLE_RESUME)}>
              填入示例简历
            </Button>
            <Button variant="ghost" onClick={() => result && copyText(result)} disabled={!result}>
              复制修订结果
            </Button>
          </div>

          {result ? (
            <div className="content-box">{result}</div>
          ) : (
            <EmptyState title="尚未生成修订结果" description="完成岗位分析后，点击“修订简历”查看输出。" />
          )}
        </div>
      )}
    </Card>
  );
}
