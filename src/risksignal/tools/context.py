"""Shared plumbing for the tool layer: context, argument checks and the error guard.

The agent (added in a later step) only ever calls the tools. Tools are the only code that
touches the database on its behalf, and they do so read-only with fixed SQL statements.
User input (a system ID, a month count, ...) is only ever passed as a bound parameter,
never pasted into SQL text, so arbitrary SQL cannot be executed through a tool.
"""

import difflib
import functools
import logging
import sqlite3
from collections.abc import Callable
from datetime import date
from functools import cached_property
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from risksignal.data.generator import DATA_END, DATA_START
from risksignal.data.storage import DB_FILENAME, DEFAULT_DATA_DIR, connect, read_table
from risksignal.graph.builder import load_graph
from risksignal.graph.queries import UnknownSystemError
from risksignal.tools.schemas import ToolError, ToolErrorType

logger = logging.getLogger(__name__)

MAX_MONTHS = 120
MIN_SIMULATIONS = 1_000
MAX_SIMULATIONS = 1_000_000
DEFAULT_SIMULATIONS = 100_000
DEFAULT_SEED = 42

_SELECT_SYSTEM = (
    "SELECT system_id, name, description, criticality, primary_process_id FROM systems WHERE system_id = ?"
)
_SELECT_SYSTEM_IDS = "SELECT system_id FROM systems ORDER BY system_id"


class ToolFailure(Exception):
    """Internal signal for an expected failure. The guard turns it into a ``ToolError``."""

    def __init__(self, error_type: ToolErrorType, message: str, suggestions: list[str] | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.suggestions = suggestions or []


class ToolContext:
    """Where the tools read from: the Atlas Bank SQLite database and its dependency graph.

    ``as_of_date`` is the "present" of the synthetic world (the end of the data), so
    "last 12 months" is reproducible and does not depend on today's date.
    ``observation_start`` and ``as_of_date`` are the span over which incident frequency
    is measured. The graph is built once, on first use.
    """

    def __init__(
        self,
        db_path: Path = DEFAULT_DATA_DIR / DB_FILENAME,
        as_of_date: date = DATA_END,
        observation_start: date = DATA_START,
    ) -> None:
        self.db_path = Path(db_path)
        self.as_of_date = as_of_date
        self.observation_start = observation_start

    @cached_property
    def graph(self) -> nx.DiGraph:
        return load_graph(self.db_path)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """Run one of the tool modules' fixed SELECT statements with bound parameters."""
        conn = connect(self.db_path)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def incidents_frame(self) -> pd.DataFrame:
        return read_table("incidents", self.db_path)

    def system_count(self) -> int:
        return int(self.query("SELECT COUNT(*) AS n FROM systems")[0]["n"])

    def get_system(self, system_id: object) -> sqlite3.Row:
        """Return the system row, or raise ``ToolFailure('unknown_system')`` with suggestions."""
        if not isinstance(system_id, str) or not system_id:
            raise ToolFailure("invalid_argument", "system_id must be a non-empty string.")
        rows = self.query(_SELECT_SYSTEM, (system_id,))
        if rows:
            return rows[0]
        known = [r["system_id"] for r in self.query(_SELECT_SYSTEM_IDS)]
        close = difflib.get_close_matches(system_id.strip().upper(), known, n=3, cutoff=0.6)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ToolFailure("unknown_system", f"Unknown system '{system_id}'.{hint}", close or known[:5])


# --------------------------------------------------------------------------- argument checks


def check_int(name: str, value: object, minimum: int, maximum: int) -> int:
    """Return ``value`` if it is a real integer within [minimum, maximum] (booleans are rejected)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolFailure("invalid_argument", f"{name} must be an integer.")
    if not minimum <= value <= maximum:
        raise ToolFailure("invalid_argument", f"{name} must be between {minimum} and {maximum}, got {value}.")
    return value


def check_months(months: object) -> int:
    return check_int("months", months, 1, MAX_MONTHS)


def check_simulation_settings(number_of_simulations: object, random_seed: object) -> tuple[int, int]:
    n = check_int("number_of_simulations", number_of_simulations, MIN_SIMULATIONS, MAX_SIMULATIONS)
    seed = check_int("random_seed", random_seed, 0, 2**32 - 1)
    return n, seed


# --------------------------------------------------------------------------- error guard


def guarded(tool_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Make a tool return a ``ToolError`` instead of raising, whatever goes wrong.

    Expected failures (bad arguments, unknown system or scenario, missing database) become
    typed errors with clear messages. Anything unexpected is logged and reported only as a
    generic ``internal_error``, so no stack trace or internal detail reaches the caller.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except ToolFailure as failure:
                return ToolError(tool_name=tool_name, error_type=failure.error_type,
                                 message=failure.message, suggestions=failure.suggestions)
            except UnknownSystemError as error:
                return ToolError(tool_name=tool_name, error_type="unknown_system", message=str(error))
            except (FileNotFoundError, sqlite3.Error):
                return ToolError(
                    tool_name=tool_name, error_type="data_unavailable",
                    message="The Atlas Bank database is not available. Generate it with: "
                            "python -m risksignal.data.generator",
                )
            except Exception:
                logger.exception("Unexpected error in tool %s", tool_name)
                return ToolError(tool_name=tool_name, error_type="internal_error",
                                 message="The tool failed unexpectedly. No result was produced.")

        return wrapper

    return decorator
