"""HTTP client for the RiskSignal API. The UI talks to the backend only through this class.

The UI never imports the stochastic engine, graph, tools or agent code. Every number it
shows was computed by the API. A ``fastapi.testclient.TestClient`` can be passed as ``client``
for tests.
"""

import os
from typing import Any

import httpx

DEFAULT_API_URL = "http://127.0.0.1:8000"
# Fail fast if the API is not running, but allow a live agent investigation (several model calls) to finish.
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 300.0


class ApiUnavailableError(Exception):
    """The API could not be reached (not running, wrong URL, or timed out)."""


class ApiRequestError(Exception):
    """The API answered with an error. Carries the error body's type, message and suggestions."""

    def __init__(self, status_code: int, error_type: str, message: str, suggestions: list[str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.suggestions = suggestions or []


class ApiClient:
    def __init__(self, base_url: str | None = None, client: httpx.Client | None = None) -> None:
        self.base_url = (base_url or os.environ.get("RISKSIGNAL_API_URL") or DEFAULT_API_URL).rstrip("/")
        self._http = client or httpx.Client(
            base_url=self.base_url, timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT))

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as error:
            raise ApiUnavailableError(f"The RiskSignal API at {self.base_url} did not answer in time.") from error
        except httpx.TransportError as error:
            raise ApiUnavailableError(f"Cannot reach the RiskSignal API at {self.base_url}.") from error
        if response.is_success:
            return response.json()
        raise self._error_from(response)

    @staticmethod
    def _error_from(response: httpx.Response) -> ApiRequestError:
        try:
            body = response.json()["error"]
            return ApiRequestError(response.status_code, body["type"], body["message"], body.get("suggestions"))
        except (ValueError, KeyError, TypeError):
            return ApiRequestError(response.status_code, "http_error", f"The API returned HTTP {response.status_code}.")

    # ------------------------------------------------------------------ read endpoints

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def overview(self, recent_incidents: int = 10) -> dict[str, Any]:
        return self._request("GET", "/overview", params={"recent_incidents": recent_incidents})

    def systems(self) -> dict[str, Any]:
        return self._request("GET", "/systems")

    def profile(self, system_id: str) -> dict[str, Any]:
        return self._request("GET", f"/systems/{system_id}")

    def incidents(self, system_id: str, months: int = 12) -> dict[str, Any]:
        return self._request("GET", f"/systems/{system_id}/incidents", params={"months": months})

    def controls(self, system_id: str) -> dict[str, Any]:
        return self._request("GET", f"/systems/{system_id}/controls")

    def dependencies(self, system_id: str) -> dict[str, Any]:
        return self._request("GET", f"/systems/{system_id}/dependencies")

    def kri(self, system_id: str, months: int = 12) -> dict[str, Any]:
        return self._request("GET", f"/systems/{system_id}/kri", params={"months": months})

    def scenarios(self) -> dict[str, Any]:
        return self._request("GET", "/scenarios")

    # ------------------------------------------------------------------ simulation endpoints

    def simulate(self, system_id: str, number_of_simulations: int, random_seed: int) -> dict[str, Any]:
        return self._request("POST", "/simulations", json={
            "system_id": system_id, "number_of_simulations": number_of_simulations, "random_seed": random_seed})

    def compare(self, system_id: str, scenario_id: str, number_of_simulations: int, random_seed: int) -> dict[str, Any]:
        return self._request("POST", "/scenarios/compare", json={
            "system_id": system_id, "scenario_id": scenario_id,
            "number_of_simulations": number_of_simulations, "random_seed": random_seed})

    def compare_custom(
        self, system_id: str, lambda_multiplier: float, severity_sigma_multiplier: float,
        number_of_simulations: int, random_seed: int, severity_mu_shift: float = 0.0,
    ) -> dict[str, Any]:
        return self._request("POST", "/scenarios/compare-custom", json={
            "system_id": system_id, "lambda_multiplier": lambda_multiplier,
            "severity_mu_shift": severity_mu_shift, "severity_sigma_multiplier": severity_sigma_multiplier,
            "number_of_simulations": number_of_simulations, "random_seed": random_seed})

    # ------------------------------------------------------------------ agent

    def investigate(self, question: str, include_tool_outputs: bool = True) -> dict[str, Any]:
        return self._request("POST", "/agent/investigate", json={
            "question": question, "include_tool_outputs": include_tool_outputs})
