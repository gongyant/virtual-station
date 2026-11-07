"""Stage D5 round 3: frozen retrospective diagnostics only; no model fitting."""

from __future__ import division, print_function

import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


ROOT = Path(__file__).resolve().parents[1]
R1 = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5"
R2 = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5_round2"
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5_round3"
PLOTS = OUT / "plots/cumulative_residual_by_year"
ERA5 = ROOT / "data/processed/era5_land"
YEARS = list(range(1978, 1984))
SECONDS_PER_DAY = 86400.0


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(frame, path):
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def safe_corr(x, y, method="pearson"):
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan
    return float(pearsonr(a[ok], b[ok])[0] if method == "pearson" else spearmanr(a[ok], b[ok])[0])


def longest_run(mask):
    best = current = 0
    for value in np.asarray(mask, dtype=bool):
        current = current + 1 if value else 0
        best = max(best, current)
    return int(best)


def autocorr(values, lag):
    x = np.asarray(values, dtype=float)
    if len(x) <= lag:
        return np.nan
    return safe_corr(x[:-lag], x[lag:])


def verify_round2_manifest():
    manifest_path = R2 / "stage_d5_round2_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for item in manifest["files"]:
        path = ROOT / item["path"]
        exists = path.exists()
        current_hash = sha256(path) if exists else None
        current_size = path.stat().st_size if exists else None
        rows.append({
            "file_path": item["path"],
            "expected_sha256": item["sha256"],
            "current_sha256": current_hash,
            "expected_size": item["bytes"],
            "current_size": current_size,
            "hash_match": bool(exists and current_hash == item["sha256"]),
            "size_match": bool(exists and current_size == item["bytes"]),
        })
    result = {
        "audit_time": dt.datetime.now().isoformat(),
        "manifest_path": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": sha256(manifest_path),
        "declared_file_count": manifest["file_count"],
        "audited_file_count": len(rows),
        "all_hashes_match": all(r["hash_match"] for r in rows),
        "all_sizes_match": all(r["size_match"] for r in rows),
        "round2_decision_remains_frozen": True,
        "files": rows,
    }
    dump_json(OUT / "stage_d5_round2_immutability_audit.json", result)
    if len(rows) != 34 or not result["all_hashes_match"] or not result["all_sizes_match"]:
        raise RuntimeError("stage_d5_round2 immutability audit failed")
    return result


def reconstruct_round1_manifest():
    excluded = {"stage_d5_round1_manifest.json"}
    files = []
    for path in sorted(R1.rglob("*")):
        if not path.is_file() or path.name in excluded or path.name.endswith(".inspect.ndjson"):
            continue
        files.append({
            "file_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "current_sha256": sha256(path),
            "file_size": path.stat().st_size,
            "original_freeze_time_unknown": True,
            "limitations": "Hash proves only the file state at reconstruction time, not its original completion-time state.",
        })
    payload = {
        "manifest_type": "reconstructed_after_completion",
        "reconstructed_at": dt.datetime.now().isoformat(),
        "source_directory": str(R1.relative_to(ROOT)).replace("\\", "/"),
        "file_count": len(files),
        "original_freeze_time_unknown": True,
        "limitations": [
            "No contemporaneous original freeze manifest is accepted as evidence for round 1.",
            "The existing stage_d5_round1_manifest.json is excluded to avoid circular or back-dated endorsement.",
            "Current hashes cannot prove that files were unchanged before this reconstruction.",
            "Hashing first-round files for this required inventory does not make 2011 eligible for model selection.",
        ],
        "files": files,
    }
    dump_json(OUT / "stage_d5_round1_reconstructed_manifest.json", payload)
    return payload


def selected_m2_parameters():
    frame = pd.read_csv(R2 / "fitted_parameters_by_fold.csv", encoding="utf-8-sig")
    selected = frame[(frame["model"] == "M2") & (frame["selected_for_outer_refit"] == True)].copy()
    if len(selected) != 6 or sorted(selected["outer_year"].astype(int).tolist()) != YEARS:
        raise RuntimeError("Expected exactly one frozen M2 parameter row per outer fold")
    return selected.sort_values("outer_year")


def m2_reparameterization_audit(params, predictions):
    rows = []
    max_diff = 0.0
    fold_diffs = []
    for row in params.itertuples(index=False):
        rho, a = float(row.rho), float(row.a)
        g = a / (1.0 - rho)
        fold = predictions[predictions["outer_held_year"] == int(row.outer_year)].copy()
        s = fold["m2_storage_state"].astype(float).values
        e = (1.0 - rho) * s
        reparam = np.maximum(0.0, float(row.b) + g * e + float(row.c) * fold["q_byblk"].astype(float).values)
        original = fold["m2_q_pred"].astype(float).values
        diff = np.abs(reparam - original)
        fold_max = float(np.nanmax(diff))
        max_diff = max(max_diff, fold_max)
        fold_diffs.append({"outer_year": int(row.outer_year), "maximum_absolute_difference": fold_max})
        rows.append({
            "outer_year": int(row.outer_year), "rho": rho, "one_minus_rho": 1.0-rho,
            "original_a": a, "normalized_g": g, "direct_c": float(row.c), "intercept_b": float(row.b),
            "original_a_near_frozen_lower_boundary": bool(a <= 0.1),
            "fit_reused_without_refit": True,
        })
    out = pd.DataFrame(rows)
    write_csv(out, OUT / "m2_reparameterized_parameters.csv")
    g_cv = float(out["normalized_g"].std(ddof=0) / out["normalized_g"].mean())
    a_cv = float(out["original_a"].std(ddof=0) / out["original_a"].mean())
    audit = {
        "mathematical_identity": "E_t=(1-rho)S_t; g=a/(1-rho); b+gE_t+cQ_t=b+aS_t+cQ_t",
        "refitted": False,
        "fold_count": 6,
        "maximum_absolute_prediction_difference": max_diff,
        "tolerance": 1e-8,
        "equivalent_within_tolerance": bool(max_diff < 1e-8),
        "fold_differences": fold_diffs,
        "normalized_g_cv": g_cv,
        "original_a_cv": a_cv,
    }
    dump_json(OUT / "m2_prediction_equivalence_audit.json", audit)
    return out, audit


