from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d12a_support_audit"
D11 = ROOT / "outputs/diagnosis_2005_snapshot/stage_d11_geometry_cross_validation"
D11_PROTOCOL = D11 / "protocol_frozen.json"
D11_RESULT = D11 / "result.json"
D11_PREDICTIONS = D11 / "outer_month_predictions.csv"
MEASUREMENTS = (
    ROOT
    / "outputs/diagnosis_2005_snapshot/stage_d4b/discharge_measurements_2011_canonical.csv"
)
DAILY_STAGE = (
    ROOT
    / "outputs/diagnosis_2005_snapshot/stage_d10_byblk_stage/daily_stage_byblk_2011_reviewed.csv"
)
SECTION_POINTS = (
    ROOT
    / "outputs/diagnosis_2005_snapshot/stage_d3/cross_section_points_2011_reviewed.csv"
)

EXPECTED_D11_HASHES = {
    "protocol_frozen.json": "a79d51b293718d027caf2b697f3d1f0ddc69b8686196b842c157e02529a8e296",
    "result.json": "563ca32744f4121705bae40c0d53d26a30bad6f8431ab055ba1f1ccb1436e599",
    "outer_month_predictions.csv": "b6f2a0ebc40363f6e9f3eb4a5f995e3fa05dc6d4863fe4bd1ddd6bfa5539a73d",
}
OPEN_MONTHS = frozenset(range(4, 11))
SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx", ".txt", ".json", ".md"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assign_regime(month: int) -> str:
    return "open_water" if int(month) in OPEN_MONTHS else "cold_season"


def assert_d11_immutable() -> None:
    for name, expected in EXPECTED_D11_HASHES.items():
        actual = sha256(D11 / name)
        if actual != expected:
            raise RuntimeError(f"D11 immutable input changed: {name}: {actual}")
    result = json.loads(D11_RESULT.read_text(encoding="utf-8"))
    if result["gate_passed"] is not False:
        raise RuntimeError("D11 gate must remain false")
    if result["common_support_rows"] != 12 or result["measurement_rows"] != 24:
        raise RuntimeError("D11 common support must remain 12/24")


def base_measurements() -> pd.DataFrame:
    data = pd.read_csv(MEASUREMENTS, dtype={"station_id": str}, parse_dates=["date"])
    data.station_id = data.station_id.str.zfill(8)
    data = data.loc[data.station_id.eq("00705600")].copy()
    data["year"] = data.date.dt.year
    data["month"] = data.date.dt.month
    data["regime"] = data.month.map(assign_regime)
    return data


def inventory_row(**kwargs: object) -> dict[str, object]:
    row = {
        "source_path": "",
        "structured_source_path": "",
        "record_type": "",
        "station_id": "",
        "station_name": "",
        "station_id_evidence": "",
        "date": "",
        "year": np.nan,
        "month": np.nan,
        "stage_m": np.nan,
        "area_m2": np.nan,
        "width_m": np.nan,
        "mean_depth_m": np.nan,
        "raw_water_level_value": np.nan,
        "raw_water_level_unit": "",
        "gauge_datum_information": "",
        "cross_section_information": "",
        "unit_information": "",
        "bed_or_section_change_information": "",
        "quality_status": "unverified",
        "mergeable_with_2011": False,
        "verified_mergeable": False,
        "auxiliary_geometry_candidate": False,
        "reason": "",
    }
    row.update(kwargs)
    return row


