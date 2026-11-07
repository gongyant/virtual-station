from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d12a1_verification"
D11 = ROOT / "outputs/diagnosis_2005_snapshot/stage_d11_geometry_cross_validation"
D11_PROTOCOL = D11 / "protocol_frozen.json"
D11_RESULT = D11 / "result.json"
D11_PREDICTIONS = D11 / "outer_month_predictions.csv"
SECTION_POINTS = ROOT / "outputs/diagnosis_2005_snapshot/stage_d3/cross_section_points_2011_reviewed.csv"
DAILY_STAGE = ROOT / "outputs/diagnosis_2005_snapshot/stage_d10_byblk_stage/daily_stage_byblk_2011_reviewed.csv"
MEASUREMENTS = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b/discharge_measurements_2011_canonical.csv"
DOC1 = ROOT / "data/teacher_raw/Doc1.docx"

EXPECTED_D11_HASHES = {
    "protocol_frozen.json": "a79d51b293718d027caf2b697f3d1f0ddc69b8686196b842c157e02529a8e296",
    "result.json": "563ca32744f4121705bae40c0d53d26a30bad6f8431ab055ba1f1ccb1436e599",
    "outer_month_predictions.csv": "b6f2a0ebc40363f6e9f3eb4a5f995e3fa05dc6d4863fe4bd1ddd6bfa5539a73d",
}
OPEN_MONTHS = frozenset({4, 5, 6, 7, 8, 9, 10})
VERTICAL_DATUM_VERIFIED = False
HORIZONTAL_REOCCUPATION_VERIFIED = False
EXTRAPOLATION_ALLOWED = False


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assign_regime(month: int) -> str:
    return "open_water" if int(month) in OPEN_MONTHS else "cold_season"


def exclude_held_calendar_month(records: pd.DataFrame, held_month: int) -> pd.DataFrame:
    """Exclude the named calendar month across every year, not merely one date/year."""
    dates = pd.to_datetime(records["date"])
    return records.loc[dates.dt.month.ne(int(held_month))].copy()


def assert_frozen_d11() -> None:
    for name, expected in EXPECTED_D11_HASHES.items():
        actual = sha256(D11 / name)
        if actual != expected:
            raise RuntimeError(f"D11 immutable artifact changed: {name}: {actual}")
    result = json.loads(D11_RESULT.read_text(encoding="utf-8"))
    if result["gate_passed"] is not False:
        raise RuntimeError("D11 gate must remain false")
    if result["measurement_rows"] != 24 or result["common_support_rows"] != 12:
        raise RuntimeError("D11 baseline must remain 12/24")


def load_byblk_points() -> pd.DataFrame:
    data = pd.read_csv(SECTION_POINTS, dtype={"station_id": str})
    data["station_id"] = data.station_id.str.zfill(8)
    data = data.loc[data.station_id.eq("00705600")].copy()
    data["survey_date"] = pd.to_datetime(data.survey_date)
    expected = {pd.Timestamp("2011-05-21"): 28, pd.Timestamp("2011-09-21"): 28}
    if data.groupby("survey_date").size().to_dict() != expected:
        raise RuntimeError("Expected exactly 28 BYBLK points in each survey")
    return data.sort_values(["survey_date", "point_index"])


def load_daily_stage() -> pd.DataFrame:
    data = pd.read_csv(DAILY_STAGE, dtype={"station_id": str})
    data["station_id"] = data.station_id.str.zfill(8)
    data = data.loc[data.station_id.eq("00705600")].copy()
    data["date"] = pd.to_datetime(data.date)
    if len(data) != 365:
        raise RuntimeError("D12A.1 expects the frozen 365-day BYBLK stage series")
    return data.sort_values("date")


def load_geometry_measurements() -> pd.DataFrame:
    data = pd.read_csv(MEASUREMENTS, dtype={"station_id": str})
    data["station_id"] = data.station_id.str.zfill(8)
    data = data.loc[data.station_id.eq("00705600")].copy()
    data["date"] = pd.to_datetime(data.date)
    data["month"] = data.date.dt.month
    data["regime"] = data.month.map(assign_regime)
    if len(data) != 24:
        raise RuntimeError("Frozen BYBLK geometry table must contain 24 rows")
    return data.sort_values("date")


