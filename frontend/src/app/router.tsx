import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AssistantPage } from "../pages/AssistantPage";
import { JobsPage } from "../pages/JobsPage";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<JobsPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
      </Routes>
    </BrowserRouter>
  );
}
