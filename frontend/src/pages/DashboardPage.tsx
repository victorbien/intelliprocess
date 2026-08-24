/** Processing dashboard (task 5.5, AC-3.9.x). */

import { useCallback, useEffect, useState } from "react";

import StatsCards from "@/components/dashboard/StatsCards";
import ProcessingSummary from "@/components/dashboard/ProcessingSummary";
import Spinner from "@/components/common/Spinner";
import ErrorAlert from "@/components/common/ErrorAlert";
import { dashboardApi } from "@/services/api";
import { ApiError, type DashboardStats } from "@/services/types";
import { logger } from "@/services/logger";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await dashboardApi.stats();
      setStats(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load dashboard.";
      logger.error("dashboard", "Stats load failed", err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Dashboard</h1>
          <p className="text-sm text-slate-500">Invoice processing summary (refreshed on load).</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex min-h-[30vh] items-center justify-center">
          <Spinner label="Loading dashboard" />
        </div>
      ) : error ? (
        <ErrorAlert message={error} onRetry={() => void load()} />
      ) : stats ? (
        <>
          <StatsCards stats={stats} />
          <ProcessingSummary activity={stats.recentActivity} />
        </>
      ) : null}
    </div>
  );
}
