import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeverityBadge, StatusBadge } from "../SeverityBadge";

describe("SeverityBadge", () => {
  it("renders the severity label", () => {
    render(<SeverityBadge severity="high" />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("falls back to medium styling for unknown severities without crashing", () => {
    render(<SeverityBadge severity="totally-unknown" />);
    expect(screen.getByText("totally-unknown")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("renders pass and fail states distinctly", () => {
    const { rerender } = render(<StatusBadge status="pass" />);
    expect(screen.getByText("pass")).toBeInTheDocument();
    rerender(<StatusBadge status="fail" />);
    expect(screen.getByText("fail")).toBeInTheDocument();
  });
});
