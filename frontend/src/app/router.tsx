import { BrowserRouter, Route, Routes } from "react-router-dom";

import { JobsPage } from "../pages/JobsPage";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<JobsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