def build_measurement_inventory() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    base = base_measurements()
    for record in base.itertuples(index=False):
        rows.append(
            inventory_row(
                source_path="data/teacher_raw/Doc1.docx#embedded_image_order_022",
                structured_source_path=str(MEASUREMENTS.relative_to(ROOT)),
                record_type="discharge_measurement_geometry_d11_baseline",
                station_id="00705600",
                station_name="巴音布鲁克",
                station_id_evidence="测流成果表和测站映射均明确为00705600",
                date=record.date.strftime("%Y-%m-%d"),
                year=record.year,
                month=record.month,
                stage_m=record.stage_m,
                area_m2=record.area_m2,
                width_m=record.width_m,
                mean_depth_m=record.mean_depth_m,
                gauge_datum_information=(
                    "测站元数据注明表内水位+2435.565 m=黄海基面；D11使用表内相对水位"
                ),
                cross_section_information="测流断面：基下3 m；来自同一巴音布鲁克测流成果表",
                unit_information="stage m; area m2; width m; mean depth m",
                bed_or_section_change_information="2011表内未提供逐次河床变迁判定",
                quality_status="verified_existing_d11_baseline",
                mergeable_with_2011=True,
                verified_mergeable=True,
                reason="D11原24条测试记录；不是额外辅助资料",
            )
        )

    stage = pd.read_csv(DAILY_STAGE, dtype={"station_id": str}, parse_dates=["date"])
    for record in stage.itertuples(index=False):
        rows.append(
            inventory_row(
                source_path="data/teacher_raw/Doc1.docx#embedded_image_order_009",
                structured_source_path=str(DAILY_STAGE.relative_to(ROOT)),
                record_type="daily_stage_only",
                station_id="00705600",
                station_name="巴音布鲁克",
                station_id_evidence="逐日平均水位表明确为00705600巴音布鲁克",
                date=record.date.strftime("%Y-%m-%d"),
                year=record.date.year,
                month=record.date.month,
                stage_m=record.stage_m,
                gauge_datum_information="表内水位+2435.565 m=黄海基面",
                cross_section_information="逐日水位表未提供同步断面几何",
                unit_information="stage m",
                bed_or_section_change_information="未提供",
                quality_status="first_pass_pending_second_review",
                reason=(
                    "只有水位、没有同步area/width/mean depth；12月月均仍有0.0081 m差异"
                ),
            )
        )

    points = pd.read_csv(SECTION_POINTS, dtype={"station_id": str}, parse_dates=["survey_date"])
    points.station_id = points.station_id.str.zfill(8)
    points = points.loc[points.station_id.eq("00705600")]
    surveys = (
        points.groupby(["survey_date", "section_id"], as_index=False)
        .agg(
            stage_m=("measured_stage", "first"),
            point_count=("point_index", "size"),
            cross_section_position=("relative_section_position", "first"),
            relative_position_m=("relative_position_m", "first"),
            datum=("stage_datum", "first"),
            depth_allowed=("absolute_depth_computation_allowed", "all"),
        )
    )
    for record in surveys.itertuples(index=False):
        rows.append(
            inventory_row(
                source_path="data/teacher_raw/Doc1.docx#embedded_image_order_039",
                structured_source_path=str(SECTION_POINTS.relative_to(ROOT)),
                record_type="large_cross_section_points_uncomputed_geometry",
                station_id="00705600",
                station_name="巴音布鲁克",
                station_id_evidence="大断面成果表明确为00705600巴音布鲁克",
                date=record.survey_date.strftime("%Y-%m-%d"),
                year=record.survey_date.year,
                month=record.survey_date.month,
                stage_m=record.stage_m,
                gauge_datum_information=str(record.datum),
                cross_section_information=(
                    f"{record.section_id}; {record.cross_section_position}{record.relative_position_m:g} m; "
                    f"已复核{record.point_count}个点"
                ),
                unit_information="原表距离/高程/水位单位按表头记录为m，但共同垂直基准未确认",
                bed_or_section_change_information="有两期断面点，但尚未完成可靠河床变迁对齐",
                quality_status="unverified_vertical_datum_geometry_blocked",
                auxiliary_geometry_candidate=True,
                reason=(
                    "水位与床面高程共同基准未确认，area/width/mean depth禁止计算；不能进入训练池"
                ),
            )
        )

    remote_sources = [
        (
            "data/processed/natural_width/landsat_byblk/landsat_width_measurements.csv",
            "landsat_single_transect_width",
            "date",
            "width_m",
            None,
        ),
        (
            "data/processed/natural_width/landsat_byblk_multitransect/landsat_multitransect_width_measurements.csv",
            "landsat_multitransect_width",
            "date",
            "width_m",
            None,
        ),
        (
            "data/processed/natural_width/landsat_recent_byblk_multitransect/landsat_recent_multitransect_width_measurements.csv",
            "landsat_recent_multitransect_width",
            "date",
            "width_m",
            None,
        ),
        (
            "data/processed/natural_width/sentinel2_byblk_multitransect/sentinel2_multitransect_width_measurements.csv",
            "sentinel2_multitransect_width",
            "date",
            "width_m",
            None,
        ),
        (
            "data/processed/natural_width/swot_byblk_reach/swot_reach_observations_accepted.csv",
            "swot_reach_wse_width",
            "date",
            "width",
            "wse",
        ),
    ]
    for relative, record_type, date_column, width_column, water_column in remote_sources:
        path = ROOT / relative
        if not path.exists():
            continue
        data = pd.read_csv(path)
        dates = pd.to_datetime(data[date_column], errors="coerce")
        for index, record in data.iterrows():
            status = str(record.get("measurement_status", "accepted_product_row"))
            raw_water = record.get(water_column, np.nan) if water_column else np.nan
            rows.append(
                inventory_row(
                    source_path=relative,
                    structured_source_path=relative,
                    record_type=record_type,
                    station_id="00705600",
                    station_name="巴音布鲁克",
                    station_id_evidence=(
                        "由BYBLK处理管线/匹配河段48220900311赋值；源观测行不含水文站ID"
                    ),
                    date=dates.iloc[index].strftime("%Y-%m-%d") if pd.notna(dates.iloc[index]) else "",
                    year=dates.iloc[index].year if pd.notna(dates.iloc[index]) else np.nan,
                    month=dates.iloc[index].month if pd.notna(dates.iloc[index]) else np.nan,
                    width_m=pd.to_numeric(record.get(width_column), errors="coerce"),
                    raw_water_level_value=pd.to_numeric(raw_water, errors="coerce"),
                    raw_water_level_unit="SWOT WSE m" if water_column else "",
                    gauge_datum_information=(
                        "SWOT产品WSE基准不能假定等同站尺基准"
                        if water_column
                        else "无同步站尺水位"
                    ),
                    cross_section_information="遥感河段/多横断面空间支持，不等同已确认的基下3 m测流断面",
                    unit_information="width m" + ("; WSE m" if water_column else ""),
                    bed_or_section_change_information="跨年份河床与河宽变化未建立到2011断面的可靠映射",
                    quality_status=f"remote_sensing_{status}_unverified_for_d11_merge",
                    auxiliary_geometry_candidate=True,
                    reason="缺少同步站尺H、area、mean depth及同断面/同基准证明；不得合并",
                )
            )

    sword_path = ROOT / "data/processed/natural_width/station_sword_width_matches.csv"
    sword = pd.read_csv(sword_path, dtype={"station_id": str})
    sword.station_id = sword.station_id.str.zfill(8)
    for record in sword.loc[sword.station_id.eq("00705600")].itertuples(index=False):
        rows.append(
            inventory_row(
                source_path=str(sword_path.relative_to(ROOT)),
                structured_source_path=str(sword_path.relative_to(ROOT)),
                record_type="sword_reach_prior_width",
                station_id="00705600",
                station_name="巴音布鲁克",
                station_id_evidence="站点—SWORD河段几何及汇水面积匹配通过",
                width_m=record.width_m,
                gauge_datum_information="无站尺水位",
                cross_section_information=f"SWORD reach {record.sword_reach_id}; 非测流断面",
                unit_information="width m",
                bed_or_section_change_information="静态先验，无2011断面变迁信息",
                quality_status="matched_reach_prior_not_cross_section_measurement",
                reason="无日期、同步H、area和mean depth；不能扩展D11插值域",
            )
        )

    screened_files = [
        ("data/raw/runoff/BYBLK-DSK日数据.xlsx", "1978-1983日流量；无H或断面几何"),
        ("data/raw/runoff/Q-dsk-byblk.xlsx", "月流量；无H或断面几何"),
        ("data/raw/runoff/Q-新疆.xls", "2005流量/MQ工作簿；无已识别H或断面几何"),
        ("data/raw/natural_width/byblk_ground_observations.csv", "空表，仅有字段名"),
        ("data/templates/byblk_ground_observations_template.csv", "空模板，不是观测"),
    ]
    for relative, reason in screened_files:
        rows.append(
            inventory_row(
                source_path=relative,
                structured_source_path=relative,
                record_type="screened_file_no_auxiliary_geometry",
                station_id="00705600" if "BYBLK" in relative or "byblk" in relative else "unverified",
                station_name="巴音布鲁克" if "BYBLK" in relative or "byblk" in relative else "unverified",
                station_id_evidence="文件名/项目既有来源审计；非断面记录",
                gauge_datum_information="not_applicable_or_unverified",
                cross_section_information="none",
                unit_information="流量文件为m3/s或空表；不用于本阶段",
                bed_or_section_change_information="none",
                quality_status="screened_not_geometry",
                reason=reason,
            )
        )
    return pd.DataFrame(rows)


