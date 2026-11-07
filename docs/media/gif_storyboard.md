# RiskSignal Walkthrough Storyboard

Simple workflow animation, 16:9 at 1280 x 720. Total duration: 12 seconds. Three beats: independent evidence, AI investigation that relates evidence, and a real Monte Carlo loss histogram generated from the repository's synthetic dataset. No source code, repository tree, terminal, or test output is shown.

| Scene | File / screen shown | Duration | Overlay text | Viewer takeaway |
|---|---|---:|---|---|
| 1. Independent evidence | Separate evidence lanes for recent incidents, KRIs, controls, and vendor dependencies for `PAYMENT_ENGINE_01` | 2.5 s | Separate signals | Values shown are actual outputs from the synthetic dataset: 5 recent incidents, 2 deployment mentions, KRI change, overdue control `C002`, and shared vendor `V04`. |
| 2. Agent investigation | The evidence lanes pass through deterministic tools to the AI investigator, which assembles a connected evidence summary and investigation questions | 4.5 s | The agent brings evidence into context | Show the actual shared-vendor link to `PAYMENT_ENGINE_02`; label relationships as connected exposure, not causation. The agent does not calculate the loss metrics. |
| 3. Monte Carlo loss | A histogram using the actual 100,000 seeded Monte Carlo outputs; mark P95 and P99 with their verified values | 5.0 s | Simulated annual aggregate loss | Plot the engine's histogram (which covers losses through P99) and state that data are synthetic and assumptions illustrative. |

## Production notes

- The GIF is a rendered workflow visualization, not a VS Code screen recording or a live application capture.
- No repository/code UI, terminal output, test counts, or credentials are part of the animation.
- Incident/KRI/control/vendor labels and Monte Carlo values are taken from an executed offline investigation and seeded simulation on the generated synthetic data. The histogram explicitly identifies its P99 range and does not imply a forecast.
- The graph and stochastic model support the workflow; the AI investigation agent remains the main focus.
- MP4 is optional; the required deliverable is `docs/media/risksignal_vscode_walkthrough.gif`.