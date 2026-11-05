"""Deployment readiness: the Render API container command and the Streamlit Community Cloud entrypoint.

No Docker engine, Render account or Streamlit Cloud account is needed. The container command is run
through a real POSIX ``sh`` (skipped only if none exists), and the Cloud entrypoint is run with
Streamlit's headless test harness, reading its secret from ``st.secrets`` exactly as on Community Cloud.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from packaging.requirements import Requirement
from streamlit.testing.v1 import AppTest

from risksignal.api.dependencies import Settings, get_settings, get_tool_context
from risksignal.api.main import create_app
from risksignal.data.generator import generate_atlas_bank
from risksignal.data.storage import save_atlas_bank
from risksignal.tools.context import ToolContext
from risksignal.ui.api_client import ApiClient

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "deploy" / "streamlit_cloud" / "streamlit_app.py"
REQUIREMENTS = ROOT / "deploy" / "streamlit_cloud" / "requirements.txt"
SECRET = "RISKSIGNAL_API_URL"
LANDING_TITLE = "Operational risk, connected."
BANNER = "Research prototype based on synthetic Atlas Bank data, results are not calibrated to observed losses."


def find_sh() -> str | None:
    found = shutil.which("sh")
    if found:
        return found
    for candidate in (r"C:\Program Files\Git\usr\bin\sh.exe", r"C:\Program Files\Git\bin\sh.exe"):
        if Path(candidate).exists():
            return candidate
    return None


def container_command() -> list[str]:
    line = next(l for l in (ROOT / "Dockerfile.api").read_text(encoding="utf-8").splitlines() if l.startswith("CMD "))
    return json.loads(line[len("CMD "):])


# ----------------------------------------------------------------- nothing is an empty placeholder


@pytest.mark.parametrize("path", [
    "Dockerfile.api", "deploy/streamlit_cloud/streamlit_app.py", "deploy/streamlit_cloud/requirements.txt",
    "docs/deployment.md", "docs/demo_script.md", "README.md",
])
def test_deployment_files_are_not_empty_placeholders(path: str) -> None:
    assert (ROOT / path).stat().st_size > 200, f"{path} is empty or a stub"


# ----------------------------------------------------------------- Render: the API container command


def test_container_command_binds_all_interfaces_on_the_port_variable() -> None:
    command = container_command()
    assert command[:2] == ["sh", "-c"] and len(command) == 3  # shell form, so ${PORT} is expanded
    text = command[2]
    assert text.startswith("exec uvicorn risksignal.api.main:app")  # uvicorn is the main process and gets stop signals
    assert "--host 0.0.0.0" in text and "--port ${PORT:-8000}" in text
    assert "127.0.0.1" not in text and "localhost" not in text


@pytest.mark.skipif(find_sh() is None, reason="no POSIX sh available to expand ${PORT}")
@pytest.mark.parametrize("port, expected", [("10000", "10000"), ("4321", "4321"), (None, "8000")])
def test_container_command_uses_render_port_and_falls_back_to_8000(port: str | None, expected: str) -> None:
    text = container_command()[2]
    assert "exec uvicorn" in text
    echoed = text.replace("exec uvicorn", "echo uvicorn", 1)  # print the command line instead of starting the server
    env = {k: v for k, v in os.environ.items() if k != "PORT"}
    if port is not None:
        env["PORT"] = port
    result = subprocess.run([find_sh(), "-c", echoed], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["uvicorn", "risksignal.api.main:app", "--host", "0.0.0.0", "--port", expected]


def test_the_build_context_keeps_everything_the_dockerfile_copies() -> None:
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    copied = {name for line in dockerfile.splitlines() if line.startswith("COPY ")
              for name in line.split()[1:-1]}
    assert {"pyproject.toml", "README.md", "src"} <= copied
    ignored = {l.strip().rstrip("/") for l in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.startswith(("#", "!"))}
    assert not (copied & ignored), f"the Docker build context excludes files the image needs: {copied & ignored}"


def test_ui_image_includes_the_introduction_walkthrough_animation() -> None:
    asset = "docs/media/risksignal_vscode_walkthrough.gif"
    assert (ROOT / asset).is_file()
    assert f"COPY {asset} {asset}" in (ROOT / "Dockerfile.ui").read_text(encoding="utf-8")
    assert f"!{asset}" in (ROOT / ".dockerignore").read_text(encoding="utf-8")


def test_the_api_image_needs_no_secret_and_runs_as_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" not in dockerfile and "sk-ant-" not in dockerfile
    assert re.search(r"^USER app$", dockerfile, re.MULTILINE)
    assert "RUN python -m risksignal.data.generator" in dockerfile  # the database is baked in: Render's disk is ephemeral


def test_render_configuration_works_from_environment_variables_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure the app the way Render does (environment variables only, no overrides, no API key)."""
    db_path = save_atlas_bank(generate_atlas_bank(), tmp_path)
    monkeypatch.setattr("risksignal.api.dependencies.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("RISKSIGNAL_LLM_PROVIDER", "mock")
    monkeypatch.setenv("RISKSIGNAL_DB_PATH", str(db_path))
    get_settings.cache_clear()
    get_tool_context.cache_clear()
    try:
        client = TestClient(create_app())
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok" and health.json()["llm_provider"] == "mock"
        assert health.json()["llm_configured"] is True and health.json()["database_available"] is True
        assert len(client.get("/systems").json()["systems"]) == 20
        investigation = client.post("/agent/investigate", json={"question": "Investigate PAYMENT_ENGINE_01."})
        assert investigation.status_code == 200 and investigation.json()["provider"] == "mock"
        assert investigation.json()["status"] == "completed" and investigation.json()["warnings"] == []
    finally:
        get_settings.cache_clear()
        get_tool_context.cache_clear()


# ----------------------------------------------------------------- Streamlit Community Cloud: files


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add((node.module or "").split(".")[0])
    return names


def test_requirements_are_exact_pins_of_only_what_the_dashboard_needs() -> None:
    lines = [l.strip() for l in REQUIREMENTS.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    requirements = [Requirement(l) for l in lines]
    assert sorted(r.name for r in requirements) == ["httpx", "plotly", "streamlit"]
    assert all(l.count("==") == 1 for l in lines)  # exact pins: the versions that were tested


def test_pinned_versions_satisfy_the_project_constraints() -> None:
    import tomllib

    declared = {Requirement(d).name: Requirement(d) for d in tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            pinned = Requirement(line)
            version = next(iter(pinned.specifier)).version
            assert declared[pinned.name].specifier.contains(version), f"{pinned.name} {version} violates pyproject.toml"


def test_the_dashboard_and_its_entrypoint_import_nothing_beyond_the_pinned_packages() -> None:
    allowed = {"streamlit", "plotly", "httpx", "risksignal"}
    for path in [ENTRYPOINT, *(ROOT / "src" / "risksignal" / "ui").rglob("*.py")]:
        third_party = {name for name in _imports(path) if name and name not in sys.stdlib_module_names}
        assert third_party <= allowed, f"{path.name} imports {third_party - allowed}, which Community Cloud would not install"


def test_the_entrypoint_does_not_import_backend_business_logic() -> None:
    imported = _imports(ENTRYPOINT)
    assert imported <= {"os", "runpy", "sys", "pathlib", "streamlit"}
    source = ENTRYPOINT.read_text(encoding="utf-8")
    for backend in ("stochastic", "graph", "tools", "agent", "risksignal.api", "risksignal.data", "sqlite3", "anthropic"):
        assert not re.search(rf"^\s*(import|from)\s+.*\b{re.escape(backend)}\b", source, re.MULTILINE), backend
    assert 'st.secrets[SECRET_NAME]' in source and "RISKSIGNAL_API_URL" in source


def test_the_dependency_folder_contains_only_one_dependency_file() -> None:
    names = {p.name for p in (ROOT / "deploy" / "streamlit_cloud").iterdir()}
    assert not names & {"uv.lock", "Pipfile", "environment.yml", "pyproject.toml"}  # these would take precedence over requirements.txt
    assert "requirements.txt" in names and "streamlit_app.py" in names


def test_the_secrets_file_is_never_committed() -> None:
    assert ".streamlit/secrets.toml" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    tracked = subprocess.run(["git", "ls-files", ".streamlit"], cwd=ROOT, capture_output=True, text=True).stdout
    assert "secrets.toml" not in tracked


# ----------------------------------------------------------------- Streamlit Community Cloud: behaviour


@pytest.fixture(scope="module")
def api_client(tmp_path_factory: pytest.TempPathFactory) -> ApiClient:
    ctx = ToolContext(db_path=save_atlas_bank(generate_atlas_bank(), tmp_path_factory.mktemp("cloud_db")))
    app = create_app()
    app.dependency_overrides[get_tool_context] = lambda: ctx
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=ctx.db_path, llm_provider="mock")
    return ApiClient(base_url="http://testserver", client=TestClient(app))


def run_entrypoint(secrets: dict[str, str] | None = None, client: ApiClient | None = None) -> AppTest:
    at = AppTest.from_file(str(ENTRYPOINT), default_timeout=60)
    for key, value in (secrets or {}).items():
        at.secrets[key] = value
    if client is not None:
        at.session_state["api_client"] = client
    return at.run()


def texts(elements) -> str:
    return " | ".join(str(e.value) for e in elements)


def test_secret_is_read_from_st_secrets_and_the_dashboard_runs(api_client: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRET, raising=False)
    at = run_entrypoint({SECRET: "http://testserver/"}, api_client)
    assert not at.exception
    assert at.title[0].value == LANDING_TITLE and BANNER in texts(at.warning)
    assert os.environ[SECRET] == "http://testserver"  # trailing slash removed, value passed to the dashboard's API client
    assert "API ok" in texts(at.sidebar.success) and "Language model: mock (configured)" in texts(at.sidebar.caption)
    assert "Start the live demo" in texts(at.get("page_link"))


def test_the_dashboard_client_targets_the_secret_url_without_a_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRET, raising=False)
    at = run_entrypoint({SECRET: "http://127.0.0.1:1/"})  # nothing listens on port 1: fails fast, must not crash
    assert not at.exception
    assert at.session_state["api_client"].base_url == "http://127.0.0.1:1"
    assert "API unavailable" in texts(at.sidebar.error) and "http://127.0.0.1:1" in texts(at.sidebar.caption)


def test_every_rerun_executes_the_dashboard_again(api_client: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRET, raising=False)
    at = run_entrypoint({SECRET: "http://testserver"}, api_client)
    assert at.title[0].value == LANDING_TITLE
    at.run()  # a second script run (a Streamlit rerun) must render the page again, not an empty app
    assert not at.exception and at.title[0].value == LANDING_TITLE and BANNER in texts(at.warning)


def test_a_missing_secret_gives_a_clear_message_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRET, raising=False)
    at = run_entrypoint()
    assert not at.exception
    assert SECRET in texts(at.error) and "not set" in texts(at.error)
    assert "https://<your-api-host>" in texts(at.markdown)
    assert not at.sidebar.success and not at.metric  # the dashboard itself did not start


@pytest.mark.parametrize("value", ["risksignal-api.onrender.com", "ftp://host", "   "])
def test_an_invalid_secret_value_is_reported(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRET, raising=False)
    at = run_entrypoint({SECRET: value})
    assert not at.exception and SECRET in texts(at.error)
    assert ("must start with" in texts(at.error)) or ("not set" in texts(at.error))  # blank behaves like missing


def test_the_environment_variable_is_a_local_fallback(api_client: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET, "http://testserver/")
    at = run_entrypoint(client=api_client)  # no st.secrets entry
    assert not at.exception and at.title[0].value == LANDING_TITLE and os.environ[SECRET] == "http://testserver"


def test_a_secret_takes_precedence_over_the_environment(api_client: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET, "http://from-environment.invalid")
    run_entrypoint({SECRET: "http://testserver"}, api_client)
    assert os.environ[SECRET] == "http://testserver"
