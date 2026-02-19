"""Docker sandbox configuration for isolated agent execution.

Wraps engine commands in Docker containers with:
- Network isolation (default: none)
- Resource limits (CPU, memory)
- Read-only root filesystem
- Workspace bind mount
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()

DEFAULT_ALLOWED_HOSTS: list[str] = [
    "pypi.org",
    "files.pythonhosted.org",
    "registry.npmjs.org",
    "github.com",
    "api.github.com",
]


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for a Docker sandbox."""

    image: str
    workspace_mount: str = "/workspace"
    network_mode: str = "none"
    memory_limit: str = "4g"
    cpu_limit: str = "2.0"
    read_only_root: bool = True
    timeout_seconds: int = 3600
    allowed_hosts: list[str] = field(default_factory=list)

    @classmethod
    def with_network(
        cls,
        image: str = "lailatov/sandbox:python",
        allowed_hosts: list[str] | None = None,
        **kwargs: object,
    ) -> SandboxConfig:
        """Create a sandbox config with network access enabled.

        Args:
            image:         Docker image to use.
            allowed_hosts: Hosts the container is allowed to reach.
                           Defaults to DEFAULT_ALLOWED_HOSTS if None.
            **kwargs:      Additional SandboxConfig field overrides.

        Returns:
            A SandboxConfig with network_mode="bridge" and the given hosts.
        """
        hosts = allowed_hosts if allowed_hosts is not None else list(DEFAULT_ALLOWED_HOSTS)
        return cls(
            image=image,
            network_mode="bridge",
            allowed_hosts=hosts,
            **kwargs,  # type: ignore[arg-type]
        )


def build_docker_cmd(
    config: SandboxConfig,
    inner_cmd: list[str],
    *,
    workspace_path: str,
    env_vars: dict[str, str] | None = None,
) -> list[str]:
    """Build a Docker run command that wraps the inner command.

    Args:
        config:         Sandbox configuration.
        inner_cmd:      The command to run inside the container.
        workspace_path: Host path to mount as workspace.
        env_vars:       Environment variables to pass to the container.

    Returns:
        Complete docker command as a list of strings.
    """
    cmd = [
        "docker", "run", "--rm",
        f"--network={config.network_mode}",
        f"--memory={config.memory_limit}",
        f"--cpus={config.cpu_limit}",
        "-v", f"{workspace_path}:{config.workspace_mount}",
        "-w", config.workspace_mount,
    ]

    if config.read_only_root:
        cmd.append("--read-only")
        cmd.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=1g"])  # noqa: S108

    for key, value in (env_vars or {}).items():
        cmd.extend(["-e", f"{key}={value}"])

    cmd.append(config.image)
    cmd.extend(inner_cmd)

    logger.info(
        "sandbox.cmd",
        image=config.image,
        network=config.network_mode,
        memory=config.memory_limit,
    )

    return cmd