def build_repository_candidate_audit() -> tuple[pd.DataFrame, dict[str, object]]:
    records = []
    extension_counts: dict[str, int] = {extension: 0 for extension in SUPPORTED_EXTENSIONS}
    for path in ROOT.rglob("*"):
        if not path.is_file() or OUT in path.parents:
            continue
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            continue
        extension_counts[suffix] += 1
        relative = str(path.relative_to(ROOT))
        path_lower = relative.lower()
        name_match = any(term in path_lower for term in ("byblk", "stage", "width", "section", "geometry")) or "巴音布鲁克" in relative
        content_match = False
        geometry_match = False
        inspection_note = "filename_only_or_binary_workbook"
        if suffix in {".csv", ".txt", ".json", ".md"} and path.stat().st_size <= 5_000_000:
            try:
                text = path.read_text(encoding="utf-8-sig", errors="ignore")
                lower = text.lower()
                content_match = any(term in lower for term in ("byblk", "00705600", "巴音布鲁克"))
                geometry_match = any(
                    term in lower
                    for term in (
                        "stage_m",
                        "water_level",
                        "cross_section",
                        "area_m2",
                        "width_m",
                        "mean_depth",
                        "水位",
                        "断面",
                    )
                )
                inspection_note = "utf8_text_scanned"
            except OSError:
                inspection_note = "text_read_failed"
        if name_match or content_match:
            records.append(
                {
                    "source_path": relative,
                    "extension": suffix,
                    "size_bytes": path.stat().st_size,
                    "station_term_match": bool(name_match or content_match),
                    "geometry_term_match": geometry_match,
                    "inspection_note": inspection_note,
                }
            )
    audit = pd.DataFrame(records).sort_values("source_path").reset_index(drop=True)
    manifest = {
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "extension_counts_excluding_d12a_output": extension_counts,
        "candidate_files": len(audit),
        "xlsx_inspection": "15 xlsx workbooks inspected read-only with bundled artifact-tool",
        "xls_inspection": (
            "legacy xls parser unavailable; existing repository lineage scripts identify Q-新疆.xls "
            "as 2005 discharge/MQ only; file remains unverified for any hidden geometry"
        ),
    }
    return audit, manifest


