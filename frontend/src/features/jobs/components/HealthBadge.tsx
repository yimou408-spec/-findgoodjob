import { StatusPill } from "../../../shared/ui/StatusPill";
import { useHealth } from "../hooks";

export function HealthBadge() {
  const { data, error, isLoading } = useHealth();

  if (isLoading) {
    return <StatusPill tone="neutral">后端检查中</StatusPill>;
  }

  if (error) {
    return <StatusPill tone="danger">后端未连接</StatusPill>;
  }

  return <StatusPill tone={data?.status === "ok" ? "success" : "warning"}>API 正常</StatusPill>;
}
