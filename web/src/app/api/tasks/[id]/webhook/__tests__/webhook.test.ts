import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/db/queries", () => ({
  getTaskThread: vi.fn(),
  updateTaskThread: vi.fn(),
  saveTaskMessage: vi.fn(),
}));

import { getTaskThread, updateTaskThread, saveTaskMessage } from "@/lib/db/queries";
import { POST } from "../route";

const mockThread = {
  id: "thread-1",
  userId: "user-1",
  status: "running",
};

function makeRequest(body: Record<string, unknown>, apiKey = "test-key") {
  return new Request("http://localhost:3000/api/tasks/thread-1/webhook", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(body),
  });
}

describe("POST /api/tasks/[id]/webhook", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    process.env.RUNNER_API_KEY = "test-key";
    vi.mocked(getTaskThread).mockResolvedValue(mockThread as never);
    vi.mocked(updateTaskThread).mockResolvedValue(mockThread as never);
    vi.mocked(saveTaskMessage).mockResolvedValue({ id: "msg-1" } as never);
  });

  it("rejects missing auth", async () => {
    const req = new Request("http://localhost:3000/api/tasks/thread-1/webhook", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "status", status: "running" }),
    });
    const res = await POST(req, { params: Promise.resolve({ id: "thread-1" }) });
    expect(res.status).toBe(401);
  });

  it("rejects wrong auth", async () => {
    const req = makeRequest({ type: "status", status: "running" }, "wrong-key");
    const res = await POST(req, { params: Promise.resolve({ id: "thread-1" }) });
    expect(res.status).toBe(401);
  });

  it("returns 404 for unknown thread", async () => {
    vi.mocked(getTaskThread).mockResolvedValue(null);
    const req = makeRequest({ type: "status", status: "running" });
    const res = await POST(req, { params: Promise.resolve({ id: "unknown" }) });
    expect(res.status).toBe(404);
  });

  it("updates status on status event", async () => {
    const req = makeRequest({ type: "status", status: "running", task_id: "t1" });
    const res = await POST(req, { params: Promise.resolve({ id: "thread-1" }) });
    expect(res.status).toBe(200);
    expect(updateTaskThread).toHaveBeenCalledWith("thread-1", { status: "running" });
  });

  it("saves message on message event", async () => {
    const req = makeRequest({
      type: "message",
      role: "system",
      content: "Engine selected: claude-code",
      task_id: "t1",
    });
    const res = await POST(req, { params: Promise.resolve({ id: "thread-1" }) });
    expect(res.status).toBe(200);
    expect(saveTaskMessage).toHaveBeenCalledWith({
      threadId: "thread-1",
      role: "system",
      content: "Engine selected: claude-code",
    });
  });

  it("updates thread on complete event", async () => {
    const req = makeRequest({
      type: "complete",
      task_id: "t1",
      status: "complete",
      commitSha: "abc123def456",
      costUsd: 0.01,
      durationMs: 5000,
      filesChanged: ["math_utils.py"],
      engine: "claude-code",
      model: "haiku",
    });
    const res = await POST(req, { params: Promise.resolve({ id: "thread-1" }) });
    expect(res.status).toBe(200);
    expect(updateTaskThread).toHaveBeenCalledWith("thread-1", {
      status: "complete",
      commitSha: "abc123def456",
      costUsd: "0.01",
      durationMs: 5000,
      engine: "claude-code",
      model: "haiku",
    });
    expect(saveTaskMessage).toHaveBeenCalled();
  });

  it("updates thread on failed event", async () => {
    const req = makeRequest({
      type: "failed",
      task_id: "t1",
      errorMessage: "Budget exceeded",
    });
    const res = await POST(req, { params: Promise.resolve({ id: "thread-1" }) });
    expect(res.status).toBe(200);
    expect(updateTaskThread).toHaveBeenCalledWith("thread-1", {
      status: "failed",
      errorMessage: "Budget exceeded",
    });
  });

  it("updates thread on cancelled event", async () => {
    const req = makeRequest({ type: "cancelled", task_id: "t1" });
    const res = await POST(req, { params: Promise.resolve({ id: "thread-1" }) });
    expect(res.status).toBe(200);
    expect(updateTaskThread).toHaveBeenCalledWith("thread-1", { status: "cancelled" });
  });

  it("rejects unknown event type", async () => {
    const req = makeRequest({ type: "bogus" });
    const res = await POST(req, { params: Promise.resolve({ id: "thread-1" }) });
    expect(res.status).toBe(400);
  });
});
