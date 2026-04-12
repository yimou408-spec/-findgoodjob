import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AssistantPage } from "../pages/AssistantPage";
import { JobsPage } from "../pages/JobsPage";
import { KnowledgeBasePage } from "../pages/KnowledgeBasePage";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<JobsPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
      </Routes>
    </BrowserRouter>
  );
}
