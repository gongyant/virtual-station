from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd


GRAVITY_M_S2 = 9.80665


@dataclass(frozen=True)
class ReachHydraulics:
    """Static information required by the steady reach energy balance."""

    length_m: float
    manning_n_upstream: float
    manning_n_downstream: float
    velocity_head_coefficient: float = 1.0
    minor_loss_coefficient: float = 0.0
    dem_bed_slope_m_per_m: float | None = None

    def __post_init__(self) -> None:
        if self.length_m <= 0:
            raise ValueError("length_m must be positive")
        if self.manning_n_upstream <= 0 or self.manning_n_downstream <= 0:
            raise ValueError("Manning roughness must be positive")
        if self.velocity_head_coefficient <= 0:
            raise ValueError("velocity_head_coefficient must be positive")
        if self.minor_loss_coefficient < 0:
            raise ValueError("minor_loss_coefficient cannot be negative")
        if self.dem_bed_slope_m_per_m is not None:
            if not np.isfinite(self.dem_bed_slope_m_per_m) or self.dem_bed_slope_m_per_m <= 0:
                raise ValueError("dem_bed_slope_m_per_m must be finite and positive")


def approximate_section_geometry(
    width_m: float,
    mean_depth_m: float,
    area_m2: float | None = None,
    side_slope_h_to_v: float = 2.0,
) -> dict[str, float]:
    """Return a transparent trapezoidal approximation for a measured section.

    When a measured area is supplied it remains authoritative. The trapezoid is
    used only to approximate wetted perimeter, which is usually absent from
    current-year discharge-measurement tables.
    """

    values = np.asarray([width_m, mean_depth_m, side_slope_h_to_v], dtype=float)
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("width, depth, and side slope must be finite and positive")
    bottom_width = float(width_m - 2.0 * side_slope_h_to_v * mean_depth_m)
    if bottom_width <= 0:
        raise ValueError("section geometry implies a nonpositive bottom width")
    trapezoid_area = float(mean_depth_m * (width_m + bottom_width) / 2.0)
    if area_m2 is None:
        area = trapezoid_area
        area_source = "trapezoidal_approximation"
    else:
        area = float(area_m2)
        if not np.isfinite(area) or area <= 0:
            raise ValueError("area_m2 must be finite and positive when supplied")
        area_source = "measured"
    wetted_perimeter = float(
        bottom_width
        + 2.0 * mean_depth_m * np.sqrt(1.0 + side_slope_h_to_v**2)
    )
    hydraulic_radius = area / wetted_perimeter
    hydraulic_depth = area / width_m
    return {
        "area_m2": area,
        "area_source": area_source,
        "bottom_width_m": bottom_width,
        "wetted_perimeter_m": wetted_perimeter,
        "hydraulic_radius_m": hydraulic_radius,
        "hydraulic_depth_m": hydraulic_depth,
    }


def _conveyance(area_m2: float, hydraulic_radius_m: float, manning_n: float) -> float:
    return float(area_m2 * hydraulic_radius_m ** (2.0 / 3.0) / manning_n)


