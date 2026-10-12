"""Deterministic generator for the fictional Atlas Bank synthetic dataset.

PURPOSE: demonstrate software architecture and workflow only. Nothing here is real,
realistic, calibrated or predictive. See docs/limitations.md.

How the data are made
---------------------
* Systems, processes, vendors and dependencies are written by hand (a small, readable
  ecosystem with a payments focus).
* Controls, incidents and KRIs combine hand-written parts with seeded random draws.
* PAYMENT_ENGINE_01 (the focal demo system) has a deliberately constructed story:
  recent incidents, an overdue control, mildly worsening KRIs and a vendor shared with
  PAYMENT_ENGINE_02. Other systems also get some drift so it is not the only one.
* Incident losses are drawn from Lognormal distributions BY CONSTRUCTION. A later
  model fitting a Lognormal to these data will therefore fit well, and that proves
  nothing about real losses.
* There is no hidden label, no "future incident probability" and no ML target.

Run ``python -m risksignal.data.generator --seed 42`` to regenerate the files.
"""

import argparse
import calendar
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from risksignal.data.schemas import (
    AtlasBankDataset,
    Control,
    Dependency,
    Incident,
    KriObservation,
    Process,
    ReviewStatus,
    Severity,
    System,
    Vendor,
    validate_dataset,
)
from risksignal.data.storage import DEFAULT_DATA_DIR, save_atlas_bank

DEFAULT_SEED = 42
DATA_START = date(2021, 10, 1)
DATA_END = date(2026, 9, 30)  # also the "as of" date for control review status
FOCAL_SYSTEM_ID = "PAYMENT_ENGINE_01"
REVIEW_CYCLE_DAYS = 365
DUE_WINDOW_DAYS = 60
# Scales the per-system rates below so the five-year total is roughly 300 incidents.
_INCIDENT_RATE_SCALE = 0.9

# --------------------------------------------------------------------------- reference data

_PROCESSES = [
    ("P01", "International Payments", "Cross-border payment initiation, messaging and settlement."),
    ("P02", "Domestic Payments", "Local payment initiation, clearing and settlement."),
    ("P03", "Trade Settlement", "Confirmation and settlement of securities trades."),
    ("P04", "Client Onboarding", "Identity checks and account opening for new clients."),
    ("P05", "Identity and Access Management", "Staff and customer authentication and access rights."),
    ("P06", "Fraud Monitoring", "Detection and review of suspicious transactions."),
    ("P07", "Regulatory Reporting", "Preparation and submission of regulatory reports."),
    ("P08", "Customer Account Servicing", "Account balances, statements and customer self-service."),
    ("P09", "Liquidity Management", "Monitoring and forecasting of cash positions."),
    ("P10", "Financial Crime Screening", "Sanctions and watchlist screening."),
]

_VENDORS = [
    ("V01", "NimbusCloud Hosting", "Cloud hosting and managed infrastructure."),
    ("V02", "Vertex Messaging Networks", "Interbank messaging and connectivity."),
    ("V03", "Orbital Identity Services", "Identity federation and authentication platform."),
    ("V04", "Keystone Payment Rails", "Payment network access and settlement connectivity."),
    ("V05", "Meridian Market Data", "Market and reference data feeds."),
    ("V06", "Sentinel Screening Data", "Sanctions and watchlist data provider."),
    ("V07", "Cobalt Core Systems", "Core ledger software support and maintenance."),
    ("V08", "Lumen Document Services", "Document capture and storage services."),
]

