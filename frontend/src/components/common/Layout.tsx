import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

const NAV = [
  { to: "/invoices", label: "📄 Invoices" },
  { to: "/documents", label: "📁 Documents" },
  { to: "/dashboard", label: "📊 Dashboard" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top bar */}
      <header className="bg-blue-700 text-white shadow-md">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <span className="font-bold text-lg tracking-tight">
            ⚡ IntelliProcess AI
          </span>
          <nav className="flex items-center gap-6">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive
                      ? "text-white underline underline-offset-4"
                      : "text-blue-200 hover:text-white"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}

            {user && (
              <div className="flex items-center gap-3 border-l border-blue-500 pl-6">
                <span className="text-xs text-blue-100" title={user.email}>
                  {user.email}
                  <span className="ml-1 rounded bg-blue-800 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                    {user.role}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-md bg-blue-800 px-3 py-1 text-xs font-medium text-white transition hover:bg-blue-900"
                >
                  Sign out
                </button>
              </div>
            )}
          </nav>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-8">
        <Outlet />
      </main>

      <footer className="text-center text-xs text-gray-400 py-3 border-t">
        IntelliProcess AI — Capstone Demo &nbsp;|&nbsp; Backend:{" "}
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="text-blue-500 underline"
        >
          API Docs ↗
        </a>
      </footer>
    </div>
  );
}
