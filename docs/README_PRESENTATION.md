# RiskSignal - presentation-day launch

Run the application locally on your laptop. No public deployment or Docker is needed.
These commands assume the existing `.venv` and synthetic database are already installed.

## 1. Start the backend

Open a PowerShell terminal and run:

```powershell
Set-Location "C:\Users\hadis\Desktop\RiskSignal"
$env:RISKSIGNAL_LLM_PROVIDER="mock"
.\.venv\Scripts\python.exe -m uvicorn risksignal.api.main:app --host 127.0.0.1 --port 8000
```

Keep this terminal open. The mock provider is a deterministic script, **not a live LLM**.
It needs no model API key.

## 2. Start the interface

Open a second PowerShell terminal and run:

```powershell
Set-Location "C:\Users\hadis\Desktop\RiskSignal"
.\.venv\Scripts\python.exe -m streamlit run src\risksignal\ui\app.py --server.address 127.0.0.1 --server.port 8501 --client.toolbarMode viewer
```

Keep this terminal open too.

## 3. Open and check

Open **http://localhost:8501** in your browser.

The API health check is **http://127.0.0.1:8000/health**.
Check that the interface reports the API is available and the provider is mock.

## Before the meeting

- Start the application 20-30 minutes before presenting.
- Select `PAYMENT_ENGINE_01` and run one investigation to check it works.
- Return to Risk Investigator at `/` and use **Refresh evidence** to clear the rehearsal answer before sharing your screen.
- Keep screenshots or a short recording as a backup.
- Say: "The records are synthetic. This demonstration uses a scripted offline provider, not a live LLM."
- Notice a signal, click **Investigate system**, then show one finding, its source and the justified follow-up.
- Explain Monte Carlo results as outcomes under illustrative assumptions, not forecasts.

## Stop the application

Press **Ctrl+C** in each terminal after the presentation.

## Sharing with managers

Attach the [one-page overview](RiskSignal_One_Page_Overview.pdf) to a short email and offer a demo.
Do not send the localhost URL: it works only on your laptop.
Do not make the current application public; it has no authentication and is not suitable for confidential data.

The [M2 preparation guide](RiskSignal_M2_Presentation_Guide.pdf) is for your rehearsal, not the initial teaser email.

## If it does not start

- If `.venv\Scripts\python.exe` is missing, follow the installation steps in the [main README](../README.md) before the meeting.
- If a port is already in use, first check whether RiskSignal is already running. Do not stop unfamiliar processes.
- If the interface cannot reach the API, check the first terminal for an error.
- Do not install dependencies or regenerate the dataset for the first time during the presentation.