# system_id, name, description, criticality, primary process, expected incidents per year
_SYSTEMS = [
    ("PAYMENT_ENGINE_01", "Payment Engine 01", "Processes outbound international payments.", "critical", "P01", 3.0),
    ("PAYMENT_ENGINE_02", "Payment Engine 02", "Processes domestic payments.", "critical", "P02", 3.0),
    ("PAYMENT_GATEWAY_01", "Payment Gateway 01", "Entry point for payment requests from channels.", "high", "P02", 4.0),
    ("MESSAGING_HUB_01", "Messaging Hub 01", "Sends and receives interbank payment messages.", "high", "P01", 3.0),
    ("FRAUD_SCREENING_01", "Fraud Screening 01", "Scores payments for fraud indicators.", "high", "P06", 3.5),
    ("SANCTIONS_SCREENING_01", "Sanctions Screening 01", "Screens parties against watchlists.", "high", "P10", 2.5),
    ("TRADE_SETTLEMENT_01", "Trade Settlement 01", "Settles confirmed securities trades.", "critical", "P03", 3.0),
    ("TRADE_CAPTURE_01", "Trade Capture 01", "Records trades from front-office desks.", "high", "P03", 3.5),
    ("CLEARING_INTERFACE_01", "Clearing Interface 01", "Connects to external clearing houses.", "high", "P03", 2.5),
    ("ONBOARDING_PORTAL_01", "Onboarding Portal 01", "Web portal for new client applications.", "medium", "P04", 4.0),
    ("KYC_DOCUMENT_STORE_01", "KYC Document Store 01", "Stores client identity documents.", "medium", "P04", 2.5),
    ("IAM_DIRECTORY_01", "IAM Directory 01", "Central directory of identities and roles.", "critical", "P05", 3.0),
    ("SSO_GATEWAY_01", "SSO Gateway 01", "Single sign-on for internal applications.", "high", "P05", 3.5),
    ("PRIVILEGED_ACCESS_01", "Privileged Access 01", "Controls and records administrator access.", "high", "P05", 2.0),
    ("CORE_LEDGER_01", "Core Ledger 01", "Book of record for customer balances.", "critical", "P08", 3.5),
    ("CUSTOMER_PORTAL_01", "Customer Portal 01", "Online banking for customers.", "medium", "P08", 5.0),
    ("REG_REPORTING_ENGINE_01", "Regulatory Reporting Engine 01", "Builds regulatory report files.", "medium", "P07", 3.0),
    ("DATA_WAREHOUSE_01", "Data Warehouse 01", "Central analytical data store.", "medium", "P07", 3.5),
    ("LIQUIDITY_MONITOR_01", "Liquidity Monitor 01", "Tracks intraday cash positions.", "high", "P09", 2.5),
    ("CASH_FORECAST_01", "Cash Forecast 01", "Produces cash flow projections.", "low", "P09", 2.0),
]

_VENDOR_LINKS = {
    "PAYMENT_ENGINE_01": ["V04", "V02"],
    "PAYMENT_ENGINE_02": ["V04", "V01"],  # shares V04 with PAYMENT_ENGINE_01
    "PAYMENT_GATEWAY_01": ["V01"],
    "MESSAGING_HUB_01": ["V02"],
    "FRAUD_SCREENING_01": ["V05"],
    "SANCTIONS_SCREENING_01": ["V06"],
    "TRADE_SETTLEMENT_01": ["V05"],
    "TRADE_CAPTURE_01": ["V05"],
    "CLEARING_INTERFACE_01": ["V02"],
    "ONBOARDING_PORTAL_01": ["V01", "V08"],
    "KYC_DOCUMENT_STORE_01": ["V08"],
    "IAM_DIRECTORY_01": ["V03"],
    "SSO_GATEWAY_01": ["V03"],
    "PRIVILEGED_ACCESS_01": ["V03"],
    "CORE_LEDGER_01": ["V07"],
    "CUSTOMER_PORTAL_01": ["V01"],
    "DATA_WAREHOUSE_01": ["V01"],
    "LIQUIDITY_MONITOR_01": ["V05"],
}

# Processes a system supports in addition to its primary process.
_EXTRA_PROCESS_LINKS = {
    "PAYMENT_GATEWAY_01": ["P01"],
    "FRAUD_SCREENING_01": ["P01", "P02"],
    "SANCTIONS_SCREENING_01": ["P01", "P04"],
    "CORE_LEDGER_01": ["P01", "P02"],
    "IAM_DIRECTORY_01": ["P04"],
    "SSO_GATEWAY_01": ["P08"],
    "DATA_WAREHOUSE_01": ["P09"],
}

