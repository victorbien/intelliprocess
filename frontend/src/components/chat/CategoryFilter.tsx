/** Category dropdown for scoping document search (AC-4.4.x). */

import type { DocumentCategory } from "@/services/types";

export type CategoryOption = DocumentCategory | "all";

const OPTIONS: { value: CategoryOption; label: string }[] = [
  { value: "all", label: "All categories" },
  { value: "policies", label: "Policies" },
  { value: "contracts", label: "Contracts" },
  { value: "finance", label: "Finance" },
  { value: "procurement", label: "Procurement" },
  { value: "general", label: "General" },
];

interface CategoryFilterProps {
  value: CategoryOption;
  onChange: (value: CategoryOption) => void;
  disabled?: boolean;
}

export default function CategoryFilter({ value, onChange, disabled }: CategoryFilterProps) {
  return (
    <label className="flex items-center gap-1 text-xs text-slate-500">
      <span className="sr-only">Document category</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as CategoryOption)}
        className="rounded-md border border-slate-300 px-2 py-1 text-xs focus:border-indigo-500 focus:outline-none disabled:opacity-60"
      >
        {OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
