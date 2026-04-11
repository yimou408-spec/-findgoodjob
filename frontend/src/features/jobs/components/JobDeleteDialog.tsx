import { Button } from "../../../shared/ui/Button";
import type { JobResponse } from "../types";

type JobDeleteDialogProps = {
  open: boolean;
  job: JobResponse | null;
  deleting: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
};

export function JobDeleteDialog({ open, job, deleting, onClose, onConfirm }: JobDeleteDialogProps) {
  if (!open || !job) {
    return null;
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel modal-panel-compact" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="card-title">删除岗位</h2>
            <p className="card-subtitle">删除后不可恢复，岗位分析结果也会一并移除。</p>
          </div>
          <Button variant="ghost" onClick={onClose}>
            关闭
          </Button>
        </div>

        <div className="content-box">
          确认删除岗位《{job.title}》吗？
          <div className="job-list-meta">公司：{job.company}</div>
        </div>

        <div className="inline-actions modal-actions">
          <Button type="button" variant="ghost" onClick={onClose} disabled={deleting}>
            取消
          </Button>
          <Button type="button" className="btn-danger" onClick={() => void onConfirm()} disabled={deleting}>
            {deleting ? "删除中..." : "确认删除"}
          </Button>
        </div>
      </div>
    </div>
  );
}
