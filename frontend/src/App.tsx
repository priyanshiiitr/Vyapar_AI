import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { AppLayout } from "@/layouts/AppLayout";
import { OverviewPage } from "@/pages/OverviewPage";
import { InvoicesPage } from "@/pages/InvoicesPage";
import { ReconciliationPage } from "@/pages/ReconciliationPage";
import { CollectionsPage } from "@/pages/CollectionsPage";
import { AIPage } from "@/pages/AIPage";
import { ApprovalsPage } from "@/pages/ApprovalsPage";
import { ActivityPage } from "@/pages/ActivityPage";
import { EvaluationPage } from "@/pages/EvaluationPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { WhatsAppMockPage } from "@/pages/WhatsAppMockPage";

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/overview" element={<Navigate to="/" replace />} />
            <Route path="/invoices" element={<InvoicesPage />} />
            <Route path="/reconciliation" element={<ReconciliationPage />} />
            <Route path="/collections" element={<CollectionsPage />} />
            <Route path="/ai" element={<AIPage />} />
            <Route path="/approvals" element={<ApprovalsPage />} />
            <Route path="/whatsapp" element={<WhatsAppMockPage />} />
            <Route path="/activity" element={<ActivityPage />} />
            <Route path="/evaluation" element={<EvaluationPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  );
}