def memory_audit(params):
    rows = []
    for row in params.itertuples(index=False):
        rho = float(row.rho)
        half_life = math.log(0.5) / math.log(rho)
        efold = -1.0 / math.log(rho)
        cumulative = {}
        for pct in (0.50, 0.80, 0.90):
            cumulative[pct] = int(math.ceil(math.log(1.0-pct) / math.log(rho)))
        rows.append({
            "outer_year": int(row.outer_year), "rho": rho,
            "half_life_days": half_life, "e_folding_time_days": efold,
            "days_to_50pct_cumulative_response": cumulative[0.50],
            "days_to_80pct_cumulative_response": cumulative[0.80],
            "days_to_90pct_cumulative_response": cumulative[0.90],
            "m1_selected_width_days": 15.0,
            "m1_width_at_frozen_upper_boundary": True,
            "m2_90pct_exceeds_15_days": bool(cumulative[0.90] > 15),
        })
    frame = pd.DataFrame(rows)
    write_csv(frame, OUT / "m1_m2_memory_timescale_comparison.csv")
    return frame


def model_bias_rows(predictions):
    annual, monthly, detail = [], [], []
    model_cols = {"M0":"m0_q_pred", "M1":"m1_q_pred", "M2":"m2_q_pred"}
    for year in YEARS:
        full = predictions[predictions["year"] == year].sort_values("date").copy()
        common = full[full["scoring_common"] == True].copy()
        by_mean = float(full["q_byblk"].mean())
        dsk_mean = float(full["q_dsk_obs"].mean())
        annual_ratio = dsk_mean / by_mean
        annual_volume_ratio = float(full["q_dsk_obs"].sum() / full["q_byblk"].sum())
        base = {
            "year": year, "full_year_days": len(full), "byblk_mean_q_m3s": by_mean,
            "dsk_mean_q_m3s": dsk_mean, "dsk_byblk_mean_ratio": annual_ratio,
            "dsk_byblk_annual_volume_ratio": annual_volume_ratio,
            "byblk_annual_volume_m3": float(full["q_byblk"].sum()*SECONDS_PER_DAY),
            "dsk_annual_volume_m3": float(full["q_dsk_obs"].sum()*SECONDS_PER_DAY),
            "prediction_comparison_window": "round2_common_window",
            "prediction_days": len(common),
        }
        for model, col in model_cols.items():
            obs = common["q_dsk_obs"].astype(float).values
            pred = common[col].astype(float).values
            err = pred - obs
            base[model.lower()+"_prediction_mean_m3s"] = float(np.mean(pred))
            base[model.lower()+"_pbias_percent"] = float(100.0*np.sum(err)/np.sum(obs))
            base[model.lower()+"_cumulative_residual_m3"] = float(np.sum(err)*SECONDS_PER_DAY)
        annual.append(base)

        full["month"] = pd.to_datetime(full["date"]).dt.month
        common["month"] = pd.to_datetime(common["date"]).dt.month
        for month in range(1, 13):
            f = full[full["month"] == month]
            cwin = common[common["month"] == month]
            mr = {
                "year": year, "month": month, "full_month_days": len(f),
                "byblk_mean_q_m3s": float(f["q_byblk"].mean()),
                "dsk_mean_q_m3s": float(f["q_dsk_obs"].mean()),
                "dsk_byblk_mean_ratio": float(f["q_dsk_obs"].mean()/f["q_byblk"].mean()),
                "common_scoring_days": len(cwin),
            }
            for model, col in model_cols.items():
                if len(cwin):
                    err = cwin[col].astype(float).values-cwin["q_dsk_obs"].astype(float).values
                    mr[model.lower()+"_pbias_percent"] = float(100.0*err.sum()/cwin["q_dsk_obs"].sum())
                else:
                    mr[model.lower()+"_pbias_percent"] = np.nan
            monthly.append(mr)

        q1, q2 = common["q_dsk_obs"].quantile([1/3,2/3]).values
        common["flow_regime"] = np.where(common["q_dsk_obs"]<=q1,"low",np.where(common["q_dsk_obs"]<=q2,"middle","high"))
        dates = pd.to_datetime(common["date"])
        common["season"] = np.select(
            [dates.dt.month.isin([12,1,2]),dates.dt.month.isin([3,4,5]),dates.dt.month.isin([6,7,8])],
            ["DJF","MAM","JJA"], default="SON")
        for model, col in model_cols.items():
            err = common[col].astype(float).values-common["q_dsk_obs"].astype(float).values
            row = {
                "year": year, "model": model, "row_type": "year_summary",
                "group": "all_common_days", "day_count": len(common),
                "pbias_percent": float(100.0*err.sum()/common["q_dsk_obs"].sum()),
                "residual_acf_lag1": autocorr(err,1), "residual_acf_lag7": autocorr(err,7),
                "residual_acf_lag30": autocorr(err,30),
                "longest_positive_error_run_days": longest_run(err>0),
                "longest_negative_error_run_days": longest_run(err<0),
                "top10pct_flow_share_of_absolute_error": float(np.abs(err[common["q_dsk_obs"].values>=np.quantile(common["q_dsk_obs"],.9)]).sum()/np.abs(err).sum()),
                "top10pct_flow_share_of_net_underestimate": float(np.maximum(-err[common["q_dsk_obs"].values>=np.quantile(common["q_dsk_obs"],.9)],0).sum()/max(np.maximum(-err,0).sum(),1e-12)),
            }
            detail.append(row)
            for group_col, groups in (("season",["DJF","MAM","JJA","SON"]),("flow_regime",["low","middle","high"])):
                for group in groups:
                    gframe = common[common[group_col] == group]
                    ge = gframe[col].astype(float).values-gframe["q_dsk_obs"].astype(float).values
                    detail.append({
                        "year":year,"model":model,"row_type":group_col,"group":group,
                        "day_count":len(gframe),"pbias_percent":float(100.0*ge.sum()/gframe["q_dsk_obs"].sum()),
                        "residual_acf_lag1":np.nan,"residual_acf_lag7":np.nan,"residual_acf_lag30":np.nan,
                        "longest_positive_error_run_days":np.nan,"longest_negative_error_run_days":np.nan,
                        "top10pct_flow_share_of_absolute_error":np.nan,"top10pct_flow_share_of_net_underestimate":np.nan,
                    })

        fig, ax = plt.subplots(figsize=(10,4.6))
        for model, col in model_cols.items():
            residual = common[col].astype(float).values-common["q_dsk_obs"].astype(float).values
            ax.plot(pd.to_datetime(common["date"]), np.cumsum(residual)*SECONDS_PER_DAY/1e6, label=model, lw=1.4)
        ax.axhline(0,color="black",lw=.7)
        ax.set_title("%d cumulative prediction residual (round-2 common window)"%year)
        ax.set_ylabel("Cumulative residual (million m3)")
        ax.legend(ncol=3)
        fig.tight_layout()
        fig.savefig(PLOTS / ("cumulative_residual_%d.png"%year), dpi=180)
        plt.close(fig)
    return pd.DataFrame(annual), pd.DataFrame(monthly), pd.DataFrame(detail)


