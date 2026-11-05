"""Transparent monitoring and interval calculations, independent of data access."""
import math
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone


def instant(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    return parsed.astimezone(timezone.utc)


def stamp(value):
    return instant(value).isoformat(timespec="microseconds")


def duration(start, end):
    return max(0.0, (instant(end) - instant(start)).total_seconds() / 3600)


def overlaps(start, end, other_start, other_end):
    return instant(start) < instant(other_end) and instant(other_start) < instant(end)


def uncovered_intervals(start, end, intervals):
    """Subtract the union of approved intervals; exact-end validity covers the shift."""
    start, end = instant(start), instant(end)
    clipped = sorted((max(start, instant(a)), min(end, instant(b))) for a, b in intervals
                     if overlaps(start, end, a, b))
    cursor, gaps = start, []
    for left, right in clipped:
        if left > cursor:
            gaps.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < end:
        gaps.append((cursor, end))
    return gaps


@dataclass(frozen=True)
class RuleConfig:
    baseline_start: str = "2026-08-07"
    horizon_hours: int = 72
    history_days: int = 90
    baseline_days: int = 56
    ewma_lambda: float = 0.25
    sigma_floor: float = 0.003
    minimum_share_increase: float = 0.015
    consecutive_breaches: int = 3
    quality_window_days: int = 21
    quality_reporting_lag_days: int = 2
    quality_min_reports: int = 5
    quality_rate_ratio: float = 1.25

    def to_dict(self):
        return asdict(self)


def overtime_drift(points, config=RuleConfig()):
    """Frozen-baseline weekday-adjusted EWMA; no forward-looking baseline fitting."""
    ordered = sorted(points, key=lambda p: p["date"])
    valid = [p for p in ordered if p.get("share") is not None]
    result = {"method": "weekday_adjusted_EWMA", "status": "insufficient_history",
              "detected": False, "first_breach_work_date": None, "series": ordered,
              "baseline": None, "minimum_share_increase": config.minimum_share_increase}
    if len(ordered) <= config.baseline_days or len(valid) != len(ordered):
        return result
    dates = [datetime.fromisoformat(p["date"]).date() for p in ordered]
    if any((b - a).days != 1 for a, b in zip(dates, dates[1:])):
        result["status"] = "incomplete_history"
        return result
    baseline = ordered[:config.baseline_days]
    by_weekday = {weekday: [p["share"] for p in baseline
                           if datetime.fromisoformat(p["date"]).weekday() == weekday] for weekday in range(7)}
    means = {weekday: statistics.mean(values) for weekday, values in by_weekday.items() if values}
    if len(means) != 7:
        return result
    residuals = [p["share"] - means[datetime.fromisoformat(p["date"]).weekday()] for p in baseline]
    sigma = max(statistics.pstdev(residuals), config.sigma_floor)
    result["baseline"] = {"start": baseline[0]["date"], "end": baseline[-1]["date"],
                          "mean_share": statistics.mean(p["share"] for p in baseline),
                          "residual_sigma": sigma, "weekday_means": means}
    ewma, breaches = 0.0, 0
    monitoring = []
    for t, p in enumerate(ordered[config.baseline_days:], start=1):
        mean = means[datetime.fromisoformat(p["date"]).weekday()]
        residual = p["share"] - mean
        ewma = config.ewma_lambda * residual / sigma + (1 - config.ewma_lambda) * ewma
        variance = config.ewma_lambda / (2 - config.ewma_lambda) * (1 - (1 - config.ewma_lambda) ** (2 * t))
        upper = 3 * math.sqrt(variance)
        breaches = breaches + 1 if ewma > upper and residual >= config.minimum_share_increase else 0
        if breaches >= config.consecutive_breaches and result["first_breach_work_date"] is None:
            result["first_breach_work_date"] = p["date"]
        monitoring.append({"date": p["date"], "share": p["share"], "ewma": ewma,
                           "upper_limit": upper, "breach_streak": breaches,
                           "point_anomaly": residual > max(3 * sigma, config.minimum_share_increase)})
    # A past breach remains visible, while current monitoring distinguishes recovery.
    result.update(status="drift" if breaches >= config.consecutive_breaches else "stable",
                  detected=breaches >= config.consecutive_breaches, monitoring=monitoring)
    return result


def quality_review(baseline_reports, current_reports, baseline_days, current_days,
                   reporting_campaign=False, config=RuleConfig()):
    result = {"baseline_reports": baseline_reports, "current_reports": current_reports,
              "baseline_patient_days": baseline_days, "current_patient_days": current_days,
              "baseline_rate_per_1000": None, "current_rate_per_1000": None,
              "rate_ratio": None, "review_required": False, "causal_claim_permitted": False,
              "status": "insufficient_denominator"}
    if baseline_days is None or current_days is None or baseline_days <= 0 or current_days <= 0:
        return result
    base_rate = baseline_reports / baseline_days * 1000
    current_rate = current_reports / current_days * 1000
    result.update(baseline_rate_per_1000=base_rate, current_rate_per_1000=current_rate,
                  rate_ratio=current_rate / base_rate if base_rate > 0 else None)
    if reporting_campaign:
        result["status"] = "reporting_context_changed"
    elif min(baseline_reports, current_reports) < config.quality_min_reports:
        result["status"] = "insufficient_report_volume"
    elif result["rate_ratio"] >= config.quality_rate_ratio:
        result.update(status="report_rate_review", review_required=True)
    else:
        result["status"] = "stable_report_rate"
    return result


def readiness_priority(rn_gap=False, provider_exposure=False, drift=False, access=False,
                       quality=False, issues=False, unverified_gap=False):
    primary = rn_gap or provider_exposure
    additional = (rn_gap and provider_exposure) or drift or access or quality
    if primary and additional:
        return "high"
    if primary or drift or access:
        return "medium"
    if quality:
        return "informational"
    if issues or unverified_gap:
        return "review_required"
    return "none"