def build_fold_support_domains(base: pd.DataFrame, auxiliary: pd.DataFrame | None = None) -> pd.DataFrame:
    auxiliary = pd.DataFrame(columns=base.columns) if auxiliary is None else auxiliary.copy()
    combined = pd.concat([base, auxiliary], ignore_index=True, sort=False)
    rows = []
    for held_month in sorted(base.month.unique()):
        held = base.loc[base.month.eq(held_month)].copy()
        regime = assign_regime(held_month)
        training = combined.loc[
            combined.regime.eq(regime) & ~combined.month.eq(held_month)
        ].copy()
        minimum = float(training.stage_m.min())
        maximum = float(training.stage_m.max())
        inside = held.stage_m.between(minimum, maximum, inclusive="both")
        original = pd.read_csv(D11_PREDICTIONS)
        common = original.loc[original.held_month.eq(held_month), "common_support"]
        rows.append(
            {
                "held_month": int(held_month),
                "regime": regime,
                "held_rows": len(held),
                "training_regime_stage_min": minimum,
                "training_regime_stage_max": maximum,
                "held_stage_min": float(held.stage_m.min()),
                "held_stage_max": float(held.stage_m.max()),
                "inside_rows": int(inside.sum()),
                "outside_low_rows": int((held.stage_m < minimum).sum()),
                "outside_high_rows": int((held.stage_m > maximum).sum()),
                "common_support_rows": int(common.sum()),
            }
        )
    return pd.DataFrame(rows)


def build_support_gap_audit(base: pd.DataFrame) -> pd.DataFrame:
    predictions = pd.read_csv(D11_PREDICTIONS, parse_dates=["date"])
    rows = []
    for record in predictions.loc[~predictions.common_support].itertuples(index=False):
        training = base.loc[~base.month.eq(record.held_month)]
        regime_training = training.loc[training.regime.eq(record.regime)]
        regime_min = float(regime_training.stage_m.min())
        regime_max = float(regime_training.stage_m.max())
        global_min = float(training.stage_m.min())
        global_max = float(training.stage_m.max())
        if record.stage_m < regime_min:
            direction = "below_low_bound"
            distance = regime_min - record.stage_m
            rule = f"其他年份/月份（但不能是{record.held_month}月）的{record.regime}实测断面stage <= {record.stage_m:.2f} m"
        elif record.stage_m > regime_max:
            direction = "above_high_bound"
            distance = record.stage_m - regime_max
            rule = f"其他年份/月份（但不能是{record.held_month}月）的{record.regime}实测断面stage >= {record.stage_m:.2f} m"
        else:
            direction = "inside_M1_but_not_common"
            distance = 0.0
            rule = "M1已在域内；需补足M0全年训练域，但D12A不改变M0/M1"
        rows.append(
            {
                "date": record.date.strftime("%Y-%m-%d"),
                "held_month": int(record.held_month),
                "regime": record.regime,
                "stage_m": record.stage_m,
                "M0_outside_domain": not bool(record.M0_global_inside_domain),
                "M1_outside_domain": not bool(record.M1_regime_inside_domain),
                "training_global_stage_min": global_min,
                "training_global_stage_max": global_max,
                "training_regime_stage_min": regime_min,
                "training_regime_stage_max": regime_max,
                "gap_direction": direction,
                "distance_to_legal_regime_support_m": distance,
                "required_other_month_stage_m": record.stage_m,
                "minimum_legal_coverage_requirement": rule,
                "extrapolation_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def eligible_auxiliary(inventory: pd.DataFrame) -> pd.DataFrame:
    required = ["stage_m", "area_m2", "width_m", "mean_depth_m"]
    mask = inventory.auxiliary_geometry_candidate.fillna(False).astype(bool)
    mask &= inventory.verified_mergeable.fillna(False).astype(bool)
    mask &= inventory[required].notna().all(axis=1)
    result = inventory.loc[mask].copy()
    if not result.empty:
        result["date"] = pd.to_datetime(result.date)
        result["year"] = result.date.dt.year
        result["month"] = result.date.dt.month
        result["regime"] = result.month.map(assign_regime)
    return result


def coverage_with_auxiliary(base: pd.DataFrame, auxiliary: pd.DataFrame) -> int:
    total_inside = 0
    combined = pd.concat([base, auxiliary], ignore_index=True, sort=False)
    for held_month in sorted(base.month.unique()):
        held = base.loc[base.month.eq(held_month)]
        regime = assign_regime(held_month)
        training = combined.loc[
            combined.regime.eq(regime) & ~combined.month.eq(held_month)
        ]
        minimum = float(training.stage_m.min())
        maximum = float(training.stage_m.max())
        total_inside += int(held.stage_m.between(minimum, maximum, inclusive="both").sum())
    return total_inside


def build_coverage_simulation(base: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    verified = eligible_auxiliary(inventory)
    hypothetical_sep = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2011-09-21"),
                "year": 2011,
                "month": 9,
                "regime": "open_water",
                "stage_m": 3.85,
                "area_m2": 1.0,
                "width_m": 1.0,
                "mean_depth_m": 1.0,
            }
        ]
    )
    return pd.DataFrame(
        [
            {
                "batch": "D11_baseline",
                "currently_admissible": True,
                "auxiliary_rows": 0,
                "common_support_rows_of_24": 12,
                "coverage": 0.50,
                "interpretation": "原D11，不改变",
            },
            {
                "batch": "all_verified_auxiliary_geometry_found_in_repository",
                "currently_admissible": True,
                "auxiliary_rows": len(verified),
                "common_support_rows_of_24": coverage_with_auxiliary(base, verified),
                "coverage": coverage_with_auxiliary(base, verified) / 24,
                "interpretation": "当前没有verified auxiliary geometry，覆盖无法恢复",
            },
            {
                "batch": "conditional_2011_09_21_section_if_future_verified",
                "currently_admissible": False,
                "auxiliary_rows": 1,
                "common_support_rows_of_24": coverage_with_auxiliary(base, hypothetical_sep),
                "coverage": coverage_with_auxiliary(base, hypothetical_sep) / 24,
                "interpretation": (
                    "仅说明潜力：必须先确认垂直基准、计算完整几何、确认同断面及河床稳定性；当前禁止使用"
                ),
            },
        ]
    )