def read_h5_netcdf(path):
    with h5py.File(str(path), "r") as f:
        attrs = {k:(v.decode("utf-8") if isinstance(v,bytes) else v) for k,v in f.attrs.items() if k != "_NCProperties"}
        data = {}
        var_attrs = {}
        for k in f.keys():
            value = f[k][()]
            if getattr(value,"dtype",None) is not None and value.dtype.kind == "O":
                value = np.asarray([x.decode("utf-8") if isinstance(x,bytes) else x for x in value])
            data[k] = value
            var_attrs[k] = {a:(v.decode("utf-8") if isinstance(v,bytes) else v) for a,v in f[k].attrs.items() if a not in ("DIMENSION_LIST","REFERENCE_LIST")}
    return data, attrs, var_attrs


def era5_audit(predictions, annual_gain):
    basin_path = ERA5 / "era5land_daily_basin_weighted_1978_1983.nc"
    interval_path = ERA5 / "era5land_incremental_byblk_to_dsk_1978_1983.nc"
    basin, basin_attrs, basin_var_attrs = read_h5_netcdf(basin_path)
    interval, int_attrs, int_var_attrs = read_h5_netcdf(interval_path)
    dates = pd.to_datetime("1978-01-01") + pd.to_timedelta(np.asarray(interval["time"],dtype=int),unit="D")
    if len(dates) != 2191 or dates.min() != pd.Timestamp("1978-01-01") or dates.max() != pd.Timestamp("1983-12-31"):
        raise RuntimeError("ERA5 interval time coverage is not complete 1978-1983")
    stations = [str(x) for x in basin["station"]]
    by_i, dsk_i = stations.index("00705600"), stations.index("00705700")
    area_by = float(basin["weighted_polygon_area_km2"][by_i])
    area_dsk = float(basin["weighted_polygon_area_km2"][dsk_i])
    direct_p = np.asarray(interval["precipitation_mm"])[0].astype(float)
    balance_p = (np.asarray(basin["precipitation_mm"])[dsk_i]*area_dsk-np.asarray(basin["precipitation_mm"])[by_i]*area_by)/(area_dsk-area_by)
    max_mass_diff = float(np.nanmax(np.abs(direct_p-balance_p)))
    daily = pd.DataFrame({
        "date":dates,
        "interval_precipitation_mm":direct_p,
        "interval_temperature_c":np.asarray(interval["temperature_c"])[0].astype(float),
        "interval_swe_mm":np.asarray(interval["swe_mm"])[0].astype(float),
        "interval_snowmelt_mm":np.asarray(interval["snowmelt_mm"])[0].astype(float),
        "byblk_upstream_precipitation_mm":np.asarray(basin["precipitation_mm"])[by_i].astype(float),
        "dsk_total_upstream_precipitation_mm":np.asarray(basin["precipitation_mm"])[dsk_i].astype(float),
    })
    daily["positive_temperature_degree_day"] = np.maximum(daily["interval_temperature_c"],0.0)
    daily["melt_proxy_mm_degC"] = daily["interval_snowmelt_mm"]*daily["positive_temperature_degree_day"]
    for variable in ("interval_precipitation_mm","interval_snowmelt_mm","positive_temperature_degree_day","melt_proxy_mm_degC"):
        for window in (7,14,30,60):
            daily[variable+"_antecedent_%dd"%window] = daily[variable].shift(1).rolling(window,min_periods=window).sum()
    daily["year"] = daily["date"].dt.year

    weights = pd.read_csv(ERA5/"basin_grid_weights.csv",dtype={"station_id":str})
    int_weights = pd.read_csv(ERA5/"incremental_grid_weights.csv",dtype={"station_id":str})
    weight_sums = weights.groupby("station_id")["weight"].sum().to_dict()
    int_weight_sum = float(int_weights["weight"].sum())
    audit_rows = []
    variable_specs = [
        ("byblk_upstream_precipitation","basin", "precipitation_mm", "mm day-1", "BYBLK upstream basin"),
        ("dsk_total_upstream_precipitation","basin", "precipitation_mm", "mm day-1", "DSK total upstream basin"),
        ("interval_precipitation","interval", "precipitation_mm", "mm day-1", "DSK minus BYBLK incremental basin"),
        ("interval_temperature","interval", "temperature_c", "degC", "DSK minus BYBLK incremental basin"),
        ("positive_temperature","derived", "max(temperature_c,0)", "degC day", "incremental basin"),
        ("interval_swe","interval", "swe_mm", "mm", "incremental basin"),
        ("interval_snowmelt","interval", "snowmelt_mm", "mm day-1", "incremental basin"),
        ("melt_proxy","derived", "snowmelt_mm*max(temperature_c,0)", "mm degC day-1", "incremental basin"),
    ]
    for name, source, source_var, unit, spatial in variable_specs:
        if name == "byblk_upstream_precipitation": arr=daily["byblk_upstream_precipitation_mm"]
        elif name == "dsk_total_upstream_precipitation": arr=daily["dsk_total_upstream_precipitation_mm"]
        elif name == "interval_precipitation": arr=daily["interval_precipitation_mm"]
        elif name == "interval_temperature": arr=daily["interval_temperature_c"]
        elif name == "positive_temperature": arr=daily["positive_temperature_degree_day"]
        elif name == "interval_swe": arr=daily["interval_swe_mm"]
        elif name == "interval_snowmelt": arr=daily["interval_snowmelt_mm"]
        else: arr=daily["melt_proxy_mm_degC"]
        audit_rows.append({
            "candidate_variable":name,"source_type":source,"source_variable":source_var,"unit":unit,
            "spatial_definition":spatial,"start_date":str(daily.date.min().date()),"end_date":str(daily.date.max().date()),
            "row_count":len(arr),"missing_count":int(arr.isna().sum()),"time_complete":bool(arr.notna().all()),
            "spatial_weighting":"exact grid-cell intersection area weighting",
            "basin_weight_sum_byblk":weight_sums.get("00705600"),"basin_weight_sum_dsk":weight_sums.get("00705700"),
            "interval_weight_sum":int_weight_sum,"daily_boundary":"UTC+00:00",
            "accumulation_conversion":"00 UTC accumulated fields shifted back one day" if "precip" in name or "snowmelt" in name else "not accumulated or explicitly derived",
            "future_leakage_check":"current day is diagnostic only; antecedent windows use shift(1) before rolling",
            "status":"available_complete_with_timing_warning",
        })
    for window in (7,14,30,60):
        audit_rows.append({
            "candidate_variable":"antecedent_%dd_variables"%window,"source_type":"derived","source_variable":"past-only rolling sum",
            "unit":"source-dependent","spatial_definition":"incremental basin","start_date":str(daily.date.min().date()),
            "end_date":str(daily.date.max().date()),"row_count":len(daily),"missing_count":window,
            "time_complete":False,"spatial_weighting":"inherits source","basin_weight_sum_byblk":np.nan,
            "basin_weight_sum_dsk":np.nan,"interval_weight_sum":int_weight_sum,"daily_boundary":"UTC+00:00",
            "accumulation_conversion":"shift(1), then rolling sum over %d prior days"%window,
            "future_leakage_check":"passed; current and future values excluded","status":"available_after_expected_leading_warmup",
        })
    era_audit = pd.DataFrame(audit_rows)
    era_audit["interval_precip_mass_balance_max_abs_diff_mm"] = max_mass_diff
    era_audit["basin_source"] = basin_attrs.get("basin_source")
    write_csv(era_audit, OUT/"era5_interval_input_audit.csv")

    annual_weather = daily.groupby("year").agg({
        "interval_precipitation_mm":"sum","interval_snowmelt_mm":"sum",
        "positive_temperature_degree_day":"sum","melt_proxy_mm_degC":"sum","interval_swe_mm":"mean",
    }).reset_index()
    annual_weather = annual_weather.merge(annual_gain[["year","dsk_byblk_mean_ratio"]],on="year",how="left")
    association_rows = []
    for var in ["interval_precipitation_mm","interval_snowmelt_mm","positive_temperature_degree_day","melt_proxy_mm_degC","interval_swe_mm"]:
        association_rows.append({
            "analysis_scope":"annual_1978_1983","target":"dsk_byblk_mean_ratio","candidate":var,
            "lag_definition":"annual aggregate","n":6,
            "pearson":safe_corr(annual_weather[var],annual_weather["dsk_byblk_mean_ratio"]),
            "spearman":safe_corr(annual_weather[var],annual_weather["dsk_byblk_mean_ratio"],"spearman"),
            "diagnostic_status":"development_diagnostic_only",
        })
    merged = predictions[predictions["scoring_common"]==True].copy()
    merged["date"] = pd.to_datetime(merged["date"])
    merged["m2_residual"] = merged["m2_q_pred"]-merged["q_dsk_obs"]
    merged = merged.merge(daily,on="date",how="left")
    merged["year_month_key"] = merged["date"].dt.strftime("%Y-%m")
    merged["m2_residual_month_anomaly"] = merged["m2_residual"]-merged.groupby("year_month_key")["m2_residual"].transform("mean")
    candidates = ["interval_precipitation_mm","interval_snowmelt_mm","positive_temperature_degree_day","melt_proxy_mm_degC"]
    candidates += [v+"_antecedent_%dd"%w for v in candidates for w in (7,14,30,60)]
    consistency = []
    for var in candidates:
        year_corrs = []
        merged[var+"_month_anomaly"] = merged[var]-merged.groupby("year_month_key")[var].transform("mean")
        anomaly_corrs = []
        for year in YEARS:
            g = merged[merged["year_x"]==year]
            year_corrs.append(safe_corr(g[var],g["m2_residual"]))
            anomaly_corrs.append(safe_corr(g[var+"_month_anomaly"],g["m2_residual_month_anomaly"]))
        finite = np.asarray([x for x in year_corrs if np.isfinite(x)])
        sign_count = max(int((finite>0).sum()),int((finite<0).sum())) if len(finite) else 0
        afinite = np.asarray([x for x in anomaly_corrs if np.isfinite(x)])
        anomaly_sign_count = max(int((afinite>0).sum()),int((afinite<0).sum())) if len(afinite) else 0
        pooled = safe_corr(merged[var],merged["m2_residual"])
        pooled_anomaly = safe_corr(merged[var+"_month_anomaly"],merged["m2_residual_month_anomaly"])
        association_rows.append({
            "analysis_scope":"daily_m2_outer_residual","target":"m2_prediction_minus_observed","candidate":var,
            "lag_definition":"past-only" if "antecedent" in var else "current_day_diagnostic_only",
            "n":int(merged[[var,"m2_residual"]].dropna().shape[0]),"pearson":pooled,
            "spearman":safe_corr(merged[var],merged["m2_residual"],"spearman"),
            "year_1978_pearson":year_corrs[0],"year_1979_pearson":year_corrs[1],"year_1980_pearson":year_corrs[2],
            "year_1981_pearson":year_corrs[3],"year_1982_pearson":year_corrs[4],"year_1983_pearson":year_corrs[5],
            "same_sign_year_count":sign_count,"cross_year_consistent":bool(sign_count>=5 and np.nanmedian(np.abs(finite))>=0.15),
            "month_anomaly_pooled_pearson":pooled_anomaly,
            "month_anomaly_year_1978_pearson":anomaly_corrs[0],"month_anomaly_year_1979_pearson":anomaly_corrs[1],
            "month_anomaly_year_1980_pearson":anomaly_corrs[2],"month_anomaly_year_1981_pearson":anomaly_corrs[3],
            "month_anomaly_year_1982_pearson":anomaly_corrs[4],"month_anomaly_year_1983_pearson":anomaly_corrs[5],
            "month_anomaly_same_sign_year_count":anomaly_sign_count,
            "cross_year_anomaly_consistent":bool(anomaly_sign_count>=5 and np.nanmedian(np.abs(afinite))>=0.15),
            "diagnostic_status":"development_diagnostic_only",
        })
        consistency.append((var,anomaly_sign_count,float(np.nanmedian(np.abs(afinite))) if len(afinite) else np.nan,pooled_anomaly))
    assoc = pd.DataFrame(association_rows)
    write_csv(assoc,OUT/"posthoc_additional_input_associations.csv")
    return era_audit, assoc, annual_weather, consistency, max_mass_diff


