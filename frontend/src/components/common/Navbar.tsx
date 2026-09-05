/**
 * Top navigation bar (AC-1.2.x).
 *
 * Links are shown according to the signed-in user's roles:
 *  - Invoices: AP_CLERK, FINANCE_MANAGER, ADMIN
 *  - Documents: all authenticated users
 *  - Dashboard: FINANCE_MANAGER, ADMIN
 *  - Admin: ADMIN only
 */

import { NavLink } from "react-router-dom";

import { useAuth } from "@/context/useAuth";
import type { UserRole } from "@/services/types";

interface NavItem {
  to: string;
  label: string;
  roles?: UserRole[]; // undefined = any authenticated user
}

const NAV_ITEMS: NavItem[] = [
  { to: "/invoices", label: "Invoices", roles: ["AP_CLERK", "FINANCE_MANAGER", "ADMIN"] },
  { to: "/purchase-orders", label: "Purchase Orders", roles: ["AP_CLERK", "FINANCE_MANAGER", "ADMIN"] },
  { to: "/goods-receipts", label: "Goods Receipt", roles: ["AP_CLERK", "FINANCE_MANAGER", "ADMIN"] },
  { to: "/documents", label: "Documents" },
  { to: "/dashboard", label: "Dashboard", roles: ["FINANCE_MANAGER", "ADMIN"] },
  { to: "/admin", label: "Admin", roles: ["ADMIN"] },
];

export default function Navbar() {
  const { user, hasRole, signOut } = useAuth();

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || hasRole(...item.roles),
  );

  return (
    <header className="border-b border-slate-200 bg-white">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-6">
          <span className="text-lg font-bold text-indigo-700">IntelliProcess</span>
          <ul className="flex items-center gap-1">
            {visibleItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm font-medium transition ${
                      isActive
                        ? "bg-indigo-50 text-indigo-700"
                        : "text-slate-600 hover:bg-slate-100"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex items-center gap-3">
          {user && (
            <span className="hidden text-sm text-slate-500 sm:inline">
              {user.email}{" "}
              <span className="text-slate-400">({user.roles.join(", ")})</span>
            </span>
          )}
          <button
            type="button"
            onClick={() => void signOut()}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
          >
            Sign out
          </button>
        </div>
      </nav>
    </header>
  );
}