_SYSTEM_LINKS = {
    "PAYMENT_ENGINE_01": ["MESSAGING_HUB_01", "FRAUD_SCREENING_01", "SANCTIONS_SCREENING_01", "CORE_LEDGER_01", "SSO_GATEWAY_01"],
    "PAYMENT_ENGINE_02": ["PAYMENT_GATEWAY_01", "FRAUD_SCREENING_01", "CORE_LEDGER_01", "SSO_GATEWAY_01"],
    "PAYMENT_GATEWAY_01": ["SSO_GATEWAY_01"],
    "TRADE_SETTLEMENT_01": ["TRADE_CAPTURE_01", "CLEARING_INTERFACE_01", "CORE_LEDGER_01"],
    "TRADE_CAPTURE_01": ["SSO_GATEWAY_01"],
    "ONBOARDING_PORTAL_01": ["KYC_DOCUMENT_STORE_01", "IAM_DIRECTORY_01", "SANCTIONS_SCREENING_01"],
    "SSO_GATEWAY_01": ["IAM_DIRECTORY_01"],
    "PRIVILEGED_ACCESS_01": ["IAM_DIRECTORY_01"],
    "CUSTOMER_PORTAL_01": ["SSO_GATEWAY_01", "CORE_LEDGER_01"],
    "REG_REPORTING_ENGINE_01": ["DATA_WAREHOUSE_01", "CORE_LEDGER_01"],
    "LIQUIDITY_MONITOR_01": ["CORE_LEDGER_01", "CASH_FORECAST_01"],
    "CASH_FORECAST_01": ["DATA_WAREHOUSE_01"],
}

# name -> (description, control type)
_CONTROL_POOL = {
    "Change Approval Review": ("Releases require independent approval before deployment.", "preventive"),
    "Pre-Release Regression Testing": ("Regression tests must pass before a release goes live.", "preventive"),
    "Rollback Procedure Test": ("Rollback steps are rehearsed so a bad release can be reversed.", "corrective"),
    "Privileged Access Recertification": ("Administrator access rights are periodically recertified.", "preventive"),
    "Real-Time Availability Monitoring": ("Automated alerts fire when the service is unavailable.", "detective"),
    "Daily Reconciliation Check": ("Totals are reconciled against upstream and downstream records.", "detective"),
    "Backup and Restore Test": ("Backups are restored in a test environment to prove they work.", "corrective"),
    "Vendor Performance Review": ("Vendor service levels and incidents are reviewed with the vendor.", "detective"),
    "Patch Management Review": ("Security patches are tracked and applied within target times.", "preventive"),
    "Segregation of Duties Check": ("No single person can both request and approve a change.", "preventive"),
    "Incident Response Drill": ("Teams rehearse the response to a major outage.", "corrective"),
    "Capacity Threshold Alerting": ("Alerts warn when load approaches capacity limits.", "detective"),
}

# system -> list of (control name, days before DATA_END of the last review)
_FOCAL_CONTROLS = {
    "PAYMENT_ENGINE_01": [
        ("Change Approval Review", 120),
        ("Pre-Release Regression Testing", 420),  # overdue
        ("Daily Reconciliation Check", 45),
        ("Vendor Performance Review", 320),  # due soon
    ],
    "PAYMENT_ENGINE_02": [
        ("Change Approval Review", 200),
        ("Real-Time Availability Monitoring", 30),
        ("Vendor Performance Review", 350),  # due soon
    ],
}

# Number of controls per system when it differs from the default of 2 (total = 40).
_CONTROL_COUNT_OVERRIDES = {
    "PAYMENT_ENGINE_01": 4,
    "PAYMENT_ENGINE_02": 3,
    "CASH_FORECAST_01": 1,
    "TRADE_CAPTURE_01": 1,
    "CUSTOMER_PORTAL_01": 1,
}