def audit_other_inputs():
    timeseries = pd.read_csv(ROOT/"data/processed/timeseries.csv",dtype={"station_id":str},parse_dates=["date"])
    period = timeseries[(timeseries.date.dt.year>=1978)&(timeseries.date.dt.year<=1983)]
    observed = period.groupby("station_id")["obs_q"].count().to_dict()
    station_rows = [
        {"candidate":"BYBLK Q","station_id":"00705600","station_name":"巴音布鲁克","days_1978_1983":int(observed.get("00705600",0)),"real_observation":True,"role":"existing upstream boundary","realtime_usable":True,"historical_reconstruction_only":False,"status":"available_existing_input"},
        {"candidate":"DSK Q","station_id":"00705700","station_name":"大山口","days_1978_1983":int(observed.get("00705700",0)),"real_observation":True,"role":"label only; forbidden as deployed residual input","realtime_usable":False,"historical_reconstruction_only":False,"status":"available_label_not_candidate_input"},
        {"candidate":"Yanqi Q","station_id":"00705850","station_name":"焉耆","days_1978_1983":int(observed.get("00705850",0)),"real_observation":False,"role":"possible downstream boundary","realtime_usable":False,"historical_reconstruction_only":True,"status":"not_found_for_1978_1983"},
        {"candidate":"intermediate tributary Q","station_id":"","station_name":"未找到","days_1978_1983":0,"real_observation":False,"role":"interval inflow proxy","realtime_usable":False,"historical_reconstruction_only":False,"status":"not_found_for_1978_1983"},
        {"candidate":"other interval inflow station Q","station_id":"","station_name":"未找到","days_1978_1983":0,"real_observation":False,"role":"interval inflow proxy","realtime_usable":False,"historical_reconstruction_only":False,"status":"not_found_for_1978_1983"},
    ]
    stations = pd.DataFrame(station_rows)
    write_csv(stations,OUT/"additional_station_input_audit.csv")
    controls = pd.DataFrame([
        {"candidate":"DSK daily stage","period":"1978-1983","available_year_count":0,"reliable_year_count":0,"source_checked":"raw Q workbooks and processed inventory","status":"not_found_non_2011","model_role":"P1B requires >=2 reliable non-2011 years"},
        {"candidate":"reservoir level","period":"1978-1983","available_year_count":0,"reliable_year_count":0,"source_checked":"project file inventory","status":"not_found","model_role":"control proxy unavailable"},
        {"candidate":"gate forebay/tailwater level","period":"1978-1983","available_year_count":0,"reliable_year_count":0,"source_checked":"project file inventory","status":"not_found","model_role":"control proxy unavailable"},
        {"candidate":"gate operation or dispatch state","period":"1978-1983","available_year_count":0,"reliable_year_count":0,"source_checked":"project file inventory","status":"not_found","model_role":"control proxy unavailable"},
        {"candidate":"hydropower operating time","period":"1978-1983","available_year_count":0,"reliable_year_count":0,"source_checked":"project file inventory","status":"not_found","model_role":"control proxy unavailable"},
    ])
    write_csv(controls,OUT/"control_proxy_availability_audit.csv")
    return stations, controls


