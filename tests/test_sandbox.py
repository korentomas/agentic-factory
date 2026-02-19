"""Tests for Docker sandbox configuration."""

from apps.runner.sandbox import DEFAULT_ALLOWED_HOSTS, SandboxConfig, build_docker_cmd


def test_build_docker_cmd_wraps_command() -> None:
    config = SandboxConfig(
        image="lailatov/sandbox:python",
        workspace_mount="/workspace",
        network_mode="none",
        memory_limit="2g",
        cpu_limit="2.0",
    )
    inner_cmd = ["claude", "--print", "--model", "claude-sonnet-4-6"]
    result = build_docker_cmd(config, inner_cmd, workspace_path="/tmp/ws/repo")

    assert result[0] == "docker"
    assert "run" in result
    assert "--rm" in result
    assert "--network=none" in result
    assert "--memory=2g" in result
    assert "--cpus=2.0" in result
    # Check workspace mount
    v_idx = result.index("-v")
    assert result[v_idx + 1] == "/tmp/ws/repo:/workspace"
    # Inner command at the end
    assert result[-4:] == inner_cmd


def test_build_docker_cmd_allows_network() -> None:
    config = SandboxConfig(
        image="lailatov/sandbox:python",
        network_mode="bridge",
    )
    cmd = build_docker_cmd(config, ["echo", "hi"], workspace_path="/tmp/ws")
    assert "--network=bridge" in cmd


def test_sandbox_config_defaults() -> None:
    config = SandboxConfig(image="lailatov/sandbox:python")
    assert config.network_mode == "none"
    assert config.memory_limit == "4g"
    assert config.cpu_limit == "2.0"
    assert config.read_only_root is True


def test_build_docker_cmd_env_vars() -> None:
    config = SandboxConfig(image="lailatov/sandbox:python")
    cmd = build_docker_cmd(
        config,
        ["echo"],
        workspace_path="/tmp/ws",
        env_vars={"API_KEY": "secret"},
    )
    e_idx = cmd.index("-e")
    assert cmd[e_idx + 1] == "API_KEY=secret"


def test_build_docker_cmd_read_only_root() -> None:
    config = SandboxConfig(image="lailatov/sandbox:python", read_only_root=True)
    cmd = build_docker_cmd(config, ["echo"], workspace_path="/tmp/ws")
    assert "--read-only" in cmd
    assert "--tmpfs" in cmd


def test_build_docker_cmd_writable_root() -> None:
    config = SandboxConfig(image="lailatov/sandbox:python", read_only_root=False)
    cmd = build_docker_cmd(config, ["echo"], workspace_path="/tmp/ws")
    assert "--read-only" not in cmd


def test_build_docker_cmd_multiple_env_vars() -> None:
    config = SandboxConfig(image="lailatov/sandbox:python")
    cmd = build_docker_cmd(
        config,
        ["echo"],
        workspace_path="/tmp/ws",
        env_vars={"KEY1": "val1", "KEY2": "val2"},
    )
    e_indices = [i for i, x in enumerate(cmd) if x == "-e"]
    assert len(e_indices) == 2


# --- Network isolation tests ---


def test_default_network_mode_is_none() -> None:
    """SandboxConfig defaults to fully-isolated network_mode='none'."""
    config = SandboxConfig(image="lailatov/sandbox:python")
    assert config.network_mode == "none"
    assert config.allowed_hosts == []


def test_build_docker_cmd_includes_network_none_by_default() -> None:
    """Default build_docker_cmd emits --network=none for full isolation."""
    config = SandboxConfig(image="lailatov/sandbox:python")
    cmd = build_docker_cmd(config, ["echo"], workspace_path="/tmp/ws")
    assert "--network=none" in cmd


def test_with_network_returns_bridge_mode_with_default_hosts() -> None:
    """with_network() without args gives bridge mode + DEFAULT_ALLOWED_HOSTS."""
    config = SandboxConfig.with_network()
    assert config.network_mode == "bridge"
    assert config.allowed_hosts == DEFAULT_ALLOWED_HOSTS
    # Verify it's a copy, not the same list object
    assert config.allowed_hosts is not DEFAULT_ALLOWED_HOSTS


def test_with_network_uses_custom_hosts() -> None:
    """with_network(custom_hosts) uses exactly those hosts."""
    custom = ["internal.corp", "mirror.local"]
    config = SandboxConfig.with_network(allowed_hosts=custom)
    assert config.network_mode == "bridge"
    assert config.allowed_hosts == custom


def test_build_docker_cmd_bridge_mode_includes_network_bridge() -> None:
    """Bridge-mode config emits --network=bridge in the docker command."""
    config = SandboxConfig.with_network()
    cmd = build_docker_cmd(config, ["npm", "install"], workspace_path="/tmp/ws")
    assert "--network=bridge" in cmd
    assert "--network=none" not in cmd


def test_network_mode_appears_in_generated_command() -> None:
    """The exact network_mode value is present in the generated command string."""
    for mode in ("none", "bridge", "host"):
        config = SandboxConfig(image="lailatov/sandbox:python", network_mode=mode)
        cmd = build_docker_cmd(config, ["echo"], workspace_path="/tmp/ws")
        assert f"--network={mode}" in cmd


def test_with_network_preserves_other_defaults() -> None:
    """with_network() keeps standard defaults for memory, cpu, etc."""
    config = SandboxConfig.with_network()
    assert config.memory_limit == "4g"
    assert config.cpu_limit == "2.0"
    assert config.read_only_root is True
    assert config.timeout_seconds == 3600


def test_with_network_accepts_overrides() -> None:
    """with_network() forwards extra kwargs to the dataclass constructor."""
    config = SandboxConfig.with_network(
        image="custom:latest",
        memory_limit="8g",
        cpu_limit="4.0",
    )
    assert config.image == "custom:latest"
    assert config.memory_limit == "8g"
    assert config.cpu_limit == "4.0"
    assert config.network_mode == "bridge"


def test_default_allowed_hosts_contains_expected_entries() -> None:
    """DEFAULT_ALLOWED_HOSTS includes the key development hosts."""
    expected = {
        "pypi.org",
        "files.pythonhosted.org",
        "registry.npmjs.org",
        "github.com",
        "api.github.com",
    }
    assert set(DEFAULT_ALLOWED_HOSTS) == expected


def test_with_network_empty_hosts_list() -> None:
    """Passing an explicit empty list gives bridge mode with no allowed hosts."""
    config = SandboxConfig.with_network(allowed_hosts=[])
    assert config.network_mode == "bridge"
    assert config.allowed_hosts == []
