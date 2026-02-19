export function ConnectRepo() {
  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-8)]">
      <h2 className="text-[var(--text-xl)] font-medium">
        Connect your first repository
      </h2>
      <p className="mt-[var(--space-3)] max-w-[52ch] text-[var(--color-text-secondary)]">
        Install the LailaTov GitHub App on your repository to start turning
        issues into pull requests automatically.
      </p>
      <a
        href="https://github.com/apps/agentfactory-bot/installations/new"
        className="mt-[var(--space-6)] inline-block rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-6)] py-[var(--space-3)] text-[var(--text-sm)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
      >
        Install GitHub App
      </a>
    </section>
  );
}
