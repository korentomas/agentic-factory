export type ChatIntent = "quick" | "task";

const TASK_PREFIXES = ["/task", "/fix", "/add", "/implement"];
const TASK_VERBS = ["fix", "add", "implement", "update", "refactor", "remove", "delete", "create", "build", "write"];

export function detectIntent(message: string): ChatIntent {
  const lower = message.toLowerCase().trim();
  if (TASK_PREFIXES.some((p) => lower.startsWith(p))) return "task";
  const firstWord = lower.split(/\s+/)[0];
  if (TASK_VERBS.includes(firstWord)) return "task";
  return "quick";
}

export function stripPrefix(message: string): string {
  const lower = message.toLowerCase().trim();
  for (const prefix of TASK_PREFIXES) {
    if (lower.startsWith(prefix)) return message.slice(prefix.length).trim();
  }
  return message;
}