def minimum_requirements() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "option": "A",
                "regime": "open_water",
                "held_month_excluded": 4,
                "required_auxiliary_calendar_month": "not April",
                "required_stage_interval": "stage >= 4.80 m",
                "recoverable_original_rows": 3,
                "resulting_coverage_if_full_geometry_verified": "15/24 = 62.5%",
                "note": "恢复April的4.34、4.62、4.80 m；5.01和5.16仍超域",
            },
            {
                "option": "B",
                "regime": "open_water",
                "held_month_excluded": 5,
                "required_auxiliary_calendar_month": "not May",
                "required_stage_interval": "stage <= 3.86 m",
                "recoverable_original_rows": 3,
                "resulting_coverage_if_full_geometry_verified": "15/24 = 62.5%",
                "note": "恢复May的3.86、3.87、3.88 m；更低阈值可恢复更多",
            },
            {
                "option": "C",
                "regime": "open_water",
                "held_month_excluded": "4 and 5",
                "required_auxiliary_calendar_month": "not the corresponding held month",
                "required_stage_interval": "non-April stage >= 4.62 m AND non-May stage <= 3.88 m",
                "recoverable_original_rows": 3,
                "resulting_coverage_if_full_geometry_verified": "15/24 = 62.5%",
                "note": "April恢复2条，May恢复1条",
            },
            {
                "option": "D",
                "regime": "cold_season plus open_water",
                "held_month_excluded": "12 plus 4 or 5",
                "required_auxiliary_calendar_month": "not December plus eligible open-water month",
                "required_stage_interval": (
                    "cold stage <= 3.65 m AND >= 4.43 m, plus one open-water boundary point"
                ),
                "recoverable_original_rows": 3,
                "resulting_coverage_if_full_geometry_verified": "15/24 = 62.5%",
                "note": "December两端最多恢复2条，仍需至少1条open-water恢复",
            },
        ]
    )


def svg_header(title: str, description: str, width: int = 900, height: int = 560) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{html.escape(title)}</title>",
        f"<desc>{html.escape(description)}</desc>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,"Microsoft YaHei",sans-serif;fill:#20252b}.title{font-size:20px;font-weight:600}.axis{font-size:13px}.tick{font-size:11px;fill:#4c596a}.grid{stroke:#d9dee5;stroke-width:1}.frame{stroke:#697586;stroke-width:1;fill:none}.legend{font-size:11px}</style>',
    ]


def linear_scale(value: float, minimum: float, maximum: float, start: float, end: float) -> float:
    if maximum == minimum:
        return (start + end) / 2
    return start + (value - minimum) * (end - start) / (maximum - minimum)