def steady_reach_discharge(
    upstream: Mapping[str, float],
    downstream: Mapping[str, float],
    reach: ReachHydraulics,
) -> dict[str, float | bool | str]:
    """Solve one steady-flow scenario from continuity and the energy equation.

    The same discharge passes both sections (no unobserved lateral inflow or
    storage change). Friction loss uses the average of the two Manning friction
    slopes. The result is rejected when the supplied water-surface elevations
    cannot drive a physically admissible downstream flow.
    """

    required = ("water_surface_elevation_m", "area_m2", "hydraulic_radius_m")
    for label, section in (("upstream", upstream), ("downstream", downstream)):
        missing = [name for name in required if name not in section]
        if missing:
            raise KeyError(f"{label} section missing fields: {missing}")
        vals = np.asarray([section[name] for name in required], dtype=float)
        if not np.isfinite(vals).all() or np.any(vals[1:] <= 0):
            raise ValueError(f"{label} section contains invalid hydraulic values")

    head_drop = float(
        upstream["water_surface_elevation_m"]
        - downstream["water_surface_elevation_m"]
    )
    if head_drop <= 0:
        return {
            "discharge_m3s": float("nan"),
            "velocity_upstream_ms": float("nan"),
            "velocity_downstream_ms": float("nan"),
            "head_drop_m": head_drop,
            "friction_head_loss_m": float("nan"),
            "energy_residual_m": float("nan"),
            "mass_residual_m3s": float("nan"),
            "physics_valid": False,
            "rejection_reason": "nonpositive_water_surface_head_drop",
        }

    area_up = float(upstream["area_m2"])
    area_down = float(downstream["area_m2"])
    conveyance_up = _conveyance(
        area_up, float(upstream["hydraulic_radius_m"]), reach.manning_n_upstream
    )
    conveyance_down = _conveyance(
        area_down,
        float(downstream["hydraulic_radius_m"]),
        reach.manning_n_downstream,
    )
    alpha = reach.velocity_head_coefficient
    friction_coefficient = 0.5 * reach.length_m * (
        conveyance_up ** -2 + conveyance_down ** -2
    )
    velocity_head_coefficient = alpha / (2.0 * GRAVITY_M_S2) * (
        area_down ** -2 - area_up ** -2
    )
    minor_loss = reach.minor_loss_coefficient / (2.0 * GRAVITY_M_S2 * area_down**2)
    denominator = friction_coefficient + velocity_head_coefficient + minor_loss
    if not np.isfinite(denominator) or denominator <= 0:
        return {
            "discharge_m3s": float("nan"),
            "velocity_upstream_ms": float("nan"),
            "velocity_downstream_ms": float("nan"),
            "head_drop_m": head_drop,
            "friction_head_loss_m": float("nan"),
            "energy_residual_m": float("nan"),
            "mass_residual_m3s": float("nan"),
            "physics_valid": False,
            "rejection_reason": "nonpositive_energy_equation_denominator",
        }

    discharge = float(np.sqrt(head_drop / denominator))
    velocity_up = discharge / area_up
    velocity_down = discharge / area_down
    friction_loss = friction_coefficient * discharge**2
    velocity_head_change = velocity_head_coefficient * discharge**2
    minor_head_loss = minor_loss * discharge**2
    energy_residual = head_drop - friction_loss - velocity_head_change - minor_head_loss
    return {
        "discharge_m3s": discharge,
        "velocity_upstream_ms": velocity_up,
        "velocity_downstream_ms": velocity_down,
        "head_drop_m": head_drop,
        "friction_head_loss_m": friction_loss,
        "energy_residual_m": energy_residual,
        "mass_residual_m3s": 0.0,
        "physics_valid": bool(discharge >= 0 and abs(energy_residual) <= 1e-8),
        "rejection_reason": "",
    }


def _prepare_states(
    frame: pd.DataFrame,
    prefix: str,
    default_datum_m: float | None,
    side_slope_h_to_v: float,
) -> pd.DataFrame:
    aliases = {
        "stage_m": ["stage_m", "stage"],
        "width_m": ["width_m", "surface_width_m"],
        "mean_depth_m": ["mean_depth_m", "depth_m"],
        "area_m2": ["area_m2", "cross_section_area_m2"],
    }
    selected: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        match = next((name for name in candidates if name in frame), None)
        if match is None and canonical != "area_m2":
            raise KeyError(f"state table requires one of {candidates}")
        if match is not None:
            selected[canonical] = match
    states = pd.DataFrame({name: pd.to_numeric(frame[source], errors="coerce") for name, source in selected.items()})
    if "area_m2" not in states:
        states["area_m2"] = np.nan
    if "water_surface_elevation_m" in frame:
        states["water_surface_elevation_m"] = pd.to_numeric(
            frame["water_surface_elevation_m"], errors="coerce"
        )
        states["elevation_source"] = "supplied_common_vertical_datum"
    else:
        datum = (
            pd.to_numeric(frame["stage_datum_m"], errors="coerce")
            if "stage_datum_m" in frame
            else default_datum_m
        )
        if datum is None:
            raise ValueError(
                "water_surface_elevation_m or a confirmed stage datum is required; "
                "relative gauge stages from different stations cannot be subtracted"
            )
        states["water_surface_elevation_m"] = states["stage_m"] + datum
        states["elevation_source"] = "stage_plus_confirmed_datum"
    if "state_id" in frame:
        states["state_id"] = frame["state_id"].astype(str).to_numpy()
    elif "measurement_id" in frame:
        states["state_id"] = frame["measurement_id"].astype(str).to_numpy()
    else:
        states["state_id"] = [f"{prefix}_{i:04d}" for i in range(len(states))]

    geometry_rows = []
    for row in states.itertuples(index=False):
        try:
            geometry_rows.append(
                approximate_section_geometry(
                    row.width_m,
                    row.mean_depth_m,
                    None if not np.isfinite(row.area_m2) else row.area_m2,
                    side_slope_h_to_v,
                )
            )
        except ValueError:
            geometry_rows.append(
                {
                    "area_m2": np.nan,
                    "area_source": "invalid",
                    "bottom_width_m": np.nan,
                    "wetted_perimeter_m": np.nan,
                    "hydraulic_radius_m": np.nan,
                    "hydraulic_depth_m": np.nan,
                }
            )
    geometry = pd.DataFrame(geometry_rows, index=states.index)
    states["area_m2"] = geometry["area_m2"]
    for column in geometry.columns.drop("area_m2"):
        states[column] = geometry[column]
    return states.add_prefix(f"{prefix}_")


