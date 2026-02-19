import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock auth before importing route
vi.mock("@/lib/auth", () => ({
  auth: vi.fn(),
}));

describe("POST /api/report-bug", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("returns 401 when not authenticated", async () => {
    const { auth } = await import("@/lib/auth");
    vi.mocked(auth).mockResolvedValue(null as never);

    const { POST } = await import("@/app/api/report-bug/route");
    const request = new Request("http://localhost/api/report-bug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Bug", description: "broken" }),
    });

    const response = await POST(request);
    expect(response.status).toBe(401);

    const data = await response.json();
    expect(data.error).toBe("Not authenticated");
  });

  it("returns 401 when session has no accessToken", async () => {
    const { auth } = await import("@/lib/auth");
    vi.mocked(auth).mockResolvedValue({
      user: { name: "Test" },
      accessToken: "",
    } as never);

    const { POST } = await import("@/app/api/report-bug/route");
    const request = new Request("http://localhost/api/report-bug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Bug", description: "broken" }),
    });

    const response = await POST(request);
    expect(response.status).toBe(401);
  });

  it("returns 400 when title is missing", async () => {
    const { auth } = await import("@/lib/auth");
    vi.mocked(auth).mockResolvedValue({
      user: { name: "Test" },
      accessToken: "gho_test",
    } as never);

    const { POST } = await import("@/app/api/report-bug/route");
    const request = new Request("http://localhost/api/report-bug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: "broken" }),
    });

    const response = await POST(request);
    expect(response.status).toBe(400);

    const data = await response.json();
    expect(data.error).toBe("Title is required");
  });

  it("creates GitHub issue and returns URL on success", async () => {
    const { auth } = await import("@/lib/auth");
    vi.mocked(auth).mockResolvedValue({
      user: { name: "Test User", email: "test@example.com" },
      accessToken: "gho_test",
    } as never);

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        html_url: "https://github.com/korentomas/agentic-factory/issues/99",
      }),
    });

    const { POST } = await import("@/app/api/report-bug/route");
    const request = new Request("http://localhost/api/report-bug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Button broken",
        description: "The submit button doesn't work",
        steps: "1. Click submit\n2. Nothing happens",
      }),
    });

    const response = await POST(request);
    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data.issue_url).toBe(
      "https://github.com/korentomas/agentic-factory/issues/99"
    );

    // Verify GitHub API was called correctly
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.github.com/repos/korentomas/agentic-factory/issues",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer gho_test",
        }),
      })
    );
  });

  it("forwards GitHub API error status on failure", async () => {
    const { auth } = await import("@/lib/auth");
    vi.mocked(auth).mockResolvedValue({
      user: { name: "Test User", email: "test@example.com" },
      accessToken: "gho_test",
    } as never);

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 422,
      text: async () => "Validation Failed",
    });

    const { POST } = await import("@/app/api/report-bug/route");
    const request = new Request("http://localhost/api/report-bug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Bug",
        description: "broken",
      }),
    });

    const response = await POST(request);
    expect(response.status).toBe(422);

    const data = await response.json();
    expect(data.error).toBe("Failed to create issue");
    expect(data.detail).toBe("Validation Failed");
  });

  it("includes optional fields in the issue body", async () => {
    const { auth } = await import("@/lib/auth");
    vi.mocked(auth).mockResolvedValue({
      user: { name: "Reporter", email: "reporter@test.com" },
      accessToken: "gho_test",
    } as never);

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        html_url: "https://github.com/korentomas/agentic-factory/issues/100",
      }),
    });

    const { POST } = await import("@/app/api/report-bug/route");
    const request = new Request("http://localhost/api/report-bug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Full report",
        description: "Detailed description",
        steps: "Step 1\nStep 2",
        expected: "It should work",
        actual: "It does not work",
        pageUrl: "https://lailatov.com/dashboard",
      }),
    });

    await POST(request);

    // Verify the body sent to GitHub includes all sections
    const callArgs = fetchMock.mock.calls[0];
    const sentBody = JSON.parse(callArgs[1].body);
    expect(sentBody.title).toBe("[user] Full report");
    expect(sentBody.body).toContain("### Description");
    expect(sentBody.body).toContain("Detailed description");
    expect(sentBody.body).toContain("### Steps to Reproduce");
    expect(sentBody.body).toContain("Step 1\nStep 2");
    expect(sentBody.body).toContain("### Expected Behavior");
    expect(sentBody.body).toContain("It should work");
    expect(sentBody.body).toContain("### Actual Behavior");
    expect(sentBody.body).toContain("It does not work");
    expect(sentBody.body).toContain("### Page URL");
    expect(sentBody.body).toContain("https://lailatov.com/dashboard");
    expect(sentBody.body).toContain("Reporter (reporter@test.com)");
    expect(sentBody.labels).toEqual(["bug", "user-reported", "ai-agent"]);
  });

  it("uses Anonymous and no email when user info is missing", async () => {
    const { auth } = await import("@/lib/auth");
    vi.mocked(auth).mockResolvedValue({
      user: {},
      accessToken: "gho_test",
    } as never);

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        html_url: "https://github.com/korentomas/agentic-factory/issues/101",
      }),
    });

    const { POST } = await import("@/app/api/report-bug/route");
    const request = new Request("http://localhost/api/report-bug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Anon bug",
        description: "Something broke",
      }),
    });

    await POST(request);

    const callArgs = fetchMock.mock.calls[0];
    const sentBody = JSON.parse(callArgs[1].body);
    expect(sentBody.body).toContain("Anonymous");
    expect(sentBody.body).toContain("no email");
  });
});