def plot_geometry(predictions: pd.DataFrame, variable: str, ylabel: str, filename: str) -> None:
    width, height = 900, 560
    left, right, top, bottom = 90, 40, 75, 80
    x0, x1 = predictions.stage_m.min(), predictions.stage_m.max()
    y0, y1 = predictions[variable].min(), predictions[variable].max()
    xpad, ypad = (x1 - x0) * 0.06, (y1 - y0) * 0.08
    x0, x1, y0, y1 = x0 - xpad, x1 + xpad, y0 - ypad, y1 + ypad
    title = f"BYBLK verified 2011 measurements: H vs {ylabel}"
    svg = svg_header(title, "Only the original 24 verified D11 measurement rows are plotted.", width, height)
    svg.append(f'<text class="title" x="{width/2}" y="35" text-anchor="middle">{html.escape(title)}</text>')
    plot_w, plot_h = width - left - right, height - top - bottom
    for index in range(6):
        xv = x0 + index * (x1 - x0) / 5
        px = linear_scale(xv, x0, x1, left, left + plot_w)
        svg.append(f'<line class="grid" x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{top+plot_h}"/>')
        svg.append(f'<text class="tick" x="{px:.1f}" y="{top+plot_h+22}" text-anchor="middle">{xv:.2f}</text>')
        yv = y0 + index * (y1 - y0) / 5
        py = linear_scale(yv, y0, y1, top + plot_h, top)
        svg.append(f'<line class="grid" x1="{left}" y1="{py:.1f}" x2="{left+plot_w}" y2="{py:.1f}"/>')
        svg.append(f'<text class="tick" x="{left-10}" y="{py+4:.1f}" text-anchor="end">{yv:.2f}</text>')
    svg.append(f'<rect class="frame" x="{left}" y="{top}" width="{plot_w}" height="{plot_h}"/>')
    colors = {"cold_season": "#276fbf", "open_water": "#e07a1f"}
    for record in predictions.itertuples(index=False):
        x = linear_scale(record.stage_m, x0, x1, left, left + plot_w)
        y = linear_scale(getattr(record, variable), y0, y1, top + plot_h, top)
        color = colors[record.regime]
        if record.common_support:
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="#ffffff" stroke-width="1"/>')
        else:
            svg.append(f'<path d="M{x-5:.1f},{y-5:.1f} L{x+5:.1f},{y+5:.1f} M{x-5:.1f},{y+5:.1f} L{x+5:.1f},{y-5:.1f}" stroke="{color}" stroke-width="2.5" fill="none"/>')
    svg.extend(
        [
            f'<text class="axis" x="{left+plot_w/2}" y="{height-22}" text-anchor="middle">Stage H (m)</text>',
            f'<text class="axis" transform="translate(23 {top+plot_h/2}) rotate(-90)" text-anchor="middle">{html.escape(ylabel)}</text>',
            f'<circle cx="{left}" cy="{height-48}" r="5" fill="#276fbf"/><text class="legend" x="{left+10}" y="{height-44}">cold / common</text>',
            f'<path d="M{left+135},{height-53} l10,10 m-10,0 l10,-10" stroke="#276fbf" stroke-width="2"/><text class="legend" x="{left+151}" y="{height-44}">cold / unsupported</text>',
            f'<circle cx="{left+310}" cy="{height-48}" r="5" fill="#e07a1f"/><text class="legend" x="{left+320}" y="{height-44}">open / common</text>',
            f'<path d="M{left+445},{height-53} l10,10 m-10,0 l10,-10" stroke="#e07a1f" stroke-width="2"/><text class="legend" x="{left+461}" y="{height-44}">open / unsupported</text>',
            "</svg>",
        ]
    )
    (OUT / filename).write_text("\n".join(svg), encoding="utf-8")


def plot_fold_domains(predictions: pd.DataFrame, domains: pd.DataFrame) -> None:
    width, height = 940, 620
    left, right, top, bottom = 125, 45, 70, 70
    x0 = min(domains.training_regime_stage_min.min(), predictions.stage_m.min()) - 0.08
    x1 = max(domains.training_regime_stage_max.max(), predictions.stage_m.max()) + 0.08
    plot_w, plot_h = width - left - right, height - top - bottom
    title = "M1 training stage domain and held-month observations"
    svg = svg_header(title, "Lines show legal training domains. Circles are inside; crosses are outside.", width, height)
    svg.append(f'<text class="title" x="{width/2}" y="35" text-anchor="middle">{title}</text>')
    for index in range(6):
        stage = x0 + index * (x1 - x0) / 5
        x = linear_scale(stage, x0, x1, left, left + plot_w)
        svg.append(f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+plot_h}"/>')
        svg.append(f'<text class="tick" x="{x:.1f}" y="{top+plot_h+24}" text-anchor="middle">{stage:.2f}</text>')
    spacing = plot_h / len(domains)
    for index, row in enumerate(domains.itertuples(index=False)):
        y = top + (index + 0.5) * spacing
        lo = linear_scale(row.training_regime_stage_min, x0, x1, left, left + plot_w)
        hi = linear_scale(row.training_regime_stage_max, x0, x1, left, left + plot_w)
        svg.append(f'<text class="axis" x="{left-12}" y="{y+4:.1f}" text-anchor="end">held {row.held_month:02d}</text>')
        svg.append(f'<line x1="{lo:.1f}" y1="{y:.1f}" x2="{hi:.1f}" y2="{y:.1f}" stroke="#4c596a" stroke-width="7" stroke-linecap="round"/>')
        held = predictions.loc[predictions.held_month.eq(row.held_month)]
        for point in held.itertuples(index=False):
            x = linear_scale(point.stage_m, x0, x1, left, left + plot_w)
            if point.M1_regime_inside_domain:
                svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2b8a3e" stroke="#fff"/>')
            else:
                svg.append(f'<path d="M{x-5:.1f},{y-5:.1f} L{x+5:.1f},{y+5:.1f} M{x-5:.1f},{y+5:.1f} L{x+5:.1f},{y-5:.1f}" stroke="#c92a2a" stroke-width="2.5"/>')
    svg.extend(
        [
            f'<rect class="frame" x="{left}" y="{top}" width="{plot_w}" height="{plot_h}"/>',
            f'<text class="axis" x="{left+plot_w/2}" y="{height-20}" text-anchor="middle">Stage H (m)</text>',
            "</svg>",
        ]
    )
    (OUT / "fold_training_stage_domains.svg").write_text("\n".join(svg), encoding="utf-8")