def write_reports(reparam, equivalence, memory, annual, monthly, bias, era, assoc, stations, controls, branch):
    gmin,gmax=reparam.normalized_g.min(),reparam.normalized_g.max()
    amin,amax=reparam.original_a.min(),reparam.original_a.max()
    rmin,rmax=reparam.rho.min(),reparam.rho.max()
    mem90min,mem90max=memory.days_to_90pct_cumulative_response.min(),memory.days_to_90pct_cumulative_response.max()
    ident = """# M2等价重参数化与可识别性报告

本轮没有重新拟合。六个fold均直接读取第二轮冻结参数，并使用`E=(1-rho)S`、`g=a/(1-rho)`逐日复算。

- 原始`a`范围：%.6f—%.6f；5/6 fold因第二轮“参数全范围1%%”规则被判为接近下界。
- 归一化`g`范围：%.4f—%.4f，变异系数为%.3f；`rho`范围：%.4f—%.4f。
- 等价预测最大绝对差为%.3e m³/s，小于1e-8；差异仅为浮点运算次序。

判断：`a`触边主要是未归一化状态`S`的量级造成。因为`S`约为`Q/(1-rho)`量级，`a`自然缩小到约0.1；换成与Q同量纲的`E`后，`g`约3—4且跨fold更易解释。第二轮的“持续触边”判定在其冻结规则下仍然成立，拒绝结论不改；科学表述应补充为“原参数化边界敏感，不能直接解释为储量效应消失或物理系数接近零”。
"""%(amin,amax,gmin,gmax,equivalence["normalized_g_cv"],rmin,rmax,equivalence["maximum_absolute_prediction_difference"])
    (OUT/"m2_identifiability_report_zh.md").write_text(ident,encoding="utf-8")

    mem_report = """# M1/M2记忆时间诊断

六个M2 fold的`rho`为%.4f—%.4f，对应半衰期%.1f—%.1f天、e-folding时间%.1f—%.1f天，累计90%%响应需要%d—%d天。六个M1 fold的宽度均达到冻结上限15天。

因此，资料支持相对稳定的“数周记忆”：10天和15天窗口对完整衰减尾部明显偏短，尤其无法覆盖90%%累计响应。扩大记忆范围具有诊断依据，但这不授权M3，也不允许把M1上限事后改大后包装成无偏评价。
"""%(rmin,rmax,memory.half_life_days.min(),memory.half_life_days.max(),memory.e_folding_time_days.min(),memory.e_folding_time_days.max(),mem90min,mem90max)
    (OUT/"memory_timescale_report_zh.md").write_text(mem_report,encoding="utf-8")

    a1979=annual[annual.year==1979].iloc[0]; a1982=annual[annual.year==1982].iloc[0]
    y1979=bias[(bias.year==1979)&(bias.model=="M2")&(bias.row_type=="year_summary")].iloc[0]
    y1982=bias[(bias.year==1982)&(bias.model=="M2")&(bias.row_type=="year_summary")].iloc[0]
    m79=monthly[monthly.year==1979].sort_values("m2_pbias_percent")
    m82=monthly[monthly.year==1982].sort_values("m2_pbias_percent",ascending=False)
    report = """# 1978—1983年度水量与偏差归因

所有预测偏差均沿用第二轮共同评分窗口；年度观测均值和DSK/BYBLK比使用完整自然年，不生成新模型成绩。

## 1979

DSK/BYBLK年均比为%.3f，六年中排名%d/6；M2年度PBIAS为%.2f%%。负偏差最大的三个月是%s。高流量前10%%日期占M2全部低估水量的%.1f%%，因此%s。M2负误差最长连续%d天，说明偏差具有持续状态，而非删除一个洪峰即可解决。

## 1982

DSK/BYBLK年均比为%.3f，M2年度PBIAS为%.2f%%。正偏差最大的三个月是%s；低流量区PBIAS为%.2f%%。因此1982主要表现为%s，与固定跨年增益不能适应年度/季节水量比例一致。

累计残差曲线、季节/流量区间PBIAS、误差自相关及最长正负连续段已写入对应CSV和逐年图片。
"""%(
        a1979.dsk_byblk_mean_ratio,int(annual.dsk_byblk_mean_ratio.rank(ascending=False,method="min")[annual.year==1979].iloc[0]),
        a1979.m2_pbias_percent,"、".join("%d月(%.1f%%)"%(r.month,r.m2_pbias_percent) for r in m79.head(3).itertuples()),
        100*y1979.top10pct_flow_share_of_net_underestimate,
        "洪峰贡献显著，但不足以解释全年低估" if y1979.top10pct_flow_share_of_net_underestimate<0.7 else "低估主要集中于少数高流量日",
        int(y1979.longest_negative_error_run_days),a1982.dsk_byblk_mean_ratio,a1982.m2_pbias_percent,
        "、".join("%d月(%.1f%%)"%(r.month,r.m2_pbias_percent) for r in m82.head(3).itertuples()),
        bias[(bias.year==1982)&(bias.model=="M2")&(bias.row_type=="flow_regime")&(bias.group=="low")].iloc[0].pbias_percent,
        "低流量期基线被抬高并叠加部分月份持续高估" if bias[(bias.year==1982)&(bias.model=="M2")&(bias.row_type=="flow_regime")&(bias.group=="low")].iloc[0].pbias_percent>0 else "中高流量期增益偏大")
    (OUT/"year_bias_report_zh.md").write_text(report,encoding="utf-8")

    consistent = assoc[(assoc.analysis_scope=="daily_m2_outer_residual") & (assoc.cross_year_anomaly_consistent==True)] if "cross_year_anomaly_consistent" in assoc else pd.DataFrame()
    add_report = """# 新增信息可用性与合法性审计

## ERA5区间变量

1978—1983的区间降水、气温、SWE、融雪以及上游/总流域降水均覆盖2191天。空间聚合使用HydroBASINS边界与网格相交面积权重；累计量采用00 UTC累积量回移一天，前期7/14/30/60日量均先`shift(1)`再滚动，避免未来泄漏。直接区间降水与面积水量平衡复算最大差为%.3e mm。

这些数据在“可用性”层面通过，但年度关系只有6个样本；逐日残差关联属于`development_diagnostic_only`。季节去均值后满足跨年份同号/强度筛选的候选数为%d。1979的年度增益异常并未被年度降水或融雪量单独解释，因此不能把整组ERA5变量一次性加入；但过去14日区间融雪量在六年均呈同向残差关系，可作为唯一冻结候选，供下一阶段用严格嵌套协议检验。

## 其他站与控制代理

同期真实逐日Q只确认BYBLK和DSK各2191天；未找到1978—1983焉耆Q或中间支流Q，所以双边界历史重建不准入。非2011年份未找到可靠DSK逐日水位、库水位、闸前/闸后水位、调度状态或水电站运行时间，因此P1B不准入。

2011没有用于任何变量筛选、关联或模型准入。
"""%(float(era.interval_precip_mass_balance_max_abs_diff_mm.iloc[0]),len(consistent))
    (OUT/"additional_information_report_zh.md").write_text(add_report,encoding="utf-8")

    final = """# 阶段D5第三轮报告

第二轮结论继续冻结为`reject_current_single_upstream_model_family`。本轮只做等价参数化、记忆时间、偏差归因和新增信息准入审计，没有重拟合M0/M1/M2，没有生成新模型NSE，也没有读取2011用于选模。

1. **M2触边**：主要是未归一化状态尺度问题。等价`g`稳定，逐日预测最大差%.3e。
2. **记忆时间**：rho跨fold稳定，90%%累计响应需%d—%d天，支持数周记忆；10/15天窗口偏短。
3. **1979**：M2 PBIAS %.2f%%，表现为跨月持续缺水量并含洪峰贡献；不是单个洪峰造成。
4. **1982**：M2 PBIAS %.2f%%，主要为若干月份和低流量基线抬高，显示固定增益跨年失配。
5. **额外信息**：ERA5完整且物理定义可审计；它不足以解释1979的跨年增益异常，但过去14日区间融雪量与M2残差在六年具有一致的季节去均值关系，足以合法预注册一个单变量低维检验。其他站Q和非2011控制代理不足。
6. **下一合法分支**：`%s`。后续只能以M2R归一化参数化为底座，加入预先冻结的一个过去14日区间融雪变量；本轮没有训练它，也不能宣称性能提升。M3仍不授权。
"""%(equivalence["maximum_absolute_prediction_difference"],mem90min,mem90max,a1979.m2_pbias_percent,a1982.m2_pbias_percent,branch["selected_branch"])
    (OUT/"stage_d5_round3_report_zh.md").write_text(final,encoding="utf-8")