_CATEGORY_WEIGHTS = {
    "technology_failure": 0.35,
    "process_failure": 0.20,
    "third_party_failure": 0.20,
    "human_error": 0.15,
    "cyber_event": 0.10,
}

# Illustrative Lognormal severity by category: (median loss, sigma of log-loss).
_SEVERITY_PARAMS = {
    "technology_failure": (25_000, 1.7),
    "process_failure": (12_000, 1.5),
    "third_party_failure": (30_000, 1.8),
    "human_error": (8_000, 1.6),
    "cyber_event": (60_000, 2.0),
}
_CRITICALITY_MULTIPLIER = {"low": 0.6, "medium": 1.0, "high": 1.4, "critical": 2.0}

_DEPLOYMENT_TEMPLATES = [
    "Failed deployment on {system}; release rolled back.",
    "Deployment to {system} introduced a defect found after release.",
    "Configuration drift after deployment on {system} caused errors.",
]
_DESCRIPTION_TEMPLATES = {
    "technology_failure": [
        "Application outage on {system} caused by an infrastructure fault.",
        "Performance degradation on {system} during peak processing.",
        "Database failover on {system} did not complete as expected.",
        "Message queue backlog on {system} delayed processing.",
    ],
    "process_failure": [
        "Manual reconciliation step missed for {system}.",
        "Change request for {system} implemented without full approval.",
        "Incomplete handover between operations teams affected {system}.",
        "Month-end processing for {system} ran late.",
    ],
    "third_party_failure": [
        "Service degradation at {vendor} affected {system}.",
        "{vendor} delivered a faulty data update used by {system}.",
        "Planned maintenance at {vendor} overran and impacted {system}.",
    ],
    "human_error": [
        "Incorrect manual configuration change applied to {system}.",
        "Operator submitted an erroneous batch to {system}.",
        "Wrong environment targeted during a support task on {system}.",
    ],
    "cyber_event": [
        "Phishing-related credential compromise attempt involving {system}.",
        "Denial-of-service traffic spike affected {system}.",
        "Malware detected on a host supporting {system}; contained.",
    ],
}

# Hand-written recent history of the focal system: (days before DATA_END, category, text).
_FOCAL_RECENT_INCIDENTS = [
    (310, "third_party_failure", "Service degradation at {vendor} affected outbound payments on {system}."),
    (226, "technology_failure", "Failed deployment on {system}; release rolled back after batch errors."),
    (141, "human_error", "Incorrect manual configuration change applied to routing rules on {system}."),
    (73, "technology_failure", "Deployment to {system} introduced a defect in message mapping; hotfix required."),
    (19, "third_party_failure", "{vendor} API latency spike delayed payment submissions from {system}."),
]
# The same vendor event also hit the other payment engine on the same day.
_SHARED_VENDOR_EVENT_DAYS_BEFORE_END = 310
_SHARED_VENDOR_ID = "V04"

_KRI_NAMES = [
    "failed_deployment_rate",
    "system_downtime_minutes",
    "near_miss_count",
    "control_exception_count",
    "vendor_incident_count",
]
_KRI_BASE_RANGE = {
    "failed_deployment_rate": (2.0, 6.0),  # percent of deployments
    "system_downtime_minutes": (10.0, 60.0),
    "near_miss_count": (1.0, 4.0),
    "control_exception_count": (0.5, 3.0),
    "vendor_incident_count": (0.2, 1.0),
}
# (system, kri) -> (month index where drift starts, multiplier reached at the last month)
_KRI_DRIFTS = {
    ("PAYMENT_ENGINE_01", "failed_deployment_rate"): (30, 2.2),
    ("PAYMENT_ENGINE_01", "system_downtime_minutes"): (36, 1.6),
    ("PAYMENT_ENGINE_01", "control_exception_count"): (36, 1.8),
    ("PAYMENT_ENGINE_01", "vendor_incident_count"): (48, 1.6),
    ("PAYMENT_ENGINE_02", "vendor_incident_count"): (48, 1.5),
    ("CORE_LEDGER_01", "failed_deployment_rate"): (24, 1.5),
    ("IAM_DIRECTORY_01", "system_downtime_minutes"): (12, 0.7),
}