def build_source_evidence_manifest() -> pd.DataFrame:
    rows = [
        ("E01", "data/teacher_raw/Doc1.docx#embedded_image_order_039", "2011-05-21；流速仪测流断面（基下3m）；测时水位3.87m；28个起点距/河底高程点；右岸至左岸", "May survey-time stage, named section, units, point count and direction", "床面高程基准、水尺零点换算、复测基准点", "direct_visual_review"),
        ("E02", "data/teacher_raw/Doc1.docx#embedded_image_order_039", "2011-09-21；流速仪测流断面（基下3m）；测时水位3.85m；28个起点距/河底高程点；右岸至左岸", "September survey-time stage, named section, units, point count and direction", "床面高程基准、水尺零点换算、复测基准点", "direct_visual_review"),
        ("E03", "data/teacher_raw/Doc1.docx#embedded_image_order_009", "逐日平均水位表：2011-05-21为3.89m，2011-09-21为3.87m；表内水位+2435.565m=黄海基面", "daily-average semantics and daily-stage gauge conversion", "大断面床面高程与逐日水位共基准", "direct_visual_review"),
        ("E04", "data/teacher_raw/Doc1.docx#embedded_image_order_022", "BYBLK 24条测流成果均列在基下3m测流断面；两次大断面日期没有同步测流成果行", "D11 geometry records' nominal section name", "大断面与逐次测流横断面严格复占、垂直基准或河床稳定性", "direct_visual_review_and_structured_cross_check"),
        ("E05", "data/teacher_raw/Doc1.docx#embedded_image_order_038,040 and adjacent 037,041", "相邻页为其他测站/同类大断面表，未发现BYBLK床面高程基准或2435.565转换说明", "absence of direct datum evidence in inspected context", "任何未明示的offset或基准转换", "direct_visual_context_review"),
    ]
    return pd.DataFrame(rows, columns=["evidence_id", "source", "observed_text_or_fact", "supports", "does_not_establish", "review_status"])


