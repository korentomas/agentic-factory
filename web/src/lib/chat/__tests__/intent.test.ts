import { describe, it, expect } from "vitest";
import { detectIntent, stripPrefix } from "../intent";

describe("detectIntent", () => {
  it("detects /task prefix as task intent", () => {
    expect(detectIntent("/task fix the login bug")).toBe("task");
  });

  it("detects /fix prefix as task intent", () => {
    expect(detectIntent("/fix broken tests")).toBe("task");
  });

  it("detects /add prefix as task intent", () => {
    expect(detectIntent("/add error handling to API")).toBe("task");
  });

  it("detects /implement prefix as task intent", () => {
    expect(detectIntent("/implement caching layer")).toBe("task");
  });

  it("detects 'fix' verb as task intent", () => {
    expect(detectIntent("fix the broken test")).toBe("task");
  });

  it("detects 'add' verb as task intent", () => {
    expect(detectIntent("add a new endpoint for users")).toBe("task");
  });

  it("detects 'implement' verb as task intent", () => {
    expect(detectIntent("implement retry logic")).toBe("task");
  });

  it("detects 'update' verb as task intent", () => {
    expect(detectIntent("update the config parser")).toBe("task");
  });

  it("detects 'refactor' verb as task intent", () => {
    expect(detectIntent("refactor the auth module")).toBe("task");
  });

  it("detects 'remove' verb as task intent", () => {
    expect(detectIntent("remove deprecated endpoints")).toBe("task");
  });

  it("detects 'delete' verb as task intent", () => {
    expect(detectIntent("delete unused imports")).toBe("task");
  });

  it("detects 'create' verb as task intent", () => {
    expect(detectIntent("create a new service class")).toBe("task");
  });

  it("detects 'build' verb as task intent", () => {
    expect(detectIntent("build the dashboard component")).toBe("task");
  });

  it("detects 'write' verb as task intent", () => {
    expect(detectIntent("write tests for the auth module")).toBe("task");
  });

  it("returns quick for general questions", () => {
    expect(detectIntent("what does this function do?")).toBe("quick");
  });

  it("returns quick for explanation requests", () => {
    expect(detectIntent("explain the auth flow")).toBe("quick");
  });

  it("returns quick for how-to questions", () => {
    expect(detectIntent("how does the pipeline work?")).toBe("quick");
  });

  it("is case-insensitive for prefixes", () => {
    expect(detectIntent("/TASK fix something")).toBe("task");
  });

  it("is case-insensitive for verbs", () => {
    expect(detectIntent("Fix the broken test")).toBe("task");
  });

  it("handles leading whitespace", () => {
    expect(detectIntent("  fix the test")).toBe("task");
  });

  it("returns quick for empty string", () => {
    expect(detectIntent("")).toBe("quick");
  });
});

describe("stripPrefix", () => {
  it("strips /task prefix", () => {
    expect(stripPrefix("/task fix the login bug")).toBe("fix the login bug");
  });

  it("strips /fix prefix", () => {
    expect(stripPrefix("/fix broken tests")).toBe("broken tests");
  });

  it("strips /add prefix", () => {
    expect(stripPrefix("/add error handling")).toBe("error handling");
  });

  it("strips /implement prefix", () => {
    expect(stripPrefix("/implement caching")).toBe("caching");
  });

  it("returns original message when no prefix matches", () => {
    expect(stripPrefix("what does this do?")).toBe("what does this do?");
  });

  it("handles extra whitespace after prefix", () => {
    expect(stripPrefix("/task   fix the test")).toBe("fix the test");
  });

  it("is case-insensitive for prefix matching", () => {
    expect(stripPrefix("/TASK fix something")).toBe("fix something");
  });
});
