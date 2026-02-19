"use client";

import { useState } from "react";

export function BugReportDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">(
    "idle",
  );
  const [issueUrl, setIssueUrl] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("sending");

    try {
      const resp = await fetch("/api/report-bug", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          description,
          steps,
          pageUrl: typeof window !== "undefined" ? window.location.href : "",
        }),
      });

      if (!resp.ok) {
        setStatus("error");
        return;
      }

      const data = await resp.json();
      setIssueUrl(data.issue_url);
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  function handleClose() {
    setIsOpen(false);
    setStatus("idle");
    setTitle("");
    setDescription("");
    setSteps("");
    setIssueUrl("");
  }

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
      >
        Report a Bug
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={handleClose}
          />
          <div className="relative w-full max-w-lg rounded-[var(--radius-lg)] bg-[var(--color-bg)] p-[var(--space-8)] shadow-xl">
            <button
              onClick={handleClose}
              aria-label="Close"
              className="absolute right-[var(--space-4)] top-[var(--space-4)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
            >
              ×
            </button>

            <h2 className="text-[var(--text-xl)] font-semibold">
              Submit Bug Report
            </h2>

            {status === "sent" ? (
              <div className="mt-[var(--space-4)]">
                <p className="text-[var(--color-text-secondary)]">
                  Bug report submitted successfully.
                </p>
                {issueUrl && (
                  <a
                    href={issueUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-[var(--space-2)] block text-[var(--color-accent)] hover:underline"
                  >
                    View issue on GitHub
                  </a>
                )}
                <button
                  onClick={handleClose}
                  className="mt-[var(--space-4)] rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-4)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--color-text-inverse)]"
                >
                  Close
                </button>
              </div>
            ) : (
              <form
                onSubmit={handleSubmit}
                className="mt-[var(--space-4)] space-y-[var(--space-4)]"
              >
                <div>
                  <label
                    htmlFor="bug-title"
                    className="block text-[var(--text-sm)] font-medium"
                  >
                    Title
                  </label>
                  <input
                    id="bug-title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                    className="mt-[var(--space-1)] w-full rounded-[var(--radius-md)] border border-[var(--color-border)] bg-transparent px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)]"
                    placeholder="Brief description of the bug"
                  />
                </div>
                <div>
                  <label
                    htmlFor="bug-description"
                    className="block text-[var(--text-sm)] font-medium"
                  >
                    Description
                  </label>
                  <textarea
                    id="bug-description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    required
                    rows={4}
                    className="mt-[var(--space-1)] w-full rounded-[var(--radius-md)] border border-[var(--color-border)] bg-transparent px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)]"
                    placeholder="What happened? What did you expect?"
                  />
                </div>
                <div>
                  <label
                    htmlFor="bug-steps"
                    className="block text-[var(--text-sm)] font-medium"
                  >
                    Steps to Reproduce (optional)
                  </label>
                  <textarea
                    id="bug-steps"
                    value={steps}
                    onChange={(e) => setSteps(e.target.value)}
                    rows={3}
                    className="mt-[var(--space-1)] w-full rounded-[var(--radius-md)] border border-[var(--color-border)] bg-transparent px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)]"
                    placeholder="1. Go to...\n2. Click on...\n3. See error"
                  />
                </div>
                {status === "error" && (
                  <p className="text-[var(--text-sm)] text-[var(--color-error)]">
                    Failed to submit report. Please try again.
                  </p>
                )}
                <button
                  type="submit"
                  disabled={status === "sending"}
                  className="w-full rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-4)] py-[var(--space-3)] text-[var(--text-sm)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
                >
                  {status === "sending" ? "Submitting..." : "Submit Report"}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
