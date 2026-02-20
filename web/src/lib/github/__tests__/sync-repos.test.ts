import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the queries module
const mockUpsertRepository = vi.fn();
vi.mock("@/lib/db/queries", () => ({
  upsertRepository: (...args: unknown[]) => mockUpsertRepository(...args),
}));

// Import after mocks
import { syncGitHubRepos } from "../sync-repos";

describe("syncGitHubRepos", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockUpsertRepository.mockReset();
    mockUpsertRepository.mockResolvedValue({
      id: "repo-1",
      userId: "user-1",
      githubRepoId: 123,
      fullName: "owner/repo",
      installationId: 456,
      isActive: true,
      createdAt: new Date(),
    });
  });

  it("returns no_token error for empty access token", async () => {
    const result = await syncGitHubRepos("user-1", "");
    expect(result).toEqual({ synced: 0, error: "no_token" });
    expect(mockUpsertRepository).not.toHaveBeenCalled();
  });

  it("returns github_api error when installations API fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("Unauthorized", { status: 401, statusText: "Unauthorized" }),
    );

    const result = await syncGitHubRepos("user-1", "bad-token");
    expect(result).toEqual({ synced: 0, error: "github_api_401" });
  });

  it("syncs repos from a single installation", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    // Mock installations response
    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          installations: [
            { id: 100, app_id: 2894826, app_slug: "agentfactory-bot" },
          ],
        }),
        { status: 200 },
      ),
    );

    // Mock repos response
    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          repositories: [
            { id: 1001, full_name: "owner/repo-a" },
            { id: 1002, full_name: "owner/repo-b" },
          ],
        }),
        { status: 200 },
      ),
    );

    const result = await syncGitHubRepos("user-1", "valid-token");

    expect(result).toEqual({ synced: 2 });
    expect(mockUpsertRepository).toHaveBeenCalledTimes(2);
    expect(mockUpsertRepository).toHaveBeenCalledWith({
      userId: "user-1",
      githubRepoId: 1001,
      fullName: "owner/repo-a",
      installationId: 100,
    });
    expect(mockUpsertRepository).toHaveBeenCalledWith({
      userId: "user-1",
      githubRepoId: 1002,
      fullName: "owner/repo-b",
      installationId: 100,
    });
  });

  it("syncs repos from multiple installations", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          installations: [
            { id: 100, app_id: 1, app_slug: "app-a" },
            { id: 200, app_id: 2, app_slug: "app-b" },
          ],
        }),
        { status: 200 },
      ),
    );

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ repositories: [{ id: 1001, full_name: "org/repo-a" }] }),
        { status: 200 },
      ),
    );

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ repositories: [{ id: 2001, full_name: "org/repo-b" }] }),
        { status: 200 },
      ),
    );

    const result = await syncGitHubRepos("user-1", "valid-token");

    expect(result).toEqual({ synced: 2 });
    expect(mockUpsertRepository).toHaveBeenCalledWith(
      expect.objectContaining({ installationId: 100 }),
    );
    expect(mockUpsertRepository).toHaveBeenCalledWith(
      expect.objectContaining({ installationId: 200 }),
    );
  });

  it("continues when one installation's repos fail", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          installations: [
            { id: 100, app_id: 1, app_slug: "app-a" },
            { id: 200, app_id: 2, app_slug: "app-b" },
          ],
        }),
        { status: 200 },
      ),
    );

    // First installation repos fail
    fetchSpy.mockResolvedValueOnce(
      new Response(null, { status: 403 }),
    );

    // Second installation repos succeed
    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ repositories: [{ id: 2001, full_name: "org/repo-b" }] }),
        { status: 200 },
      ),
    );

    const result = await syncGitHubRepos("user-1", "valid-token");

    expect(result).toEqual({ synced: 1 });
    expect(mockUpsertRepository).toHaveBeenCalledTimes(1);
  });

  it("sends correct authorization headers", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify({ installations: [] }), { status: 200 }),
    );

    await syncGitHubRepos("user-1", "my-oauth-token");

    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.github.com/user/installations",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer my-oauth-token",
          Accept: "application/vnd.github+json",
        }),
      }),
    );
  });

  it("returns no_installations error for empty installations array", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ installations: [] }), { status: 200 }),
    );

    const result = await syncGitHubRepos("user-1", "valid-token");
    expect(result).toEqual({ synced: 0, error: "no_installations" });
    expect(mockUpsertRepository).not.toHaveBeenCalled();
  });

  it("handles empty repositories array", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          installations: [{ id: 100, app_id: 1, app_slug: "app" }],
        }),
        { status: 200 },
      ),
    );

    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify({ repositories: [] }), { status: 200 }),
    );

    const result = await syncGitHubRepos("user-1", "valid-token");
    expect(result).toEqual({ synced: 0 });
    expect(mockUpsertRepository).not.toHaveBeenCalled();
  });

  it("continues syncing when upsertRepository throws for one repo", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          installations: [{ id: 100, app_id: 1, app_slug: "app" }],
        }),
        { status: 200 },
      ),
    );

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          repositories: [
            { id: 1001, full_name: "org/repo-a" },
            { id: 1002, full_name: "org/repo-b" },
          ],
        }),
        { status: 200 },
      ),
    );

    // First upsert fails, second succeeds
    mockUpsertRepository
      .mockRejectedValueOnce(new Error("DB error"))
      .mockResolvedValueOnce({
        id: "repo-2",
        userId: "user-1",
        githubRepoId: 1002,
        fullName: "org/repo-b",
        installationId: 100,
        isActive: true,
        createdAt: new Date(),
      });

    const result = await syncGitHubRepos("user-1", "valid-token");
    expect(result).toEqual({ synced: 1 });
    expect(mockUpsertRepository).toHaveBeenCalledTimes(2);
  });
});
