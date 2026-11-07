"""Synthetic-label evaluation; NA is explicit, inference clusters are years."""
import public_runtime
import itertools
import math
import numpy as np
from .contracts import ScienceError

def result(value=None, reason=None):
    if value is not None and (not math.isfinite(float(value))):
        raise ScienceError('NONFINITE_METRIC')
    return {'value': None if value is None else float(value), 'status': 'N/A' if reason else 'OK', 'reason_code': reason}

def _arrays(observed, predicted):
    y, p = (np.asarray(observed, float), np.asarray(predicted, float))
    if y.ndim != 1 or y.shape != p.shape or (not len(y)) or (not np.isfinite(y).all()) or (not np.isfinite(p).all()):
        raise ScienceError('INVALID_EVALUATION_ARRAYS')
    return (y, p)

def metric_bundle(observed, predicted, *, synthetic):
    public_runtime.admit_metric(observed, predicted, synthetic)
    y, p = _arrays(observed, predicted)
    err = p - y
    mse = float(np.mean(err ** 2))
    out = {'MAE': result(np.mean(np.abs(err))), 'RMSE': result(math.sqrt(mse)), 'MSE': result(mse)}
    sst = float(np.sum((y - y.mean()) ** 2))
    out['NSE'] = result(1 - float(np.sum(err ** 2)) / sst) if sst > 0 else result(reason='CONSTANT_OBSERVATION')
    out['PBIAS'] = result(100 * float(np.sum(err)) / float(np.sum(y))) if abs(float(np.sum(y))) > 1e-12 else result(reason='ZERO_OBSERVATION_SUM')
    sy, sp = (float(np.std(y, ddof=0)), float(np.std(p, ddof=0)))
    r = result(float(np.corrcoef(y, p)[0, 1])) if len(y) >= 2 and sy > 0 and (sp > 0) else result(reason='UNDEFINED_CORRELATION')
    a = result(sp / sy) if sy > 0 else result(reason='ZERO_OBSERVATION_STD')
    b = result(float(p.mean() / y.mean())) if abs(float(y.mean())) > 1e-12 else result(reason='ZERO_OBSERVATION_MEAN')
    out.update(KGE_r=r, KGE_alpha=a, KGE_beta=b)
    out['KGE'] = result(1 - math.sqrt((r['value'] - 1) ** 2 + (a['value'] - 1) ** 2 + (b['value'] - 1) ** 2)) if all((v['status'] == 'OK' for v in (r, a, b))) else result(reason='UNDEFINED_KGE_COMPONENT')
    return out

def same_sample_skill(observed, predictions, benchmark, ids, benchmark_ids, *, synthetic):
    if tuple(ids) != tuple(benchmark_ids) or len(set(ids)) != len(ids):
        raise ScienceError('COMMON_SAMPLE_IDS_MISMATCH')
    public_runtime.admit_metric(observed, predictions, synthetic)
    y, p = _arrays(observed, predictions)
    _, b = _arrays(y, benchmark)
    denom = float(np.mean((b - y) ** 2))
    return result(1 - float(np.mean((p - y) ** 2)) / denom) if denom > 1e-24 else result(reason='PERFECT_OR_ZERO_LOSS_BENCHMARK')

def holm_adjust(pvalues):
    names = sorted(pvalues, key=lambda k: (pvalues[k], k))
    if any((not 0 <= pvalues[k] <= 1 for k in names)):
        raise ScienceError('INVALID_P_VALUE')
    out, running = ({}, 0.0)
    for i, name in enumerate(names):
        running = max(running, min(1.0, (len(names) - i) * pvalues[name]))
        out[name] = running
    return out

def exact_sign_flip(differences):
    d = np.asarray(differences, float)
    if not np.isfinite(d).all() or len(d) < 2:
        return {'p': result(reason='INSUFFICIENT_INDEPENDENT_YEARS')}
    if len(d) > 20:
        raise ScienceError('EXACT_ENUMERATION_LIMIT', 'predefined maximum 20 years; no silent approximation')
    observed = abs(float(d.mean()))
    exceed = sum((abs(float(np.mean(d * np.asarray(signs)))) >= observed - 1e-12 * max(1, observed) for signs in itertools.product((-1, 1), repeat=len(d))))
    return {'p': result(exceed / 2 ** len(d)), 'n_years': len(d), 'assignments': 2 ** len(d), 'two_sided': True, 'statistic': 'ABS_YEAR_MEAN_PAIRED_LOSS_DIFFERENCE', 'assumption': 'year differences independent and sign-exchangeable/symmetric under null; not established by sparse records'}

def year_block_bootstrap(differences, seed=20261025, repetitions=999):
    d = np.asarray(differences, float)
    if len(d) < 2 or not np.isfinite(d).all():
        return {'mean': result(reason='INSUFFICIENT_INDEPENDENT_YEARS')}
    if repetitions < 2:
        raise ScienceError('INSUFFICIENT_BOOTSTRAP_REPETITIONS')
    rng = np.random.default_rng(seed)
    draws = d[rng.integers(0, len(d), size=(repetitions, len(d)))].mean(axis=1)
    return {'mean': result(d.mean()), 'percentile_95_interval': np.quantile(draws, [0.025, 0.975]).tolist(), 'seed': seed, 'repetitions': repetitions, 'resampling_unit': 'YEAR', 'n_years': len(d), 'caveat': 'year dependence is not removed by resampling; interval is unstable for few years'}