def plot_support_status(predictions: pd.DataFrame) -> None:
    counts = (
        predictions.assign(status=np.where(predictions.common_support, "common_support", "unsupported"))
        .groupby(["held_month", "status"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["common_support", "unsupported"], fill_value=0)
    )
    width, height = 900, 520
    left, right, top, bottom = 85, 35, 70, 75
    plot_w, plot_h = width - left - right, height - top - bottom
    maximum = int(counts.sum(axis=1).max())
    title = "Common-support and unsupported records by held month"
    svg = svg_header(title, "Stacked counts use only original D11 records.", width, height)
    svg.append(f'<text class="title" x="{width/2}" y="35" text-anchor="middle">{title}</text>')
    for value in range(maximum + 1):
        y = linear_scale(value, 0, maximum, top + plot_h, top)
        svg.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}"/>')
        svg.append(f'<text class="tick" x="{left-10}" y="{y+4:.1f}" text-anchor="end">{value}</text>')
    step = plot_w / len(counts)
    bar_width = step * 0.58
    for index, (month, row) in enumerate(counts.iterrows()):
        x = left + index * step + (step - bar_width) / 2
        common_h = row.common_support / maximum * plot_h
        unsupported_h = row.unsupported / maximum * plot_h
        svg.append(f'<rect x="{x:.1f}" y="{top+plot_h-common_h:.1f}" width="{bar_width:.1f}" height="{common_h:.1f}" fill="#2b8a3e"/>')
        svg.append(f'<rect x="{x:.1f}" y="{top+plot_h-common_h-unsupported_h:.1f}" width="{bar_width:.1f}" height="{unsupported_h:.1f}" fill="#c92a2a"/>')
        svg.append(f'<text class="tick" x="{x+bar_width/2:.1f}" y="{top+plot_h+22}" text-anchor="middle">{month:02d}</text>')
    svg.extend(
        [
            f'<rect class="frame" x="{left}" y="{top}" width="{plot_w}" height="{plot_h}"/>',
            f'<text class="axis" x="{left+plot_w/2}" y="{height-22}" text-anchor="middle">Held calendar month</text>',
            f'<text class="axis" transform="translate(22 {top+plot_h/2}) rotate(-90)" text-anchor="middle">Original D11 test records</text>',
            f'<rect x="{left}" y="{height-52}" width="12" height="12" fill="#2b8a3e"/><text class="legend" x="{left+18}" y="{height-42}">common support</text>',
            f'<rect x="{left+145}" y="{height-52}" width="12" height="12" fill="#c92a2a"/><text class="legend" x="{left+163}" y="{height-42}">unsupported</text>',
            "</svg>",
        ]
    )
    (OUT / "common_support_status_by_month.svg").write_text("\n".join(svg), encoding="utf-8")


def write_report(
    inventory: pd.DataFrame,
    gaps: pd.DataFrame,
    domains: pd.DataFrame,
    simulation: pd.DataFrame,
) -> None:
    verified_aux = eligible_auxiliary(inventory)
    satellite_rows = int(inventory.record_type.str.contains("landsat|sentinel|swot", regex=True).sum())
    accepted_remote = int(
        inventory.quality_status.str.contains("accepted|accepted_product_row", regex=True).sum()
    )
    conditional = simulation.loc[
        simulation.batch.eq("conditional_2011_09_21_section_if_future_verified")
    ].iloc[0]
    report = f"""# 阶段D12A：BYBLK分状态H→断面关系支持域与数据完整性审计

## 1. 为什么启动D12A

D11在共同支持域内显示分状态关系的面积MAE由9.62397降至1.59037 m²、RMSE由13.28248降至2.38943 m²，但其目标不是继续追求误差，而是解释为什么24条原始测试记录只有12条可在M0与M1共同域内合法插值。D12A不修改GNN、D9B参数、季节定义、D11协议或门槛，也不允许外推。

## 2. D11唯一gate失败原因

D11的冻结结果仍为`gate_passed=false`。唯一失败项是common support coverage=12/24=50%，低于冻结的60%；误差改善、RMSE改善和分状态不退化条件均满足。本阶段保留原判定，不降低门槛。

## 3. 哪些月份/水位段导致支持不足

12条域外记录全部集中在April、May和December。April的M1训练域为3.84–4.11 m，6条测试中仅3.93 m在域内；4.34、4.62、4.80、5.01、5.16 m位于高端域外。May的M1训练域为3.93–5.16 m，3.84–3.88 m五条全部低端域外。December的冷季训练域为3.68–4.31 m，3.65 m低端域外、4.43 m高端域外。

## 4. open-water缺哪些stage

要单独把coverage提高到至少15/24，可取得非April、完整且同断面的open-water几何，使训练高端达到至少4.80 m；或取得非May几何，使训练低端达到至多3.86 m。组合方案是非April达到至少4.62 m并且非May达到至多3.88 m。阈值是支持域需求，不是合成观测。

## 5. cold-season缺哪些stage

December折需要非December冷季完整断面在低端达到不高于3.65 m、高端达到不低于4.43 m。补齐两端最多恢复2条，仍需至少1条open-water记录才能达到15/24。

## 6. 仓库中发现了哪些额外实测资料

除D11原24条外，发现365条2011逐日水位、2期BYBLK实测大断面点（2011-05-21 H=3.87 m、2011-09-21 H=3.85 m）、{satellite_rows}条遥感河宽/WSE候选记录（其中{accepted_remote}条产品或算法状态为accepted）、1条SWORD静态宽度先验。原始xlsx/xls runoff工作簿只含流量或MQ；地面观测CSV与模板为空。仓库中多个review工作簿是上述资料的派生副本，不是独立观测。

## 7. 哪些可以合并、哪些不能以及原因

当前verified auxiliary geometry数量为{len(verified_aux)}。逐日水位没有同步面积、宽度和平均水深；大断面点的床面高程与水位共同垂直基准未确认，现有质量文件明确禁止计算几何；Landsat/Sentinel/SWOT/SWORD的空间支持不是已确认的基下3 m测流断面，也没有同时满足站尺基准、面积、平均水深和河床稳定性证据。因此没有任何额外资料可以自动并入D11训练池。

## 8. 如果加入合法资料，coverage理论上能提高多少

加入仓库内当前全部verified auxiliary geometry后仍为12/24（50%），因为合格记录为0。2011-09-21断面若未来完成基准确认、几何计算、同断面映射和河床稳定性核验，其H=3.85 m且月份为September，可合法进入held-May折，理论上把M1覆盖提高到{int(conditional.common_support_rows_of_24)}/24={conditional.coverage:.1%}；这只是条件模拟，当前资料不得使用。

## 9. 是否值得启动正式D12B confirmatory experiment

当前不建议立即冻结D12B。先把2011-09-21大断面从“点已转录但基准未确认”提升为可计算完整几何的独立记录，或找到同一测流断面、非May的open-water H≤3.86 m完整测量；高水位方向则需非April的H≥4.80 m完整测量。只有至少一批资料通过全部合并检查后，才值得冻结D12B。

## 10. 数据仍不足时需要补采/补找什么

优先补找原始大断面表的高程基准说明、水尺零点沿革、断面桩号/基上基下定义和2011河床变迁记录，并由第二人复核日水位。若需补采，open-water应覆盖≤3.86 m与≥4.80 m，cold-season应覆盖≤3.65 m与≥4.43 m；每次必须同步记录H、面积、宽度、平均水深、断面位置、单位和水尺基准。为保持out-of-month含义，目标held month的所有年份记录都必须从对应折训练中排除。
"""
    (OUT / "stage_d12a_report_zh.md").write_text(report, encoding="utf-8")