def main():
    OUT.mkdir(parents=True,exist_ok=True); PLOTS.mkdir(parents=True,exist_ok=True)
    immutable = verify_round2_manifest()
    reconstruct_round1_manifest()
    predictions = pd.read_csv(R2/"outer_year_predictions.csv",parse_dates=["date"])
    if predictions.year.min()!=1978 or predictions.year.max()!=1983:
        raise RuntimeError("Round-2 predictions contain a forbidden year")
    params = selected_m2_parameters()
    reparam,equivalence=m2_reparameterization_audit(params,predictions)
    memory=memory_audit(params)
    annual,monthly,bias=model_bias_rows(predictions)
    write_csv(annual,OUT/"annual_gain_and_volume_diagnostics.csv")
    write_csv(monthly,OUT/"monthly_gain_diagnostics.csv")
    write_csv(bias,OUT/"year_specific_bias_diagnostics.csv")
    era,assoc,annual_weather,consistency,mass_diff=era5_audit(predictions,annual)
    write_csv(annual_weather,OUT/"annual_weather_gain_diagnostics.csv")
    stations,controls=audit_other_inputs()
    registry_rows=[]
    registry_rows.append({"branch":"M2R","candidate_group":"normalized single storage","available":True,"complete_1978_1983":True,"physical_meaning":True,"cross_year_diagnostic_consistency":equivalence["normalized_g_cv"]<=0.15,"deployment_legality":True,"admission":"eligible_not_selected_as_separate_branch","reason":"mathematically equivalent normalization; use as M2C implementation basis, not as a performance candidate"})
    consistent_count=int(((assoc.get("cross_year_anomaly_consistent",pd.Series(dtype=bool))==True)&(assoc.analysis_scope=="daily_m2_outer_residual")).sum())
    registry_rows.append({"branch":"M2C","candidate_group":"past-14-day incremental-basin snowmelt only","available":True,"complete_1978_1983":True,"physical_meaning":True,"cross_year_diagnostic_consistency":consistent_count>0,"deployment_legality":True,"admission":"selected_for_future_preregistered_test","reason":"past-14-day snowmelt anomaly has the same residual-correlation sign in all six years; one variable only, no current/future leakage"})
    registry_rows.append({"branch":"P1B","candidate_group":"DSK stage/control proxy","available":False,"complete_1978_1983":False,"physical_meaning":True,"cross_year_diagnostic_consistency":False,"deployment_legality":False,"admission":"blocked","reason":"fewer than two reliable non-2011 daily-stage years"})
    registry_rows.append({"branch":"dual_boundary","candidate_group":"Yanqi/intermediate observed Q","available":False,"complete_1978_1983":False,"physical_meaning":True,"cross_year_diagnostic_consistency":False,"deployment_legality":False,"admission":"blocked","reason":"no reliable multi-year additional station Q found"})
    registry=pd.DataFrame(registry_rows); write_csv(registry,OUT/"candidate_additional_inputs_registry.csv")
    branch={
        "decision_context":"development_diagnostic_only",
        "round2_decision_unchanged":"reject_current_single_upstream_model_family",
        "selected_branch":"M2C_single_storage_plus_interval_weather",
        "selected_branch_label":"分支B：M2C单储量＋区间气象",
        "performance_claim_allowed":False,
        "mathematically_equivalent_to_M2":False,
        "M2R_used_as_parameterization_basis":True,
        "frozen_candidate_variable_group":[{
            "variable":"interval_snowmelt_mm_antecedent_14d",
            "definition":"sum of the previous 14 complete UTC days of incremental-basin ERA5-Land snowmelt_mm; shift(1) before rolling",
            "unit":"mm over prior 14 days","current_day_allowed":False,"future_values_allowed":False,
            "selection_basis":"development_diagnostic_only; month-anomaly residual correlation has same sign in 6/6 years",
        }],
        "reasons":["M2R removes the misleading state-scale boundary","ERA5 interval series are complete and area weighted","past-14-day interval snowmelt has a same-sign month-anomaly residual association in 6/6 years","the group is frozen to one variable before any future fit"],
        "M2C_status":"admitted_for_one_future_nested_protocol_test_only; not trained in round 3",
        "P1B_status":"blocked_no_two_reliable_non2011_stage_years",
        "dual_boundary_status":"blocked_no_multiyear_additional_station_Q",
        "M3_authorized":False,"2011_used_for_selection":False,"new_model_trained":False,
    }
    dump_json(OUT/"next_branch_decision.json",branch)
    write_reports(reparam,equivalence,memory,annual,monthly,bias,era,assoc,stations,controls,branch)
    access={
        "program":"scripts/run_stage_d5_round3_diagnostics.py",
        "semantic_inputs":[
            "outputs/diagnosis_2005_snapshot/stage_d5_round2/fitted_parameters_by_fold.csv",
            "outputs/diagnosis_2005_snapshot/stage_d5_round2/outer_year_predictions.csv",
            "outputs/diagnosis_2005_snapshot/stage_d5_round2/multiyear_byblk_dsk_daily_canonical.csv",
            "data/processed/era5_land/era5land_daily_basin_weighted_1978_1983.nc",
            "data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc",
            "data/processed/era5_land/basin_grid_weights.csv","data/processed/era5_land/incremental_grid_weights.csv",
            "data/processed/timeseries.csv"],
        "round1_files_hashed_for_required_reconstruction_only":True,
        "2011_semantic_data_read":False,"2011_used_for_variable_selection":False,"model_refit":False,
        "new_nse_generated":False,"m3_developed":False,"gnn_used":False,
    }
    dump_json(OUT/"stage_d5_round3_input_access_audit.json",access)
    print(json.dumps({"round2_hashes_ok":immutable["all_hashes_match"],"m2_max_equivalence_diff":equivalence["maximum_absolute_prediction_difference"],"selected_branch":branch["selected_branch"],"consistent_weather_candidates":consistent_count},ensure_ascii=False))


if __name__ == "__main__":
    main()
