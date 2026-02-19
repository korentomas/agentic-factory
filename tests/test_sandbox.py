"""Tests for Docker sandbox configuration."""

from apps.runner.sandbox import SandboxConfig, build_docker_cmd


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