# --------------------------------------------------------------------------- reference tables


def make_processes() -> list[Process]:
    return [Process(process_id=i, name=n, description=d) for i, n, d in _PROCESSES]


def make_vendors() -> list[Vendor]:
    return [Vendor(vendor_id=i, name=n, description=d) for i, n, d in _VENDORS]


def make_systems() -> list[System]:
    return [
        System(system_id=i, name=n, description=d, criticality=c, primary_process_id=p)
        for i, n, d, c, p, _rate in _SYSTEMS
    ]


def make_dependencies() -> list[Dependency]:
    deps: list[Dependency] = []
    for system_id, name, _d, _c, primary, _r in _SYSTEMS:
        for process_id in [primary, *_EXTRA_PROCESS_LINKS.get(system_id, [])]:
            deps.append(Dependency(source_id=system_id, source_type="system", relation="SUPPORTS",
                                   target_id=process_id, target_type="process"))
        for vendor_id in _VENDOR_LINKS.get(system_id, []):
            deps.append(Dependency(source_id=system_id, source_type="system", relation="DEPENDS_ON",
                                   target_id=vendor_id, target_type="vendor"))
        for other_id in _SYSTEM_LINKS.get(system_id, []):
            deps.append(Dependency(source_id=system_id, source_type="system", relation="DEPENDS_ON",
                                   target_id=other_id, target_type="system"))
    return deps


# --------------------------------------------------------------------------- controls


def review_status_for(last_review_date: date, as_of: date = DATA_END) -> ReviewStatus:
    """Status from the review date: overdue after one year, due in the last 60 days."""
    next_due = last_review_date + timedelta(days=REVIEW_CYCLE_DAYS)
    if as_of > next_due:
        return "overdue"
    if (next_due - as_of).days <= DUE_WINDOW_DAYS:
        return "due"
    return "current"