def build_hydraulic_scenario_library(
    upstream_states: pd.DataFrame,
    downstream_states: pd.DataFrame,
    reach: ReachHydraulics,
    upstream_stage_datum_m: float | None = None,
    downstream_stage_datum_m: float | None = None,
    side_slope_h_to_v: float = 2.0,
) -> pd.DataFrame:
    """Enumerate every upstream/downstream state pair and solve it physically."""

    up = _prepare_states(
        upstream_states, "upstream", upstream_stage_datum_m, side_slope_h_to_v
    )
    down = _prepare_states(
        downstream_states, "downstream", downstream_stage_datum_m, side_slope_h_to_v
    )
    pairs = up.merge(down, how="cross")
    solved: list[dict[str, float | bool | str]] = []
    for row in pairs.itertuples(index=False):
        upstream = {
            "water_surface_elevation_m": row.upstream_water_surface_elevation_m,
            "area_m2": row.upstream_area_m2,
            "hydraulic_radius_m": row.upstream_hydraulic_radius_m,
        }
        downstream = {
            "water_surface_elevation_m": row.downstream_water_surface_elevation_m,
            "area_m2": row.downstream_area_m2,
            "hydraulic_radius_m": row.downstream_hydraulic_radius_m,
        }
        try:
            result = steady_reach_discharge(upstream, downstream, reach)
        except ValueError:
            result = {
                "discharge_m3s": np.nan,
                "velocity_upstream_ms": np.nan,
                "velocity_downstream_ms": np.nan,
                "head_drop_m": np.nan,
                "friction_head_loss_m": np.nan,
                "energy_residual_m": np.nan,
                "mass_residual_m3s": np.nan,
                "physics_valid": False,
                "rejection_reason": "invalid_section_geometry",
            }
        solved.append(result)
    result = pd.concat([pairs.reset_index(drop=True), pd.DataFrame(solved)], axis=1)
    result.insert(0, "scenario_id", [f"scenario_{i:06d}" for i in range(len(result))])
    result["reach_length_m"] = reach.length_m
    result["manning_n_upstream"] = reach.manning_n_upstream
    result["manning_n_downstream"] = reach.manning_n_downstream
    result["water_surface_slope_m_per_m"] = result.head_drop_m / reach.length_m
    result["dem_bed_slope_m_per_m"] = reach.dem_bed_slope_m_per_m
    if reach.dem_bed_slope_m_per_m is None:
        result["water_surface_to_dem_slope_ratio"] = np.nan
    else:
        result["water_surface_to_dem_slope_ratio"] = (
            result.water_surface_slope_m_per_m / reach.dem_bed_slope_m_per_m
        )
    result["froude_upstream"] = result.velocity_upstream_ms / np.sqrt(
        GRAVITY_M_S2 * result.upstream_hydraulic_depth_m
    )
    result["froude_downstream"] = result.velocity_downstream_ms / np.sqrt(
        GRAVITY_M_S2 * result.downstream_hydraulic_depth_m
    )
    result["subcritical_both_sections"] = (
        result.froude_upstream.lt(1.0) & result.froude_downstream.lt(1.0)
    )
    return result


