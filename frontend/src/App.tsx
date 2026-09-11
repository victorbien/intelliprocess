import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Layout from "./components/common/Layout";
import ProtectedRoute from "./components/common/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import { useAuth } from "./context/useAuth";
import DashboardPage from "./pages/DashboardPage";
import InvoicesPage from "./pages/InvoicesPage";
import InvoiceDetailPage from "./pages/InvoiceDetailPage";
import PurchaseOrdersPage from "./pages/PurchaseOrdersPage";
import PurchaseOrderDetailPage from "./pages/PurchaseOrderDetailPage";
import GoodsReceiptsPage from "./pages/GoodsReceiptsPage";
import GoodsReceiptDetailPage from "./pages/GoodsReceiptDetailPage";
import DocumentsPage from "./pages/DocumentsPage";
import AdminPage from "./pages/AdminPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import FloatingChatButton from "./components/chat/FloatingChatButton";
import ChatDrawer from "./components/chat/ChatDrawer";

/** Records Assistant widget — only mounted for authenticated users. */
function ChatWidget() {
  const { isAuthenticated } = useAuth();
  const [open, setOpen] = useState(false);

  if (!isAuthenticated) return null;

  return (
    <>
      <FloatingChatButton open={open} onClick={() => setOpen((v) => !v)} />
      <ChatDrawer open={open} onClose={() => setOpen(false)} />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/invoices" replace />} />
            <Route
              path="/invoices"
              element={
                <ProtectedRoute roles={["AP_CLERK", "FINANCE_MANAGER", "ADMIN"]}>
                  <InvoicesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/invoices/:id"
              element={
                <ProtectedRoute roles={["AP_CLERK", "FINANCE_MANAGER", "ADMIN"]}>
                  <InvoiceDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/purchase-orders"
              element={
                <ProtectedRoute roles={["AP_CLERK", "FINANCE_MANAGER", "ADMIN"]}>
                  <PurchaseOrdersPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/purchase-orders/:id"
              element={
                <ProtectedRoute roles={["AP_CLERK", "FINANCE_MANAGER", "ADMIN"]}>
                  <PurchaseOrderDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/goods-receipts"
              element={
                <ProtectedRoute roles={["AP_CLERK", "FINANCE_MANAGER", "ADMIN"]}>
                  <GoodsReceiptsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/goods-receipts/:id"
              element={
                <ProtectedRoute roles={["AP_CLERK", "FINANCE_MANAGER", "ADMIN"]}>
                  <GoodsReceiptDetailPage />
                </ProtectedRoute>
              }
            />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute roles={["FINANCE_MANAGER", "ADMIN"]}>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <ProtectedRoute roles={["ADMIN"]}>
                  <AdminPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>

        <ChatWidget />
      </BrowserRouter>
    </AuthProvider>
  );
}
