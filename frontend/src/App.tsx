import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/common/Layout";
import ProtectedRoute from "./components/common/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import InvoicesPage from "./pages/InvoicesPage";
import InvoiceDetailPage from "./pages/InvoiceDetailPage";
import DocumentsPage from "./pages/DocumentsPage";
import NotFoundPage from "./pages/NotFoundPage";
import FloatingChatButton from "./components/chat/FloatingChatButton";
import ChatDrawer from "./components/chat/ChatDrawer";

export default function App() {
  const [chatOpen, setChatOpen] = useState(false);
  const { isAuthenticated } = useAuth();

  return (
    <BrowserRouter>
      <Routes>
        {/* Public route */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes — require an authenticated session */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/invoices" replace />} />
            <Route path="/invoices" element={<InvoicesPage />} />
            <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>

      {/* Records Assistant widget — only shown when signed in, and rendered
          outside the route tree so it persists across navigation and sits
          above all page content */}
      {isAuthenticated && (
        <>
          <FloatingChatButton open={chatOpen} onClick={() => setChatOpen((v) => !v)} />
          <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
        </>
      )}
    </BrowserRouter>
  );
}
