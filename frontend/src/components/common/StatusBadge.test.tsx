import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import StatusBadge from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders a friendly label for a known status", () => {
    render(<StatusBadge status="ESCALATED" />);
    expect(screen.getByText("Escalated")).toBeInTheDocument();
  });

  it("renders APPROVED with green styling", () => {
    render(<StatusBadge status="APPROVED" />);
    const badge = screen.getByText("Approved");
    expect(badge.className).toMatch(/green/);
  });

  it("falls back to the raw value for an unknown status", () => {
    render(<StatusBadge status="WEIRD" />);
    expect(screen.getByText("WEIRD")).toBeInTheDocument();
  });
});
