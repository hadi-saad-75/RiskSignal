# Deployment

How to deploy RiskSignal as a public demonstration:

| Part | Where | What |
|---|---|---|
| API | Render (Docker web service) | FastAPI backend from `Dockerfile.api`, running with `RISKSIGNAL_LLM_PROVIDER=mock` |
| Dashboard | Streamlit Community Cloud | `deploy/streamlit_cloud/streamlit_app.py`, calling the API through `RISKSIGNAL_API_URL` |

```
browser  ->  Streamlit Community Cloud (dashboard)  --HTTPS-->  Render (FastAPI + synthetic SQLite, mock agent)
```

The dashboard calls the API from Streamlit's **server**, not from the visitor's browser, so no CORS configuration is needed. The dashboard imports none of the backend code; it needs only Streamlit, Plotly and httpx.

> **All data are synthetic and the public deployment uses the deterministic mock agent.** With the mock provider the Assistant is a script that calls the same tools a language model would and writes the summary from their results. It is not a language model, and the dashboard shows `AI provider: mock (ready)` in the sidebar. Say so when you show it. The live Anthropic provider is deliberately **not** enabled (see section 5).

---

## 1. What was verified, and what was not

Verified (details in section 7): the dependency resolution for the Docker image and for Streamlit Cloud on Linux with Python 3.12 (wheels only), the image's build steps on a real Python 3.12.15, the container command through a real `sh` with `PORT=10000` and with `PORT` unset, every API endpoint named below, and the dashboard entrypoint run from the repository root in a clean Python 3.12 environment that contains **only** the dashboard requirements, reading its secret from `st.secrets`.

**Not verified, because it could not be done on the development machine:**

- `docker build` and `docker run` themselves (there is no Docker engine, and WSL is not installed). The Dockerfile steps were replayed by hand instead. **The first Render build is the first real build of this image.**
- Anything on Render or Streamlit Community Cloud themselves (account, quotas, cold starts, the platform-specific install log).
- The live Anthropic provider (not part of this deployment).

---

## 2. Render: the API

Create **New > Web Service**, connect the GitHub repository, then use these settings (labels in the Render dashboard may differ slightly).

| Setting | Value |
|---|---|
| Service type | **Web Service** |
| Repository | `hadi-saad-75/RiskSignal` |
| Branch | `main` |
| Language / runtime | **Docker** |
| Root directory | *(leave empty)* |
| Dockerfile path | `./Dockerfile.api` |
| Docker build context directory | `.` *(the repository root, the default)* |
| Instance type | Free is enough for a demonstration |
| Environment variable | `RISKSIGNAL_LLM_PROVIDER` = `mock` |
| Health check path | `/health` |
| Pre-deploy command / Docker command | *(leave empty: the command is in the Dockerfile)* |
| Auto-deploy | On commit (default) |

**Do not set `PORT`.** Render sets it (default `10000`), and the container command binds to it:

```
sh -c "exec uvicorn risksignal.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"
```

No other variable is needed: `ANTHROPIC_API_KEY` is **not** required with the mock provider and should not be set. The synthetic database is generated during the image build (seed 42, identical every time), so Render's ephemeral filesystem does not matter.

`GET /health` returns HTTP 200 with `"status": "ok"` when the database is readable and contains systems, and `"status": "degraded"` (also HTTP 200) otherwise. Render considers any 2xx or 3xx within five seconds healthy.