def _vendors_by_system(dependencies: list[Dependency]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for dep in dependencies:
        if dep.relation == "DEPENDS_ON" and dep.target_type == "vendor":
            result[dep.source_id].append(dep.target_id)
    return result


def _control_plan(
    rng: np.random.Generator, system_id: str, has_vendor: bool
) -> list[tuple[str, date]]:
    """List of (control name, last review date) for one system."""
    if system_id in _FOCAL_CONTROLS:
        return [(name, DATA_END - timedelta(days=days)) for name, days in _FOCAL_CONTROLS[system_id]]
    names = [n for n in _CONTROL_POOL if has_vendor or n != "Vendor Performance Review"]
    count = _CONTROL_COUNT_OVERRIDES.get(system_id, 2)
    chosen = rng.choice(len(names), size=count, replace=False)
    offsets = rng.integers(10, 441, size=count)
    return [(names[i], DATA_END - timedelta(days=int(o))) for i, o in zip(chosen, offsets)]


def make_controls(
    rng: np.random.Generator, systems: list[System], dependencies: list[Dependency]
) -> list[Control]:
    vendors_of = _vendors_by_system(dependencies)
    controls: list[Control] = []
    for system in systems:
        plan = _control_plan(rng, system.system_id, bool(vendors_of[system.system_id]))
        for name, last_review in plan:
            description, control_type = _CONTROL_POOL[name]
            controls.append(Control(
                control_id=f"C{len(controls) + 1:03d}",
                name=name,
                description=f"{description} Applies to {system.name}.",
                control_type=control_type,
                system_id=system.system_id,
                last_review_date=last_review,
                review_status=review_status_for(last_review),
            ))
    return controls


# --------------------------------------------------------------------------- incidents


def severity_for_loss(loss: float) -> Severity:
    """Severity label from the loss size (illustrative thresholds)."""
    if loss < 25_000:
        return "low"
    if loss < 250_000:
        return "medium"
    if loss < 2_500_000:
        return "high"
    return "critical"


def _draw_loss(rng: np.random.Generator, category: str, criticality: str) -> float:
    median, sigma = _SEVERITY_PARAMS[category]
    mu = math.log(median * _CRITICALITY_MULTIPLIER[criticality])
    return float(max(1, round(rng.lognormal(mu, sigma))))


def _draw_category(rng: np.random.Generator, has_vendor: bool) -> str:
    names = [c for c in _CATEGORY_WEIGHTS if has_vendor or c != "third_party_failure"]
    weights = np.array([_CATEGORY_WEIGHTS[c] for c in names])
    return names[int(rng.choice(len(names), p=weights / weights.sum()))]


def _draw_description(
    rng: np.random.Generator, category: str, system_name: str, vendor_names: list[str]
) -> str:
    if category == "technology_failure" and rng.random() < 0.35:
        templates = _DEPLOYMENT_TEMPLATES
    else:
        templates = _DESCRIPTION_TEMPLATES[category]
    vendor = vendor_names[int(rng.integers(len(vendor_names)))] if vendor_names else ""
    return templates[int(rng.integers(len(templates)))].format(system=system_name, vendor=vendor)


def _random_incidents(
    rng: np.random.Generator, system: System, rate: float, vendor_names: list[str]
) -> list[tuple[date, str, str, str, float]]:
    """Poisson number of incidents at uniformly random dates in the system's history window."""
    # The focal system's last 12 months are hand-written, so random history stops before.
    end = DATA_END - timedelta(days=365) if system.system_id == FOCAL_SYSTEM_ID else DATA_END
    span_days = (end - DATA_START).days
    count = int(rng.poisson(rate * span_days / 365.25))
    rows = []
    for offset in rng.integers(0, span_days + 1, size=count):
        category = _draw_category(rng, bool(vendor_names))
        description = _draw_description(rng, category, system.name, vendor_names)
        loss = _draw_loss(rng, category, system.criticality)
        rows.append((DATA_START + timedelta(days=int(offset)), system.system_id, category, description, loss))
    return rows


def _focal_incidents(
    rng: np.random.Generator, systems: dict[str, System], vendor_name: str
) -> list[tuple[date, str, str, str, float]]:
    focal = systems[FOCAL_SYSTEM_ID]
    rows = []
    for days, category, text in _FOCAL_RECENT_INCIDENTS:
        description = text.format(system=focal.name, vendor=vendor_name)
        loss = _draw_loss(rng, category, focal.criticality)
        rows.append((DATA_END - timedelta(days=days), focal.system_id, category, description, loss))
    other = systems["PAYMENT_ENGINE_02"]
    description = f"Service degradation at {vendor_name} affected payments on {other.name}."
    loss = _draw_loss(rng, "third_party_failure", other.criticality)
    day = DATA_END - timedelta(days=_SHARED_VENDOR_EVENT_DAYS_BEFORE_END)
    rows.append((day, other.system_id, "third_party_failure", description, loss))
    return rows


def make_incidents(
    rng: np.random.Generator,
    systems: list[System],
    vendors: list[Vendor],
    dependencies: list[Dependency],
) -> list[Incident]:
    vendor_name = {v.vendor_id: v.name for v in vendors}
    vendors_of = _vendors_by_system(dependencies)
    rates = {row[0]: row[5] * _INCIDENT_RATE_SCALE for row in _SYSTEMS}
    rows: list[tuple[date, str, str, str, float]] = []
    for system in systems:
        names = [vendor_name[v] for v in vendors_of[system.system_id]]
        rows += _random_incidents(rng, system, rates[system.system_id], names)
    rows += _focal_incidents(rng, {s.system_id: s for s in systems}, vendor_name[_SHARED_VENDOR_ID])
    rows.sort(key=lambda r: (r[0], r[1], r[3]))
    return [
        Incident(
            incident_id=f"INC{n:04d}", date=day, system_id=system_id, category=category,
            description=description, financial_loss=loss, severity=severity_for_loss(loss),
        )
        for n, (day, system_id, category, description, loss) in enumerate(rows, start=1)
    ]


# --------------------------------------------------------------------------- KRIs


def _month_ends() -> list[date]:
    """Month-end dates from DATA_START's month to DATA_END's month (60 months)."""
    ends = []
    year, month = DATA_START.year, DATA_START.month
    while (year, month) <= (DATA_END.year, DATA_END.month):
        ends.append(date(year, month, calendar.monthrange(year, month)[1]))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return ends


def _trend(month_index: int, n_months: int, drift: tuple[int, float] | None) -> float:
    """Multiplier that is 1 before the drift starts, then moves linearly to the end value."""
    if drift is None:
        return 1.0
    start, end_multiplier = drift
    if month_index <= start:
        return 1.0
    return 1.0 + (end_multiplier - 1.0) * (month_index - start) / (n_months - 1 - start)


def _draw_kri_value(rng: np.random.Generator, kri: str, level: float) -> float:
    if kri == "failed_deployment_rate":
        return round(float(level * rng.lognormal(0.0, 0.25)), 2)
    if kri == "system_downtime_minutes":
        return round(float(rng.gamma(2.0, level / 2.0)), 1)
    return float(rng.poisson(level))


def make_kri_observations(
    rng: np.random.Generator, systems: list[System], dependencies: list[Dependency]
) -> list[KriObservation]:
    vendors_of = _vendors_by_system(dependencies)
    months = _month_ends()
    rows: list[KriObservation] = []
    for system in systems:
        for kri in _KRI_NAMES:
            if kri == "vendor_incident_count" and not vendors_of[system.system_id]:
                continue
            low, high = _KRI_BASE_RANGE[kri]
            base = float(rng.uniform(low, high))
            drift = _KRI_DRIFTS.get((system.system_id, kri))
            for index, month_end in enumerate(months):
                level = base * _trend(index, len(months), drift)
                rows.append(KriObservation(
                    date=month_end, system_id=system.system_id, kri_name=kri,
                    value=_draw_kri_value(rng, kri, level),
                ))
    return rows


# --------------------------------------------------------------------------- assembly


def generate_atlas_bank(seed: int = DEFAULT_SEED) -> AtlasBankDataset:
    """Build the full synthetic dataset. The same seed always gives the same dataset."""
    rng = np.random.default_rng(seed)
    processes = make_processes()
    vendors = make_vendors()
    systems = make_systems()
    dependencies = make_dependencies()
    dataset = AtlasBankDataset(
        systems=systems,
        processes=processes,
        vendors=vendors,
        controls=make_controls(rng, systems, dependencies),
        incidents=make_incidents(rng, systems, vendors, dependencies),
        kri_observations=make_kri_observations(rng, systems, dependencies),
        dependencies=dependencies,
    )
    validate_dataset(dataset, max_date=DATA_END)
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic Atlas Bank dataset.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed (default: 42)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DATA_DIR, help="where to write CSV and SQLite files")
    args = parser.parse_args()
    dataset = generate_atlas_bank(args.seed)
    db_path = save_atlas_bank(dataset, args.output_dir)
    print(f"Synthetic Atlas Bank generated with seed {args.seed}.")
    print(f"CSV files and database written to {args.output_dir}")
    for table in ("systems", "processes", "vendors", "controls", "incidents", "kri_observations", "dependencies"):
        print(f"  {table}: {len(getattr(dataset, table))} rows")
    print(f"SQLite database: {db_path}")
    print("All data are synthetic and illustrative.")


if __name__ == "__main__":
    main()
