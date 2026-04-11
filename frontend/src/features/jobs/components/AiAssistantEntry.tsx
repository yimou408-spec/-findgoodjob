import { Link } from "react-router-dom";

function AssistantSparkIcon() {
  return (
    <svg className="assistant-entry-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2.5 13.95 8l5.55 1.95L13.95 11.9 12 17.5l-1.95-5.6L4.5 9.95 10.05 8 12 2.5Z"
        fill="currentColor"
      />
      <path d="M18.2 3.8 18.9 5.7l1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7.7-1.9Z" fill="currentColor" />
      <path d="m18.2 14.2 1 2.8 2.8 1-2.8 1-1 2.8-1-2.8-2.8-1 2.8-1 1-2.8Z" fill="currentColor" />
    </svg>
  );
}

export function AiAssistantEntry() {
  return (
    <Link to="/assistant" className="assistant-entry-button">
      <span className="assistant-entry-icon-shell">
        <AssistantSparkIcon />
      </span>
      <span className="assistant-entry-copy">
        <span className="assistant-entry-title">AI 求职助手</span>
        <span className="assistant-entry-subtitle">进入聊天工作台</span>
      </span>
      <span className="assistant-entry-badge">Beta</span>
    </Link>
  );
}
