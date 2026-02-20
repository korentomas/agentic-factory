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
        className="rounded-md border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary"
      >
        Report a Bug
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={handleClose}
          />
          <div className="relative w-full max-w-lg rounded-lg bg-background p-8 shadow-xl">
            <button
              onClick={handleClose}
              aria-label="Close"
              className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
            >
              ×
            </button>

            <h2 className="text-xl font-semibold">
              Submit Bug Report
            </h2>

            {status === "sent" ? (
              <div className="mt-4">
                <p className="text-muted-foreground">
                  Bug report submitted successfully.
                </p>
                {issueUrl && (
                  <a
                    href={issueUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 block text-primary hover:underline"
                  >
                    View issue on GitHub
                  </a>
                )}
                <button
                  onClick={handleClose}
                  className="mt-4 rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
                >
                  Close
                </button>
              </div>
            ) : (
              <form
                onSubmit={handleSubmit}
                className="mt-4 space-y-4"
              >
                <div>
                  <label
                    htmlFor="bug-title"
                    className="block text-sm font-medium"
                  >
                    Title
                  </label>
                  <input
                    id="bug-title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                    className="mt-1 w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm"
                    placeholder="Brief description of the bug"
                  />
                </div>
                <div>
                  <label
                    htmlFor="bug-description"
                    className="block text-sm font-medium"
                  >
                    Description
                  </label>
                  <textarea
                    id="bug-description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    required
                    rows={4}
                    className="mt-1 w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm"
                    placeholder="What happened? What did you expect?"
                  />
                </div>
                <div>
                  <label
                    htmlFor="bug-steps"
                    className="block text-sm font-medium"
                  >
                    Steps to Reproduce (optional)
                  </label>
                  <textarea
                    id="bug-steps"
                    value={steps}
                    onChange={(e) => setSteps(e.target.value)}
                    rows={3}
                    className="mt-1 w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm"
                    placeholder="1. Go to...\n2. Click on...\n3. See error"
                  />
                </div>
                {status === "error" && (
                  <p className="text-sm text-[var(--color-error)]">
                    Failed to submit report. Please try again.
                  </p>
                )}
                <button
                  type="submit"
                  disabled={status === "sending"}
                  className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
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
