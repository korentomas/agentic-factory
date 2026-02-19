import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BugReportDialog } from "@/components/bug-report-dialog";

describe("BugReportDialog", () => {
  it("renders trigger button", () => {
    render(<BugReportDialog />);
    expect(screen.getByText("Report a Bug")).toBeInTheDocument();
  });

  it("opens dialog when trigger is clicked", () => {
    render(<BugReportDialog />);
    fireEvent.click(screen.getByText("Report a Bug"));
    expect(screen.getByText("Submit Bug Report")).toBeInTheDocument();
  });

  it("has title and description fields", () => {
    render(<BugReportDialog />);
    fireEvent.click(screen.getByText("Report a Bug"));
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
  });

  it("closes dialog when close button is clicked", () => {
    render(<BugReportDialog />);
    fireEvent.click(screen.getByText("Report a Bug"));
    expect(screen.getByText("Submit Bug Report")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Close"));
    expect(screen.queryByText("Submit Bug Report")).not.toBeInTheDocument();
  });
});