def build_stage_reconciliation(points: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for date in (pd.Timestamp("2011-05-21"), pd.Timestamp("2011-09-21")):
        survey = points.loc[points.survey_date.eq(date), "measured_stage"].unique()
        day = daily.loc[daily.date.eq(date), "stage_m"].unique()
        if len(survey) != 1 or len(day) != 1:
            raise RuntimeError(f"Stage reconciliation failed for {date:%Y-%m-%d}")
        survey_h, daily_h = float(survey[0]), float(day[0])
        rows.append({
            "date": date.strftime("%Y-%m-%d"), "station_id": "00705600",
            "section_survey_stage_m": survey_h, "section_stage_semantics": "测时水位（断面施测时水位）",
            "daily_mean_stage_m": daily_h, "daily_stage_semantics": "逐日平均水位",
            "survey_minus_daily_m": survey_h - daily_h, "unit_consistency_verified": True,
            "unit_evidence": "两张原表表头均以m记录水位", "same_gauge_datum_verified": False,
            "datum_reason": "逐日表给出水尺到黄海基面换算；大断面表未明示测时水位的水尺零点/基面",
            "stage_for_section_geometry_m": survey_h,
            "stage_choice_status": "semantic_choice_only_geometry_blocked",
            "stage_choice_reason": "断面几何应对应同时刻的测时水位，不应用日平均替代；但垂直基准未确认，禁止计算verified几何",
            "verified_geometry_computation_allowed": False,
            "source_survey": "Doc1.docx#embedded_image_order_039",
            "source_daily": "Doc1.docx#embedded_image_order_009",
        })
    return pd.DataFrame(rows)


def build_vertical_datum_audit() -> pd.DataFrame:
    rows = [
        ("断面床面高程采用什么垂直基准", "原表仅标河底高程(m)，未给出基面、BM、水尺零点或假定基面说明", False, False, "unverified"),
        ("逐日水位采用什么垂直基准", "逐日表明确表内水位+2435.565m=黄海基面高程", True, True, "verified_for_daily_stage_only"),
        ("大断面测时水位与逐日水位是否同一水尺基准", "单位一致且数值接近，但大断面表没有水尺零点/基面说明；不得用数值接近代替文档证据", False, False, "unverified"),
        ("是否可用Z_water=H+2435.565m计算大断面几何", "2435.565只被逐日水位表明确；未证明28个床面高程点与该黄海基面处于同一基准", False, False, "prohibited"),
        ("是否存在可用的假定基面/offset转换", "检查的原页及相邻页未发现明确转换关系；禁止通过面积拟合选择offset", False, False, "not_found"),
    ]
    return pd.DataFrame(rows, columns=["question", "finding", "direct_document_evidence", "verified", "decision"])


def build_section_identity_audit(points: pd.DataFrame) -> pd.DataFrame:
    may = points.loc[points.survey_date.eq("2011-05-21")].sort_values("point_index")
    sep = points.loc[points.survey_date.eq("2011-09-21")].sort_values("point_index")
    same_x = may.distance_from_origin_m.tolist() == sep.distance_from_origin_m.tolist()
    rows = [
        ("section_name", "两期均为流速仪测流断面（基下3m）；D11原24条测流成果也均列为基下3m", True, "E01,E02,E04"),
        ("chainage_or_position", "相对基本水尺为基下3m，但未发现绝对桩号/坐标", False, "E01,E02"),
        ("x_zero_reference", "原表给出起点距，但未说明x=0永久基点", False, "E01,E02"),
        ("bank_and_survey_direction", "两期均按右岸至左岸列点", True, "E01,E02"),
        ("point_grid_identity", f"两期各28点；x网格不完全相同（May含56.5m，September对应56.0m）；exact_equal={same_x}", False, "structured transcription of E01,E02"),
        ("section_migration", "未发现断面迁移或不迁移的记录", False, "E01,E02,E05"),
        ("baseline_change", "未发现基准线/复测控制点变化记录，也未找到明确不变声明", False, "E01,E02,E05"),
        ("overall_identity", "名义上同一基下3m测流断面，但严格复占和坐标基准证据不足", False, "combined evidence"),
    ]
    return pd.DataFrame(rows, columns=["check_item", "finding", "verified", "evidence"])


def build_auxiliary_mergeability_decision() -> pd.DataFrame:
    return pd.DataFrame([{
        "candidate_date": "2011-09-21",
        "station_id": "00705600",
        "station_id_verified": True,
        "station_id_evidence": "Doc1大断面表头为开都河巴音布鲁克站；测站映射为00705600",
        "same_section_nominal": True,
        "same_section_reliable_mapping_verified": False,
        "section_evidence": "两期及D11均标基下3m，但缺桩号、永久x=0和复测控制线",
        "gauge_datum_verified": False,
        "gauge_datum_evidence": "逐日表有2435.565换算；大断面页没有证明该换算及床面共基准",
        "units_verified": True,
        "unit_evidence": "原表水位、起点距、河底高程均标m",
        "bed_or_section_stability_verified": False,
        "stability_evidence": "缺水平/垂直配准和断面变迁记录，稳定性指标被阻断",
        "verified_mergeable": False,
        "training_pool_admission": "rejected",
        "reason": "垂直基准与严格断面复占控制不足",
    }])


def write_blocked_geometry(points: pd.DataFrame, date: str) -> None:
    selected = points.loc[points.survey_date.eq(date)].sort_values("point_index").copy()
    stage = float(selected.measured_stage.iloc[0])
    date_token = date.replace("-", "")
    pointwise = pd.DataFrame({
        "station_id": "00705600", "date": date, "point_index": selected.point_index,
        "distance_from_origin_m": selected.distance_from_origin_m,
        "reported_bed_elevation": selected.bed_elevation,
        "reported_bed_elevation_datum": selected.bed_elevation_datum,
        "section_survey_stage_m": stage, "water_surface_elevation_m": np.nan,
        "depth_m": np.nan, "depth_status": "blocked_vertical_datum_unverified", "verified": False,
    })
    pointwise.to_csv(OUT / f"pointwise_depths_{date_token}.csv", index=False, encoding="utf-8-sig")
    geometry = pd.DataFrame([{
        "station_id": "00705600", "date": date, "section_name": "流速仪测流断面（基下3m）",
        "point_count": len(selected), "section_survey_stage_m": stage,
        "vertical_datum_verified": False, "horizontal_reoccupation_verified": False,
        "z_water_m": np.nan, "left_water_intersection_m": np.nan, "right_water_intersection_m": np.nan,
        "area_m2": np.nan, "top_width_m": np.nan, "mean_depth_m": np.nan,
        "wetted_perimeter_m": np.nan, "hydraulic_radius_m": np.nan,
        "geometry_status": "blocked_vertical_datum_unverified",
        "reason": "未证明测时水位与28个床面高程处于同一垂直基准；禁止选择offset拟合D11",
    }])
    geometry.to_csv(OUT / f"section_geometry_{date_token}.csv", index=False, encoding="utf-8-sig")
    write_raw_profile_svg(selected, date, OUT / f"section_profile_{date_token}.svg")


def write_raw_profile_svg(points: pd.DataFrame, date: str, path: Path) -> None:
    width, height = 1080, 620
    left, right, top, bottom = 90, 35, 90, 85
    x = points.distance_from_origin_m.to_numpy(float)
    z = points.bed_elevation.to_numpy(float)
    xmin, xmax = float(x.min()), float(x.max())
    zmin, zmax = float(z.min()), float(z.max())
    xpad, zpad = max((xmax - xmin) * 0.03, 0.5), max((zmax - zmin) * 0.08, 0.2)
    xmin, xmax, zmin, zmax = xmin - xpad, xmax + xpad, zmin - zpad, zmax + zpad
    sx = lambda value: left + (value - xmin) / (xmax - xmin) * (width - left - right)
    sy = lambda value: top + (zmax - value) / (zmax - zmin) * (height - top - bottom)
    polyline = " ".join(f"{sx(a):.2f},{sy(b):.2f}" for a, b in zip(x, z))
    circles = "".join(f'<circle cx="{sx(a):.2f}" cy="{sy(b):.2f}" r="3.3" fill="#0b7285"/>' for a, b in zip(x, z))
    title = html.escape(f"BYBLK {date} 原表床面点（未验证垂直基准）")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#fbfcfe"/>
<text x="{width/2}" y="34" text-anchor="middle" font-family="sans-serif" font-size="22" font-weight="bold">{title}</text>
<text x="{width/2}" y="61" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#a33">仅绘制原始(x,z)；未绘制水面、深度或verified几何</text>
<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#333"/>
<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#333"/>
<polyline points="{polyline}" fill="none" stroke="#0b7285" stroke-width="2.4"/>{circles}
<text x="{width/2}" y="{height-28}" text-anchor="middle" font-family="sans-serif" font-size="15">原表起点距 (m)，右岸→左岸</text>
<text x="22" y="{height/2}" transform="rotate(-90 22 {height/2})" text-anchor="middle" font-family="sans-serif" font-size="15">原表河底高程 (m；基准未确认)</text>
<text x="{left}" y="{height-55}" font-family="sans-serif" font-size="12">x={x.min():g}–{x.max():g} m</text>
<text x="{width-right}" y="{height-55}" text-anchor="end" font-family="sans-serif" font-size="12">28 points | status=blocked</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")


def build_bed_stability_audit(points: pd.DataFrame) -> pd.DataFrame:
    may = points.loc[points.survey_date.eq("2011-05-21")]
    sep = points.loc[points.survey_date.eq("2011-09-21")]
    reported_low = max(float(may.distance_from_origin_m.min()), float(sep.distance_from_origin_m.min()))
    reported_high = min(float(may.distance_from_origin_m.max()), float(sep.distance_from_origin_m.max()))
    return pd.DataFrame([{
        "may_date": "2011-05-21", "september_date": "2011-09-21", "same_named_section": True,
        "horizontal_reference_verified": HORIZONTAL_REOCCUPATION_VERIFIED,
        "vertical_datum_verified": VERTICAL_DATUM_VERIFIED,
        "reported_x_overlap_min_m": reported_low, "reported_x_overlap_max_m": reported_high,
        "reported_x_overlap_length_m": reported_high - reported_low,
        "overlapping_horizontal_extent_m": np.nan, "bed_elevation_bias_m": np.nan,
        "bed_elevation_mae_m": np.nan, "bed_elevation_rmse_m": np.nan,
        "max_absolute_change_m": np.nan, "approximate_scour_fill_cross_sectional_area_m2": np.nan,
        "horizontal_shift_optimized": False, "vertical_shift_optimized": False,
        "stability_judgment": "insufficient_evidence",
        "reason": "同一水平复测基线与床面垂直基准均未确认；禁止插值比较或任意平移优化",
    }])


def conditional_coverage(predictions: pd.DataFrame, measurements: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, record_rows = [], []
    for candidate_h, label in ((3.85, "source_confirmed_survey_time_stage"), (3.87, "daily_mean_not_geometry_stage")):
        support = []
        for record in predictions.itertuples(index=False):
            train = exclude_held_calendar_month(measurements, int(record.held_month))
            train = train.loc[train.regime.eq(record.regime)]
            stages = train.stage_m.astype(float).tolist()
            if int(record.held_month) != 9:
                stages.append(candidate_h)
            m1_inside = min(stages) <= float(record.stage_m) <= max(stages)
            common = bool(record.M0_global_inside_domain) and m1_inside
            support.append(common)
            if common and not bool(record.common_support):
                record_rows.append({
                    "scenario_stage_m": candidate_h, "scenario_label": label, "date": record.date,
                    "held_month": int(record.held_month), "stage_m": float(record.stage_m), "recovered": True,
                    "admissible_now": False, "reason": "only_if_September_geometry_becomes_verified_mergeable",
                })
        rows.append({
            "scenario_stage_m": candidate_h, "scenario_label": label,
            "stage_semantically_valid_for_section": candidate_h == 3.85,
            "auxiliary_verified_now": False, "admissible_training_now": False,
            "leave_one_calendar_month_out": True, "extrapolation_allowed": False,
            "baseline_common_support_rows": int(predictions.common_support.sum()),
            "conditional_common_support_rows": int(sum(support)),
            "conditional_common_support_coverage": float(np.mean(support)),
            "decision": "conditional_only_not_applied" if candidate_h == 3.85 else "counterfactual_rejected_wrong_stage_semantics",
        })
    return pd.DataFrame(rows), pd.DataFrame(record_rows)


def build_daily_stage_support(daily: pd.DataFrame, measurements: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    domains = measurements.groupby("regime").stage_m.agg(["min", "max"]).to_dict("index")
    rows = []
    for record in daily.itertuples(index=False):
        month = int(record.date.month)
        regime = assign_regime(month)
        low, high = float(domains[regime]["min"]), float(domains[regime]["max"])
        stage = float(record.stage_m)
        inside = low <= stage <= high
        if stage < low:
            direction, distance = "outside_low", low - stage
        elif stage > high:
            direction, distance = "outside_high", stage - high
        else:
            direction, distance = "inside", 0.0
        rows.append({
            "date": record.date.strftime("%Y-%m-%d"), "month": month, "regime": regime, "stage_m": stage,
            "verified_geometry_support_min_m": low, "verified_geometry_support_max_m": high,
            "inside_verified_geometry_support": inside, "support_status": direction,
            "distance_to_support_m": distance, "geometry_label_available": False,
            "used_as_geometry_test_label": False, "used_to_change_d11_gate": False,
            "analysis_role": "descriptive_operational_support_only",
        })
    audit = pd.DataFrame(rows)
    summary = audit.groupby(["month", "regime"], as_index=False).agg(
        days=("date", "size"), stage_min_m=("stage_m", "min"), stage_max_m=("stage_m", "max"),
        inside_days=("inside_verified_geometry_support", "sum"),
        outside_low_days=("support_status", lambda x: int((x == "outside_low").sum())),
        outside_high_days=("support_status", lambda x: int((x == "outside_high").sum())),
    )
    summary["inside_fraction"] = summary.inside_days / summary.days
    return audit, summary


def write_report(stage_recon: pd.DataFrame, conditional: pd.DataFrame, daily_audit: pd.DataFrame) -> None:
    may, sep = stage_recon.iloc[0], stage_recon.iloc[1]
    c385 = conditional.loc[conditional.scenario_stage_m.eq(3.85)].iloc[0]
    daily_inside = int(daily_audit.inside_verified_geometry_support.sum())
    report = f"""# D12A.1 / D12A-VERIFY 中文报告

## 结论摘要

2011-09-21 的 **3.85 m 是大断面施测时的“测时水位”**，3.87 m 是同日的**逐日平均水位**。断面几何在语义上应对应 3.85 m，而不是日平均 3.87 m。但是，现有原始资料没有直接证明大断面表的 28 个河底高程、断面测时水位与逐日水位使用同一垂直基准，也没有证明可以把 2435.565 m 加到断面测时水位后与床面点直接相减。因此 `vertical_datum_verified=false`，两期完整断面几何和河床变化指标均被阻断，9 月资料不能升级为 verified auxiliary geometry，D11 实际 coverage 仍为 12/24，D12B 未启动。

## 1. 2011-09-21 的 3.85 和 3.87 分别是什么

- `Doc1.docx#embedded_image_order_039` 在 2011-09-21 大断面表中明确写“测时水位：3.85m”。
- `Doc1.docx#embedded_image_order_009` 是逐日平均水位表，9 月 21 日为 3.87m。
- 两者相差 -0.02m，不构成矛盾：瞬时/施测时值和日平均值本来可以不同。5 月也呈同样结构：大断面测时水位 {may.section_survey_stage_m:.2f}m，而同日日平均为 {may.daily_mean_stage_m:.2f}m。

## 2. 哪个水位应与断面几何对应

应使用与断面施测同步的测时水位：5 月为 {may.section_survey_stage_m:.2f}m，9 月为 {sep.section_survey_stage_m:.2f}m。日平均水位不能替代断面施测时水位。此选择来自表头语义，而非 D11 coverage 或曲线拟合。垂直基准尚未确认，因此目前不授权计算 verified 几何。

## 3. 床面高程与水位是否同一垂直基准

不能确认。大断面表只给出“河底高程(m)”和“测时水位(m)”，没有说明床面高程基面、BM、水尺零点或两者转换。单位同为米、数值看似可配合，均不是垂直基准的直接证据。禁止通过选择 offset 使面积接近 D11 曲线来反推基准。

## 4. 2435.565 是否可以合法使用

当前不可以。逐日水位表明确说明其表内水位加 2435.565m 可换算到黄海基面；但原始大断面页及相邻页没有证明 28 个床面点也使用黄海基面，亦未证明断面测时水位与逐日表水尺零点相同。

## 5. May 和 September 是否为同一断面

证据支持“名义上同一断面”，但不足以证明严格复占：两期都写“流速仪测流断面（基下3m）”，都由右岸向左岸列点，各 28 点；D11 原24条测流成果也列在基下3m断面。没有绝对桩号/坐标、x=0永久基点、复测控制线或断面迁移记录；两期x网格也不完全相同（5月有56.5m，9月相应点为56.0m）。判为 `nominal_same_section_with_incomplete_reoccupation_control`。

## 6. 两期河床是否存在明显变化

判定为 `insufficient_evidence`。只有同一水平和垂直基准确认后才能计算床面 bias、MAE、RMSE、最大变化和冲淤面积。当前指标均为 NaN；未进行水平或垂直平移优化。CSV 中仅保留原表 x 范围9–60m作为转录事实，不把它冒充已验证的重叠断面范围。

## 7. September 是否可以升级为 verified auxiliary geometry

不可以。日期、断面名称、28点和3.85m测时水位已有直接证据，但垂直基准映射与严格复占证据不足。`verified_mergeable=false`，没有进入训练池。

## 8. 如果未来核验通过，潜在 coverage 是多少

实际 coverage 保持 **12/24**。条件情景：若未来证明9月断面可合法合并，并按原表测时水位H=3.85m加入，同时保持 leave-one-calendar-month-out 和禁止外推，则可恢复 held-May 的 2011-05-10、05-15、05-25、05-26；05-30 H=3.84m仍在域外。潜在 common support 为 **{int(c385.conditional_common_support_rows)}/24 = {c385.conditional_common_support_coverage:.1%}**。这不改变D11 gate。若未来证据改变断面测时H，必须按最终值重算，旧16/24不得保留。以3.87m日平均冒充断面H的反事实情景被拒绝。

## 9. 还缺哪些原始资料

1. 大断面测量说明/原始记录，明确河底高程基面、测时水位水尺零点和二者转换；
2. 基本水尺零点或BM成果，明确2435.565m是否适用于大断面测时水位及床面点；
3. “基下3m”断面的桩号、坐标、x=0永久标志、左右岸方向与复测基线说明；
4. 2011-05至09月断面迁移、冲淤、整治或基准点变动记录；
5. 最好取得两期原始测量手簿/计算表，把测时水位与床面点放在同一垂直基准上。

## 10. 是否满足冻结 D12B 协议的条件

尚不满足。9月辅助断面仍未验证，当前数据不能解决D11支持域不足。`d12b_started=false`。

## 描述性 daily-stage operational support audit

以D11原24条几何的分状态stage全范围作描述性运行支持域：open-water 3.84–5.16m，cold-season 3.65–4.43m。365天中有 {daily_inside}/365 天落在对应状态观测范围。逐日数据只有H，`geometry_label_available=false`，不作为几何测试标签，也不改变D11 gate。

## 科研完整性边界

D11三个冻结文件hash已校验；原24条、12/24 common support、`gate_passed=false`均未改变。不允许外推，不读取逐日流量标签或D9B残差参数，不修改季节定义，不启动D12B。
"""
    (OUT / "stage_d12a1_verification_report_zh.md").write_text(report, encoding="utf-8")


def main() -> None:
    assert_frozen_d11()
    OUT.mkdir(parents=True, exist_ok=True)
    points, daily, measurements = load_byblk_points(), load_daily_stage(), load_geometry_measurements()
    predictions = pd.read_csv(D11_PREDICTIONS)
    evidence = build_source_evidence_manifest()
    stage_recon = build_stage_reconciliation(points, daily)
    datum = build_vertical_datum_audit()
    identity = build_section_identity_audit(points)
    mergeability = build_auxiliary_mergeability_decision()
    stability = build_bed_stability_audit(points)
    conditional, recovered = conditional_coverage(predictions, measurements)
    daily_audit, daily_summary = build_daily_stage_support(daily, measurements)
    for frame, name in [
        (evidence, "source_evidence_manifest.csv"), (stage_recon, "stage_value_reconciliation.csv"),
        (datum, "vertical_datum_audit.csv"), (identity, "section_identity_audit.csv"),
        (mergeability, "auxiliary_mergeability_decision.csv"),
        (stability, "bed_stability_audit.csv"), (conditional, "conditional_coverage_simulation.csv"),
        (recovered, "conditional_recovered_records.csv"), (daily_audit, "daily_stage_support_audit.csv"),
        (daily_summary, "daily_stage_support_monthly_summary.csv"),
    ]:
        frame.to_csv(OUT / name, index=False, encoding="utf-8-sig")
    write_blocked_geometry(points, "2011-05-21")
    write_blocked_geometry(points, "2011-09-21")
    write_report(stage_recon, conditional, daily_audit)
    result = {
        "stage": "D12A.1 / D12A-VERIFY", "status": "completed_verification_auxiliary_rejected",
        "d11_hashes": {name: sha256(D11 / name) for name in EXPECTED_D11_HASHES},
        "doc1_sha256": sha256(DOC1), "d11_gate_passed": False, "d11_measurement_rows": 24,
        "d11_common_support_rows": 12, "d11_common_support_coverage": 0.5,
        "september_survey_stage_m": 3.85, "september_daily_mean_stage_m": 3.87,
        "stage_semantics_reconciled": True, "vertical_datum_verified": VERTICAL_DATUM_VERIFIED,
        "horizontal_reoccupation_verified": HORIZONTAL_REOCCUPATION_VERIFIED,
        "z_water_offset_2435_565_allowed_for_section": False,
        "section_identity_status": "nominal_same_section_with_incomplete_reoccupation_control",
        "bed_stability_status": "insufficient_evidence", "september_verified_auxiliary_geometry": False,
        "september_verified_mergeable": False,
        "verified_auxiliary_training_rows_added": 0, "actual_common_support_after_verification": "12/24",
        "conditional_common_support_if_3_85_verified": "16/24", "extrapolation_allowed": EXTRAPOLATION_ALLOWED,
        "leave_one_calendar_month_out": True, "daily_stage_geometry_labels": 0,
        "daily_stage_role": "descriptive_operational_support_only",
        "season_definition": {"open_water_months": sorted(OPEN_MONTHS), "cold_season_months": [11, 12, 1, 2, 3]},
        "d12b_started": False,
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