def jackknife(differences):
    d = np.asarray(differences, float)
    if len(d) < 2 or not np.isfinite(d).all():
        return {'estimate': result(reason='INSUFFICIENT_INDEPENDENT_YEARS')}
    loo = [(float(d.sum()) - float(x)) / (len(d) - 1) for x in d]
    se = math.sqrt((len(d) - 1) / len(d) * float(np.sum((np.array(loo) - np.mean(loo)) ** 2)))
    return {'estimate': result(d.mean()), 'leave_one_year_out_estimates': loo, 'standard_error': se, 'all_deletions_positive': bool(min(loo) > 0), 'max_abs_change': max((abs(v - float(d.mean())) for v in loo))}

def detectable_effect(differences):
    d = np.asarray(differences, float)
    if len(d) < 2 or not np.isfinite(d).all():
        return result(reason='INSUFFICIENT_INDEPENDENT_YEARS')
    value = (1.959963984540054 + 0.8416212335729143) * float(np.std(d, ddof=1)) / math.sqrt(len(d))
    return {**result(value), 'method': 'NORMAL_APPROX_TWO_SIDED_005_POWER_080_UNADJUSTED', 'caveat': 'detectable-effect diagnostic only; not small-sample t or Holm-adjusted prospective power'}

def paired_year_comparison(y, challenger, benchmark, years, seed=20261025):
    y, c = _arrays(y, challenger)
    _, b = _arrays(y, benchmark)
    unique = sorted(set(years.tolist()))
    d = [float(np.mean((b[years == year] - y[years == year]) ** 2) - np.mean((c[years == year] - y[years == year]) ** 2)) for year in unique]
    return {'years': unique, 'year_MSE_improvement': d, 'n_independent_units_assumed': len(unique), 'mean_year_improvement': result(np.mean(d)), 'fraction_years_improved': sum((v > 1e-12 for v in d)) / len(d), 'exact_sign_flip': exact_sign_flip(d), 'year_bootstrap': year_block_bootstrap(d, seed), 'jackknife': jackknife(d), 'detectable_effect': detectable_effect(d)}

def evaluate_oof(features, observed_labels, predictions, group, seed=20261025):
    features.require_synthetic()
    y = np.asarray(observed_labels, float)
    if len(y) != len(features.keys):
        raise ScienceError('LABEL_LENGTH_MISMATCH')
    ids = features.ids
    out = {'synthetic': True, 'status': 'SYNTHETIC_ONLY', 'experiment_group': group, 'inference_unit': 'YEAR', 'n_months': len(ids), 'n_years': len(set(features.years.tolist())), 'unit_status': 'SYNTHETIC_ARBITRARY_UNITS', 'models': {}, 'comparisons': {}}
    raw = {}
    for model_id, records in predictions.items():
        if set(records) != set(ids):
            raise ScienceError('INCOMPLETE_OR_EXTRA_OOF_IDS', model_id)
        raw[model_id] = np.array([records[s]['raw'] for s in ids], float)
    for model_id in predictions:
        p = raw[model_id]
        yearly = {str(year): metric_bundle(y[features.years == year], p[features.years == year], synthetic=True) for year in sorted(set(features.years.tolist()))}
        item = {'pooled_raw': metric_bundle(y, p, synthetic=True), 'pooled_constrained_secondary': metric_bundle(y, np.maximum(p, 0), synthetic=True), 'yearly_raw': yearly, 'equal_year_MSE': result(np.mean([v['MSE']['value'] for v in yearly.values()])), 'skills_raw': {b: same_sample_skill(y, p, raw[b], ids, ids, synthetic=True) for b in ('E0', 'C0') if b in raw}}
        item['delta_NSE'] = metric_bundle(y - features.columns['Qu'], p - features.columns['Qu'], synthetic=True)['NSE'] if 'Qu' in features.columns else result(reason='UPSTREAM_Q_NOT_IN_EXPERIMENT_GROUP')
        out['models'][model_id] = item
    comparisons = [('E1b', 'E0'), ('E2', 'E1b'), ('E3', 'E2'), ('E3n', 'C0')]
    for c, b in comparisons:
        if c in raw and b in raw:
            out['comparisons'][f'{c}_vs_{b}'] = paired_year_comparison(y, raw[c], raw[b], features.years, seed)
    ps = {name: c['exact_sign_flip']['p']['value'] for name, c in out['comparisons'].items() if c['exact_sign_flip']['p']['status'] == 'OK'}
    for name, adjusted in holm_adjust(ps).items():
        out['comparisons'][name]['Holm_adjusted_p'] = adjusted
        out['comparisons'][name]['classification'] = 'SYNTHETIC_CODE_VERIFICATION_NOT_SCIENTIFIC_CLAIM'
    return out
