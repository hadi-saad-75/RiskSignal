"""Tests for the local demonstration setup: Docker files, health check, .env.example and README.

No Docker engine is needed: the files are parsed and their commands exercised directly.
"""

import io
import re
import tomllib
import urllib.request
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from risksignal.agent.anthropic_provider import DEFAULT_MODEL, AnthropicProvider
from risksignal.api.dependencies import Settings, get_settings, get_tool_context
from risksignal.api.main import create_app
from risksignal.data.generator import generate_atlas_bank
from risksignal.data.storage import DEFAULT_DATA_DIR, save_atlas_bank
from risksignal.tools.context import ToolContext

ROOT = Path(__file__).resolve().parents[1]
KEY_SHAPE = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(read("docker-compose.yml"))


@pytest.fixture(scope="module")
def healthy_app(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    ctx = ToolContext(db_path=save_atlas_bank(generate_atlas_bank(), tmp_path_factory.mktemp("deploy_db")))
    app = create_app()
    app.dependency_overrides[get_tool_context] = lambda: ctx
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=ctx.db_path, llm_provider="anthropic")
    return TestClient(app)


# ----------------------------------------------------------------- files exist


@pytest.mark.parametrize("name", ["Dockerfile.api", "Dockerfile.ui", "docker-compose.yml", ".dockerignore",
                                  ".env.example", "README.md"])
def test_deployment_files_exist(name: str) -> None:
    assert (ROOT / name).is_file()


# ----------------------------------------------------------------- docker compose


def test_compose_defines_exactly_the_api_and_the_ui(compose: dict) -> None:
    assert set(compose["services"]) == {"api", "ui"}  # no database server, no extra infrastructure
    assert compose["services"]["api"]["build"]["dockerfile"] == "Dockerfile.api"
    assert compose["services"]["ui"]["build"]["dockerfile"] == "Dockerfile.ui"


def test_the_ui_waits_until_the_api_is_healthy(compose: dict) -> None:
    assert compose["services"]["ui"]["depends_on"] == {"api": {"condition": "service_healthy"}}
    health = compose["services"]["api"]["healthcheck"]
    assert "/health" in health["test"][-1] and health["retries"] >= 5
    assert "depends_on" not in compose["services"]["api"]


def test_ports_are_published_on_localhost_only(compose: dict) -> None:
    assert compose["services"]["api"]["ports"] == ["127.0.0.1:8000:8000"]
    assert compose["services"]["ui"]["ports"] == ["127.0.0.1:8501:8501"]


def test_environment_variables_are_passed_through_not_hardcoded(compose: dict) -> None:
    api_env = compose["services"]["api"]["environment"]
    assert api_env["ANTHROPIC_API_KEY"] == "${ANTHROPIC_API_KEY:-}"
    assert api_env["RISKSIGNAL_LLM_PROVIDER"] == "${RISKSIGNAL_LLM_PROVIDER:-anthropic}"
    assert compose["services"]["ui"]["environment"]["RISKSIGNAL_API_URL"] == "${RISKSIGNAL_API_URL:-http://api:8000}"
    assert not KEY_SHAPE.search(read("docker-compose.yml"))


def test_compose_has_no_volumes_or_cloud_platform_settings(compose: dict) -> None:
    assert not {"volumes", "secrets", "configs", "networks"} & set(compose)
    assert not any(k in svc for svc in compose["services"].values() for k in ("deploy", "volumes", "env_file"))


# ----------------------------------------------------------------- the images


def test_api_image(compose: dict) -> None:
    text = read("Dockerfile.api")
    assert re.search(r"^FROM python:3\.12", text, re.MULTILINE)
    assert "pip install -e ." in text  # editable: the data directory resolves to /app/data/synthetic
    assert "WORKDIR /app" in text
    assert "RUN python -m risksignal.data.generator" in text  # the explicit data-setup step
    assert text.index("COPY src") > text.index("pip install") and text.index("generator") > text.index("COPY src")
    assert re.search(r"^USER app$", text, re.MULTILINE)  # not root
    assert 'CMD ["sh", "-c", "exec uvicorn risksignal.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]' in text
    assert "EXPOSE 8000" in text


def test_the_data_path_assumed_by_the_api_image_matches_the_code() -> None:
    # In the image the repository root is /app, so the generator writes to /app/data/synthetic,
    # which is where the API looks by default.
    assert DEFAULT_DATA_DIR == ROOT / "data" / "synthetic"


def test_ui_image_is_minimal_and_points_at_the_api() -> None:
    text = read("Dockerfile.ui")
    assert re.search(r"^FROM python:3\.12", text, re.MULTILINE)
    for heavy in ("scipy", "anthropic", "fastapi", "networkx", "pydantic", "uvicorn", "pip install -e"):
        assert heavy not in text, heavy
    copies = re.findall(r"^COPY (\S+) ", text, re.MULTILINE)
    assert copies == [
        "src/risksignal/__init__.py",
        "src/risksignal/text.py",
        "src/risksignal/ui",
    ]
    assert "ENV RISKSIGNAL_API_URL=http://api:8000" in text
    assert re.search(r"^USER app$", text, re.MULTILINE) and "EXPOSE 8501" in text
    assert "src/risksignal/ui/app.py" in text and "--server.address=0.0.0.0" in text and "--server.headless=true" in text


