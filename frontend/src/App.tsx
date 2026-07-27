import { BrowserRouter, Routes, Route } from "react-router-dom";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Route placeholders - implementation pending */}
        <Route path="/" element={<div>Dashboard</div>} />
        <Route path="/invoices" element={<div>Invoices</div>} />
        <Route path="/invoices/:id" element={<div>Invoice Detail</div>} />
        <Route path="/chat" element={<div>Records Assistant</div>} />
        <Route path="/admin" element={<div>Admin</div>} />
        <Route path="/login" element={<div>Login</div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