**Free-instance behaviour to expect** (from Render's documentation): the service spins down after 15 minutes without traffic and takes about a minute to start again on the next request. The first dashboard load after an idle period can therefore be slow or show "API not reachable" until the API has woken up; reload after a minute. Open `/health` yourself a minute before a demonstration. How Render treats a non-browser request that arrives while the service is waking could not be tested.

---

## 3. Streamlit Community Cloud: the dashboard

On share.streamlit.io choose **Create app > Yup, I have an app**, then:

| Setting | Value |
|---|---|
| Repository | `hadi-saad-75/RiskSignal` |
| Branch | `main` |
| Main file path | `deploy/streamlit_cloud/streamlit_app.py` |
| App URL | any free subdomain you like |
| Python version (Advanced settings) | **3.12** |
| Secrets (Advanced settings) | the TOML below |

```toml
RISKSIGNAL_API_URL = "https://<your-render-service>.onrender.com"
```

Use the public `https://` URL of the Render service, with or without a trailing slash (it is removed). It must start with `http://` or `https://`.

**Dependencies.** Community Cloud uses a requirements file in the entrypoint's directory in preference to one in the repository root, so it installs `deploy/streamlit_cloud/requirements.txt`: exactly `streamlit==1.65.0`, `plotly==7.1.0` and `httpx==0.28.1`. In the build log you should see only these and their dependencies, with no FastAPI, SciPy or Anthropic.

**How the entrypoint works.** Community Cloud runs from the repository root and puts only the entrypoint's own directory on the Python path. `streamlit_app.py` therefore (1) reads `RISKSIGNAL_API_URL` from `st.secrets` (falling back to an environment variable of the same name for local runs), (2) adds `<repository>/src` to `sys.path`, and (3) executes `src/risksignal/ui/app.py` on every rerun. If the secret is missing, the page shows a clear instruction instead of failing.

**Never commit the secret.** `.streamlit/secrets.toml` is git-ignored; paste the value in **App settings > Secrets** instead.

---

## 4. URLs to test after deployment

Replace `API` with your Render URL and `UI` with your Streamlit URL.

**API**

| Check | URL | Expect |
|---|---|---|
| Health | `API/health` | HTTP 200, `"status":"ok"`, `"llm_provider":"mock"`, `"database_available":true` |
| Interactive docs | `API/docs` | Swagger page loads |
| Systems | `API/systems` | 20 systems |
| Focal system | `API/systems/PAYMENT_ENGINE_01` | profile, criticality `critical`, process International Payments |
| Overview | `API/overview` | 20 systems, 10 processes, 8 vendors, 40 controls |
| Unknown system | `API/systems/NOPE` | HTTP 404 with suggestions |

```bash
# bash / macOS / Linux
curl -s -X POST API/simulations -H "Content-Type: application/json" \
     -d '{"system_id":"PAYMENT_ENGINE_01","number_of_simulations":100000,"random_seed":42}'
curl -s -X POST API/scenarios/compare -H "Content-Type: application/json" \
     -d '{"system_id":"PAYMENT_ENGINE_01","scenario_id":"SHARED_VENDOR_OUTAGE"}'
curl -s -X POST API/agent/investigate -H "Content-Type: application/json" \
     -d '{"question":"Investigate PAYMENT_ENGINE_01."}'
```

```powershell
# PowerShell
Invoke-RestMethod -Method Post -Uri "API/simulations" -ContentType "application/json" -Body '{"system_id":"PAYMENT_ENGINE_01"}'
Invoke-RestMethod -Method Post -Uri "API/scenarios/compare" -ContentType "application/json" -Body '{"system_id":"PAYMENT_ENGINE_01","scenario_id":"SHARED_VENDOR_OUTAGE"}'
Invoke-RestMethod -Method Post -Uri "API/agent/investigate" -ContentType "application/json" -Body '{"question":"Investigate PAYMENT_ENGINE_01."}'
```

Expected: the simulation returns `"data_kind":"modelled_output"` with the same figures as the reference table in [demo_script.md](demo_script.md) (section 1.4); the scenario comparison returns the baseline and the stress figures from the same table; the agent returns `"status":"completed"`, `"provider":"mock"`, six tool-activity lines, and no warnings.

**Dashboard**

| Check | URL | Expect |
|---|---|---|
| Overview | `UI/overview` | banner "Research prototype using synthetic Atlas Bank data. Not a calibrated risk model."; sidebar `API ok`, `AI provider: mock (ready)`; counts 20 / 10 / 8 / 40 / 312 |
| System Explorer | `UI/system-explorer` | `PAYMENT_ENGINE_01` profile, incidents, KRIs, controls, shared-exposure map |
| Scenario Lab | `UI/scenario-lab` | estimated λ, μ, σ; running the simulation shows baseline and stress figures matching the API |
| Assistant | `UI` | **Investigate this system** produces six sections and a tool activity log; "Which systems should I look at first?" returns the portfolio comparison |

If the sidebar shows `API not reachable`, wait a minute for the Render service to wake and reload.

---

## 5. Do not enable the live model on a public URL (yet)

The API has **no authentication and no rate limiting**. With `RISKSIGNAL_LLM_PROVIDER=anthropic` and an `ANTHROPIC_API_KEY`, anyone who finds the URL could trigger paid model calls, and a long-running 1,000,000-year simulation request costs CPU on any setup. Before enabling the live provider on a public deployment, add access control and rate limiting (see [technical_review.md](technical_review.md), section 5, and [institutional_validation.md](institutional_validation.md), section 11). Also run the live path once locally first: it has not been exercised against the real API.

---

## 6. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Render deploy fails with "no open ports detected" | The container is not listening on `$PORT`. Check that the service uses `Dockerfile.api` and that you did not override the start command. |
| Render health check keeps failing | Check the path is exactly `/health` and read the deploy log for a startup error. |
| Render build fails during `pip install` | Read the build log; the dependency set resolves to prebuilt Linux wheels on Python 3.12, so a failure points to a platform or network problem. |
| Dashboard shows "The secret `RISKSIGNAL_API_URL` is not set" | Add the secret under App settings > Secrets and reboot the app. |
| Dashboard shows "must start with http:// or https://" | Fix the secret value. |
| Sidebar `API not reachable` | The Render service is asleep, still deploying, or the URL is wrong. Open `API/health` in a browser first. |
| `ModuleNotFoundError: risksignal` on Streamlit Cloud | The main file path is not `deploy/streamlit_cloud/streamlit_app.py`. A different file does not add `src` to the path. |
| Dashboard installs FastAPI, SciPy, etc. | Community Cloud used a different dependency file. Make sure `deploy/streamlit_cloud/requirements.txt` exists on the branch you deploy, and that there is no `uv.lock`, `Pipfile` or `environment.yml` in that folder (they take precedence). |

---

## 7. Verification record

Performed on 2026-10-12 on Windows with a real Python 3.12.15 (obtained with `uv`), because the project targets Python 3.12 and the development environment is 3.13.

- **Dependency resolution** for Linux x86_64, Python 3.12, wheels only (no compiler, as in `python:3.12-slim`): `pyproject.toml` resolved to prebuilt wheels (for example pandas 3.0.6, numpy 2.5.4, scipy 1.18.1, fastapi 0.143.0); the dashboard requirements resolved to streamlit 1.65.0, plotly 7.1.0, httpx 0.28.1 with pandas 3.0.6 and numpy 2.5.4.
- **Image build steps** replayed from a clean directory: stub package and editable install, copy of `src`, data generation (20 systems, 312 incidents). Python 3.12.15 imported the package from the copied source.
- **Container command**: the `CMD` was read out of `Dockerfile.api` and executed by a real POSIX `sh` with the mock provider and no API key. With `PORT=10000` the process listened on `0.0.0.0:10000` and not on 8000; with `PORT` unset it listened on `0.0.0.0:8000`.
- **API behaviour** on that process: `/health` (HTTP 200, `ok`, mock), `/docs`, `/openapi.json`, `/systems` (20), `/systems/PAYMENT_ENGINE_01`, `POST /simulations`, `POST /scenarios/compare`, `POST /agent/investigate` (completed, six tool calls, six sections, no warnings), HTTP 404 for an unknown system and HTTP 422 for an invalid parameter. The process used about 127 MB (Windows working set, indicative only; Render's free instance has 512 MB).
- **Dashboard entrypoint**: run from the repository root in a fresh Python 3.12 environment created from `deploy/streamlit_cloud/requirements.txt` alone (none of `risksignal`, FastAPI, SciPy, NetworkX, Pydantic or Anthropic installed), with the secret supplied through `.streamlit/secrets.toml` (read through `st.secrets`) and a trailing slash that was removed. The sidebar showed `API ok`; the Overview, Scenario Lab (baseline and stress figures identical to the API) and the investigation (six sections, six tool-log lines) all worked. With no secret at all, the page showed the instruction above instead of an error.
- **Test suite**: see the repository's test results; the deployment tests in `tests/test_deployment.py` and `tests/test_render_and_cloud.py` cover the command, the port behaviour, the entrypoint, its secret handling and the requirements file.