def main() -> None:
    assert_d11_immutable()
    OUT.mkdir(parents=True, exist_ok=True)
    base = base_measurements()
    inventory = build_measurement_inventory()
    candidate_audit, scan_manifest = build_repository_candidate_audit()
    gaps = build_support_gap_audit(base)
    domains = build_fold_support_domains(base)
    simulation = build_coverage_simulation(base, inventory)
    requirements = minimum_requirements()

    inventory.to_csv(OUT / "measurement_inventory.csv", index=False, encoding="utf-8-sig")
    gaps.to_csv(OUT / "d12_support_gap_audit.csv", index=False, encoding="utf-8-sig")
    domains.to_csv(OUT / "fold_support_domains.csv", index=False, encoding="utf-8-sig")
    candidate_audit.to_csv(OUT / "repository_candidate_sources.csv", index=False, encoding="utf-8-sig")
    simulation.to_csv(OUT / "auxiliary_coverage_simulation.csv", index=False, encoding="utf-8-sig")
    requirements.to_csv(OUT / "minimum_additional_stage_requirements.csv", index=False, encoding="utf-8-sig")
    (OUT / "repository_scan_manifest.json").write_text(
        json.dumps(scan_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    predictions = pd.read_csv(D11_PREDICTIONS)
    plot_geometry(predictions, "area_m2", "Cross-section area (m²)", "h_vs_area_by_regime.svg")
    plot_geometry(predictions, "width_m", "Surface width (m)", "h_vs_width_by_regime.svg")
    plot_geometry(predictions, "mean_depth_m", "Mean depth (m)", "h_vs_mean_depth_by_regime.svg")
    plot_fold_domains(predictions, domains)
    plot_support_status(predictions)
    write_report(inventory, gaps, domains, simulation)

    result = {
        "status": "completed_support_domain_and_data_integrity_audit",
        "d11_protocol_unchanged": sha256(D11_PROTOCOL) == EXPECTED_D11_HASHES["protocol_frozen.json"],
        "d11_gate_passed": False,
        "d11_common_support": "12/24",
        "unsupported_rows_audited": len(gaps),
        "verified_auxiliary_geometry_rows": len(eligible_auxiliary(inventory)),
        "coverage_after_all_current_verified_auxiliary": "12/24",
        "d12b_started": False,
        "decision": "current_repository_data_cannot_resolve_d11_support_deficit",
        "season_definition": {"open_water_months": sorted(OPEN_MONTHS), "cold_season_months": [11, 12, 1, 2, 3]},
        "extrapolation_allowed": False,
        "inputs": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in [D11_PROTOCOL, D11_RESULT, D11_PREDICTIONS, MEASUREMENTS, DAILY_STAGE, SECTION_POINTS]
        },
    }
    (OUT / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nFold domains:\n", domains.to_string(index=False))
    print("\nCoverage simulation:\n", simulation.to_string(index=False))


if __name__ == "__main__":
    main()
