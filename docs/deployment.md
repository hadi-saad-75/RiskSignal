# Deploying RiskSignal online

RiskSignal is **two programs**: the FastAPI backend (all the logic and the data) and the Streamlit dashboard (a thin client that only talks to the backend over HTTP). To put the dashboard online you must host **both**.

> **Why "connection error"?** The dashboard looks for the API at `http://127.0.0.1:8000` unless told otherwise. Streamlit Community Cloud runs only the Streamlit script, so nothing answers at that address and the dashboard reports "Cannot reach the RiskSignal API". The fix is to host the API somewhere and give the dashboard its address (step 3 below).

> **What has and has not been verified.** The Docker images were never built on the development machine (no Docker engine was available), and the Streamlit Cloud launcher has not been run on Streamlit Cloud. Their steps were emulated locally and are covered by tests, but expect a first deployment to possibly need a small fix. All data are synthetic.

For a local demonstration you do not need any of this: see "Quick start" in the [README](../README.md).

---

## 1. Put the code on GitHub

```bash
git add -A
git status                      # check that .env and *.db are NOT listed
git commit -m "RiskSignal prototype"      # skip if already committed
git branch -M main
git remote add origin https://github.com/<your-user>/RiskSignal.git   # create an empty repository on GitHub first
git push -u origin main
```

`.env` (your API key) and `data/synthetic/atlas_bank.db` are git-ignored on purpose. The database is regenerated from the seeded generator during the API image build.

## 2. Host the API (any host that runs Docker images)

Use a platform that builds a Dockerfile from a GitHub repository (for example Render, Railway or Fly.io; the steps differ slightly per platform).

1. Create a new web service from your GitHub repository and choose **Docker** with the Dockerfile path `Dockerfile.api` and the repository root as build context.
2. Environment variables:
   - `RISKSIGNAL_LLM_PROVIDER=mock` for a public demo (deterministic offline provider, no cost).
   - Or `ANTHROPIC_API_KEY=...` with `RISKSIGNAL_LLM_PROVIDER=anthropic` for the live agent. **Read the security note below first.**
3. The container listens on `$PORT` if the platform sets it, otherwise on 8000.
4. When it is running, open `https://<your-api-url>/health`. It must return `"status":"ok"`. Also try `https://<your-api-url>/docs`.

Free tiers often put a service to sleep when idle; the first request after a pause can take a minute.

## 3. Deploy the dashboard on Streamlit Community Cloud

1. Go to <https://share.streamlit.io> and choose **Create app** (deploy from GitHub). Select your repository and the `main` branch.
2. **Main file path:** `deploy/streamlit_cloud/streamlit_app.py`
3. Open **Advanced settings**:
   - **Python version:** 3.12
   - **Secrets:**
     ```toml
     RISKSIGNAL_API_URL = "https://<your-api-url>"
     ```
     (no trailing path, no quotes inside the URL).
4. Deploy. The dashboard's sidebar should show "API ok" and the Overview should show the counts.

### Why a separate launcher folder

`deploy/streamlit_cloud/` contains the launcher and its own minimal `requirements.txt` (only `streamlit`, `plotly` and `httpx`). Streamlit Cloud uses the dependency file next to the main file in preference to the one in the repository root, so the dashboard does not install the whole engine stack. The launcher also puts `src/` on the Python path (the package is not pip-installed on Streamlit Cloud) and copies the secret `RISKSIGNAL_API_URL` into the environment.

## Troubleshooting

| What you see | Likely cause | Fix |
|---|---|---|
| "Cannot reach the RiskSignal API at http://127.0.0.1:8000" | No API address configured, or the API is not hosted. | Host the API (step 2) and set the `RISKSIGNAL_API_URL` secret (step 3). |
| "Cannot reach the RiskSignal API at https://..." | The API is asleep, crashed or the URL is wrong. | Open `<url>/health` in a browser; wait for a sleeping service to wake; correct the secret. |
| `ModuleNotFoundError: No module named 'risksignal'` | The main file path is not the launcher. | Set the main file path to `deploy/streamlit_cloud/streamlit_app.py`. |
| Sidebar says "AI provider: anthropic (not configured)" | The API has no `ANTHROPIC_API_KEY`. | Set it on the API host, or use `RISKSIGNAL_LLM_PROVIDER=mock`. The rest of the dashboard works without it. |
| "Database: missing" | The API image was built without the data step. | Rebuild the API image from `Dockerfile.api` (it runs the generator). |

## Security notes

- **The API has no authentication.** Anyone with its URL can call it. The data are synthetic, so that is harmless, but if you configure a real `ANTHROPIC_API_KEY` on a public API, anyone can trigger paid model calls. For a public demo use `RISKSIGNAL_LLM_PROVIDER=mock`, or put the API behind access control first.
- Never commit `.env` or paste a key into the repository. Keys belong in the hosting platform's environment settings or Streamlit's Secrets.
- Nothing here is production infrastructure. Real use would need institution data, authentication, audit logging and security review (see [limitations.md](limitations.md)).
