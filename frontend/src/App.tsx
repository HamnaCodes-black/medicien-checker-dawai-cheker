import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AdminPage } from "./pages/AdminPage";
import { AnalyzingPage } from "./pages/AnalyzingPage";
import { CapturePage } from "./pages/CapturePage";
import { HistoryPage } from "./pages/HistoryPage";
import { HomePage } from "./pages/HomePage";
import { HowItWorksPage } from "./pages/HowItWorksPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { ReportPage } from "./pages/ReportPage";
import { ResultPage } from "./pages/ResultPage";
import { SavedResultPage } from "./pages/SavedResultPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="onboarding" element={<OnboardingPage />} />
        <Route path="scan" element={<CapturePage />} />
        <Route path="capture" element={<Navigate to="/scan" replace />} />
        <Route path="analyzing" element={<AnalyzingPage />} />
        <Route path="result" element={<ResultPage />} />
        <Route path="saved/:id" element={<SavedResultPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="report" element={<ReportPage />} />
        <Route path="how-it-works" element={<HowItWorksPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