class HydraulicScenarioInterpolator:
    """Domain-gated inverse-distance lookup over an enumerated scenario table."""

    DEFAULT_FEATURES = (
        "upstream_stage_m",
        "downstream_stage_m",
        "upstream_width_m",
        "downstream_width_m",
        "upstream_mean_depth_m",
        "downstream_mean_depth_m",
    )

    def __init__(
        self,
        scenarios: pd.DataFrame,
        feature_names: Iterable[str] | None = None,
        neighbors: int = 8,
        power: float = 2.0,
    ) -> None:
        self.feature_names = tuple(feature_names or self.DEFAULT_FEATURES)
        if neighbors <= 0 or power <= 0:
            raise ValueError("neighbors and power must be positive")
        required = set(self.feature_names) | {"discharge_m3s", "physics_valid"}
        missing = required - set(scenarios)
        if missing:
            raise KeyError(f"scenario table missing fields: {sorted(missing)}")
        valid = scenarios.loc[scenarios.physics_valid.astype(bool)].copy()
        valid = valid.dropna(subset=[*self.feature_names, "discharge_m3s"])
        if valid.empty:
            raise ValueError("scenario table has no valid hydraulic scenarios")
        self.scenarios = valid.reset_index(drop=True)
        self.neighbors = min(int(neighbors), len(valid))
        self.power = float(power)
        self.minimum = self.scenarios.loc[:, self.feature_names].min().to_numpy(float)
        self.maximum = self.scenarios.loc[:, self.feature_names].max().to_numpy(float)
        span = self.maximum - self.minimum
        self.scale = np.where(span > 0, span, 1.0)
        self.features = self.scenarios.loc[:, self.feature_names].to_numpy(float)

    def query(self, state: Mapping[str, float]) -> dict[str, float | str | bool]:
        missing = [name for name in self.feature_names if name not in state]
        if missing:
            raise KeyError(f"query missing fields: {missing}")
        point = np.asarray([state[name] for name in self.feature_names], dtype=float)
        if not np.isfinite(point).all():
            raise ValueError("query features must be finite")
        outside = (point < self.minimum) | (point > self.maximum)
        if outside.any():
            return {
                "discharge_m3s": float("nan"),
                "velocity_upstream_ms": float("nan"),
                "velocity_downstream_ms": float("nan"),
                "lookup_status": "outside_scenario_domain",
                "inside_scenario_domain": False,
                "nearest_normalized_distance": float("nan"),
            }

        distances = np.linalg.norm((self.features - point) / self.scale, axis=1)
        nearest = np.argpartition(distances, self.neighbors - 1)[: self.neighbors]
        nearest_distances = distances[nearest]
        if np.any(nearest_distances <= 1e-12):
            weights = np.zeros_like(nearest_distances)
            weights[np.argmin(nearest_distances)] = 1.0
            status = "exact_scenario_match"
        else:
            weights = nearest_distances ** -self.power
            weights /= weights.sum()
            status = "interpolated_within_scenario_domain"
        rows = self.scenarios.iloc[nearest]
        discharge = float(np.dot(weights, rows.discharge_m3s.to_numpy(float)))
        area_up = float(state.get("upstream_area_m2", state["upstream_width_m"] * state["upstream_mean_depth_m"]))
        area_down = float(state.get("downstream_area_m2", state["downstream_width_m"] * state["downstream_mean_depth_m"]))
        if area_up <= 0 or area_down <= 0:
            raise ValueError("query section areas must be positive")
        return {
            "discharge_m3s": discharge,
            "velocity_upstream_ms": discharge / area_up,
            "velocity_downstream_ms": discharge / area_down,
            "lookup_status": status,
            "inside_scenario_domain": True,
            "nearest_normalized_distance": float(nearest_distances.min()),
        }


def add_hydraulic_lookup_features(
    frame: pd.DataFrame,
    interpolator: HydraulicScenarioInterpolator,
    feature_column_map: Mapping[str, str] | None = None,
    prefix: str = "hydraulic_",
) -> pd.DataFrame:
    """Attach model-ready physical-reference features to a time-series table.

    Missing inputs and out-of-domain states remain unavailable instead of being
    silently filled. The resulting ``<prefix>reference_q_m3s`` column can be
    selected as ``physics_reference_feature`` by the existing training pipeline.
    """

    mapping = {
        name: (feature_column_map or {}).get(name, name)
        for name in interpolator.feature_names
    }
    missing = [column for column in mapping.values() if column not in frame]
    if missing:
        raise KeyError(f"time-series table missing hydraulic input columns: {missing}")
    output = frame.copy()
    records: list[dict[str, float | str | bool]] = []
    for row in output.itertuples(index=False, name=None):
        row_values = dict(zip(output.columns, row))
        state = {feature: row_values[column] for feature, column in mapping.items()}
        if not np.isfinite(np.asarray(list(state.values()), dtype=float)).all():
            records.append(
                {
                    "discharge_m3s": np.nan,
                    "velocity_upstream_ms": np.nan,
                    "velocity_downstream_ms": np.nan,
                    "lookup_status": "missing_hydraulic_inputs",
                    "inside_scenario_domain": False,
                    "nearest_normalized_distance": np.nan,
                }
            )
            continue
        records.append(interpolator.query(state))
    lookup = pd.DataFrame(records, index=output.index)
    rename = {
        "discharge_m3s": f"{prefix}reference_q_m3s",
        "velocity_upstream_ms": f"{prefix}velocity_upstream_ms",
        "velocity_downstream_ms": f"{prefix}velocity_downstream_ms",
        "lookup_status": f"{prefix}lookup_status",
        "inside_scenario_domain": f"{prefix}reference_available",
        "nearest_normalized_distance": f"{prefix}lookup_distance",
    }
    return pd.concat([output, lookup.rename(columns=rename)], axis=1)