def test_ui_image_dependencies_match_pyproject() -> None:
    declared = tomllib.loads(read("pyproject.toml"))["project"]["dependencies"]
    wanted = {d.split(">")[0]: d for d in declared if d.split(">")[0] in ("streamlit", "plotly", "httpx")}
    installed = re.search(r"RUN pip install (.+)", read("Dockerfile.ui")).group(1)
    specs = re.findall(r'"([^"]+)"', installed)
    assert sorted(specs) == sorted(wanted.values())


def test_the_package_root_is_light_enough_for_the_ui_image() -> None:
    # The UI image copies only risksignal/__init__.py, so it must not import anything heavy.
    imports = [l for l in (ROOT / "src/risksignal/__init__.py").read_text(encoding="utf-8").splitlines()
               if l.startswith(("import ", "from "))]
    assert imports == []


def test_dockerignore_keeps_secrets_and_local_state_out_of_images() -> None:
    lines = set(read(".dockerignore").splitlines())
    assert {".env", ".venv", ".git", "__pycache__", "*.db", ".streamlit"} <= lines
    assert "!.env.example" in lines


# ----------------------------------------------------------------- secrets and .env.example


def test_env_example_has_an_empty_api_key_and_no_secret() -> None:
    lines = read(".env.example").splitlines()
    assert "ANTHROPIC_API_KEY=" in lines  # empty value
    assert not KEY_SHAPE.search(read(".env.example"))
    assigned = [l for l in lines if l and not l.startswith("#")]
    assert assigned == ["ANTHROPIC_API_KEY="]  # every other setting is commented out


def test_env_files_are_git_ignored() -> None:
    assert ".env" in read(".gitignore").splitlines()


def test_no_secret_in_any_deployment_file() -> None:
    for name in ("Dockerfile.api", "Dockerfile.ui", "docker-compose.yml", ".env.example", ".dockerignore", "README.md"):
        assert not KEY_SHAPE.search(read(name)), name


# ----------------------------------------------------------------- health through the container setup


def _run_compose_healthcheck(command: str, client: TestClient) -> int:
    """Execute the compose health-check Python snippet, answering its HTTP call from the real app."""
    def fake_urlopen(url: str, timeout: float = 0) -> io.BytesIO:
        assert url == "http://127.0.0.1:8000/health"
        return io.BytesIO(client.get("/health").content)

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen  # type: ignore[assignment]
    try:
        exec(compile(command, "<healthcheck>", "exec"), {})
    except SystemExit as exit_call:
        return int(exit_call.code)
    finally:
        urllib.request.urlopen = original
    return 0


def test_the_compose_health_check_command_passes_against_the_app(compose: dict, healthy_app: TestClient) -> None:
    command = compose["services"]["api"]["healthcheck"]["test"][-1]
    assert _run_compose_healthcheck(command, healthy_app) == 0


def test_the_compose_health_check_command_fails_when_the_database_is_missing(compose: dict, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_tool_context] = lambda: ToolContext(db_path=tmp_path / "missing.db")
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=tmp_path / "missing.db", llm_provider="anthropic")
    assert _run_compose_healthcheck(compose["services"]["api"]["healthcheck"]["test"][-1], TestClient(app)) == 1


def test_health_works_in_the_container_default_configuration(healthy_app: TestClient) -> None:
    body = healthy_app.get("/health").json()  # no API key, default provider: still healthy
    assert body["status"] == "ok" and body["database_available"] is True
    assert body["llm_provider"] == "anthropic" and body["llm_configured"] is False


def test_empty_variables_passed_by_compose_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Compose sets unset variables to the empty string ("${VAR:-}"); that must behave like "not set".
    monkeypatch.setattr("risksignal.api.dependencies.load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr("risksignal.agent.anthropic_provider.load_dotenv", lambda *a, **k: False)
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "RISKSIGNAL_LLM_PROVIDER", "RISKSIGNAL_DB_PATH"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.llm_provider == "anthropic" and settings.db_path == DEFAULT_DATA_DIR / "atlas_bank.db"
    finally:
        get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    assert AnthropicProvider().model == DEFAULT_MODEL  # empty ANTHROPIC_MODEL is ignored


# ----------------------------------------------------------------- README instructions


@pytest.mark.parametrize("command", [
    "docker compose up --build",
    "python -m venv .venv",
    ".venv\\Scripts\\Activate.ps1",
    "source .venv/bin/activate",
    'pip install -e ".[dev]"',
    "python -m risksignal.data.generator",
    "pytest",
    "uvicorn risksignal.api.main:app --reload",
    "streamlit run src/risksignal/ui/app.py",
    "docker compose down",
    "http://localhost:8501",
    "http://localhost:8000/health",
    "RISKSIGNAL_LLM_PROVIDER=mock docker compose up --build",
    "cp .env.example .env",
])
def test_readme_gives_the_exact_commands(command: str) -> None:
    assert command in read("README.md")


def test_readme_documents_every_setting_and_the_docker_caveat() -> None:
    text = read("README.md")
    for variable in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "RISKSIGNAL_LLM_PROVIDER", "RISKSIGNAL_API_URL", "RISKSIGNAL_DB_PATH"):
        assert variable in text
    assert "no Docker engine was available" in text  # honest about what was verified
    assert "Planned architecture" not in text and "Planned demo" not in text
