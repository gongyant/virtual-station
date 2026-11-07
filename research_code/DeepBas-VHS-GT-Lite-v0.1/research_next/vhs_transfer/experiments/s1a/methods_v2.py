"""S1A-R0 numerical modules. No import-time I/O, fitting or real-data entry point.

Features receive upstream values only. Model fit accepts FitLabels only;
evaluation labels have a separate type. Python API boundaries are not an OS sandbox.
"""
from dataclasses import dataclass
import numpy as np

DISPLACEMENTS = (-90, -60, -30, -14, -7, -3, 0, 3, 7, 14, 30, 60, 90)
WINDOWS = (1, 7, 30)

def days(start, end):
    return np.arange(np.datetime64(start, 'D'), np.datetime64(end, 'D') + 1)

def months(d):
    return np.asarray(d, dtype='datetime64[M]').astype(int) % 12

def checked_dates(d):
    d = np.asarray(d, dtype='datetime64[D]')
    if d.ndim != 1 or len(d) == 0 or np.isnat(d).any() or np.any(np.diff(d).astype(int) != 1):
        raise ValueError('Dates must be complete, unique, strictly daily and nonempty')
    return d.copy()

def values(v, n):
    v = np.asarray(v, dtype=float)
    if v.shape != (n,) or not np.isfinite(v).all() or np.any(v < 0):
        raise ValueError('Missing/nonfinite/negative Q or shape mismatch: stop; no imputation')
    return v.copy()

@dataclass(frozen=True)
class Fold:
    year: int
    fit_start: str = '1978-01-31'

    @property
    def train(self):
        return days(self.fit_start, f'{self.year-1}-12-31')

    @property
    def dev(self):
        return days(f'{self.year}-01-01', f'{self.year}-12-31')

@dataclass(frozen=True)
class Upstream:
    dates: np.ndarray
    q: np.ndarray

    def __post_init__(self):
        d = checked_dates(self.dates)
        q = values(self.q, len(d))
        d.flags.writeable = q.flags.writeable = False
        object.__setattr__(self, 'dates', d)
        object.__setattr__(self, 'q', q)

@dataclass(frozen=True)
class FitLabels:
    dates: np.ndarray
    q: np.ndarray

    def __post_init__(self):
        d = checked_dates(self.dates)
        q = values(self.q, len(d))
        d.flags.writeable = q.flags.writeable = False
        object.__setattr__(self, 'dates', d)
        object.__setattr__(self, 'q', q)

@dataclass(frozen=True)
class EvalLabels:
    dates: np.ndarray
    q: np.ndarray

def positions(source_dates, requested):
    requested = np.asarray(requested, dtype='datetime64[D]')
    p = np.searchsorted(source_dates, requested)
    if np.any(p >= len(source_dates)) or not np.array_equal(source_dates[p], requested):
        raise ValueError('Source date out of bounds; no wrapping or filling')
    return p

def raw_windows(up, anchors):
    # Anchor s: W1(s)=U(s-1), W7(s)=mean U(s-7..s-1), etc.
    return np.column_stack([
        np.mean(up.q[positions(up.dates, np.asarray(anchors)[:, None] - np.arange(1, w+1))], axis=1)
        for w in WINDOWS])

def monthly_fit(d, x):
    m = months(d)
    if len(np.unique(m)) != 12:
        raise ValueError('All twelve training months required')
    return np.stack([np.mean(x[m == i], axis=0) for i in range(12)])

def fourier2(d):
    d = np.asarray(d, dtype='datetime64[D]')
    y = d.astype('datetime64[Y]')
    doy = (d - y.astype('datetime64[D]')).astype(int)
    year = y.astype(int) + 1970
    leap = (year % 4 == 0) & ((year % 100 != 0) | (year % 400 == 0))
    # 365-day climatological calendar: Feb29 halfway between Feb28 and Mar1.
    doy = doy.astype(float) - (leap & (doy >= 60))
    doy[leap & (doy == 59) & (months(d) == 1)] = 58.5
    phi = 2 * np.pi * doy / 365
    return np.column_stack([np.ones(len(d)), np.sin(phi), np.cos(phi),
                            np.sin(2*phi), np.cos(2*phi)])

def ols(x, y, required_rank):
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('Nonfinite OLS inputs')
    s = np.linalg.svd(x, compute_uv=False)
    if len(s) != required_rank or s[-1] <= s[0] * 1e-12:
        raise ValueError('Rank-deficient design: stop; do not choose ridge or remove windows')
    return np.linalg.pinv(x, rcond=1e-12) @ y

@dataclass(frozen=True)
class FeatureTransform:
    climate: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, up, train):
        w = raw_windows(up, train)
        c = monthly_fit(train, w)
        a = w - c[months(train)]
        scale = np.std(a, axis=0, ddof=0)
        if np.any(scale <= 1e-12):
            raise ValueError('Zero training anomaly scale')
        return cls(c, scale)

    def apply(self, up, anchors):
        return (raw_windows(up, anchors) - self.climate[months(anchors)]) / self.scale

def common_support(fold, up):
    # Source anchors used in fit must stay in ORIGINAL legal training calendar.
    fit = fold.train[90:-90]
    # All development source anchors must be <= that development year's end.
    dev = fold.dev[:-90]
    if not len(fit) or not len(dev):
        raise ValueError('Insufficient support')
    for k in DISPLACEMENTS:
        s = fit - np.timedelta64(k, 'D')
        if s[0] < fold.train[0] or s[-1] > fold.train[-1]:
            raise ValueError('Placebo fitting source crosses training boundary')
        raw_windows(up, s)
        raw_windows(up, dev - np.timedelta64(k, 'D'))
    return fit, dev

@dataclass(frozen=True)
class Model:
    fold: Fold
    target_climate: np.ndarray
    transform: FeatureTransform
    beta: np.ndarray
    k: int
    calendar: str
    fit_dates: np.ndarray
    role: str

    def baseline_raw(self, dates):
        return (self.target_climate[months(dates)] if self.calendar == 'monthly'
                else fourier2(dates) @ self.target_climate)

    def predict(self, up, dates, operational=False):
        if operational:
            # Timestamp metadata is unverified for ALL models, not only negative k.
            raise PermissionError('No certified operational forecast; nominal daily-index analysis only')
        dates = np.asarray(dates, dtype='datetime64[D]')
        if np.any(dates < self.fold.dev[0]) or np.any(dates > self.fold.dev[-1]):
            raise ValueError('Prediction dates outside declared development year')
        anchors = dates - np.timedelta64(self.k, 'D')
        if np.any(anchors > self.fold.dev[-1]):
            raise ValueError('Future placebo crosses declared source boundary')
        base = self.baseline_raw(dates)
        raw = base + self.transform.apply(up, anchors) @ self.beta
        return {'dates': dates.copy(), 'baseline': np.maximum(base, 0),
                'prediction': np.maximum(raw, 0), 'unclipped': raw, 'role': self.role,
                'clip_count': int(np.sum(raw < 0)), 'clip_delta_sum': float(np.sum(np.maximum(raw, 0)-raw))}

def fit_model(up, labels, fold, k=0, placebo=False, calendar='monthly'):
    if type(labels) is not FitLabels or not np.array_equal(labels.dates, fold.train):
        raise ValueError('FitLabels must contain exactly this fold training dates, never dev labels')
    if k not in DISPLACEMENTS or (not placebo and k != 0):
        raise ValueError('Displacement outside frozen diagnostic grid or in primary model')
    if calendar not in ('monthly', 'fourier2') or (placebo and calendar != 'monthly'):
        raise ValueError('Unregistered calendar/combined sensitivity')
    climate = (monthly_fit(labels.dates, labels.q) if calendar == 'monthly'
               else ols(fourier2(labels.dates), labels.q, 5))
    tr = FeatureTransform.fit(up, fold.train)
    fit_dates = common_support(fold, up)[0] if placebo else fold.train
    anchors = fit_dates - np.timedelta64(k, 'D')
    if anchors[0] < fold.train[0] or anchors[-1] > fold.train[-1]:
        raise ValueError('Source-anchor fit leakage')
    x = tr.apply(up, anchors)
    b = climate[months(fit_dates)] if calendar == 'monthly' else fourier2(fit_dates) @ climate
    residual = labels.q[positions(labels.dates, fit_dates)] - b
    beta = ols(x, residual, 3)
    role = ('NONCAUSAL_FUTURE_UPSTREAM_PLACEBO' if k < 0 else
            'DISPLACEMENT_DIAGNOSTIC' if placebo else 'NOMINALLY_PAST_ONLY_PRIMARY')
    return Model(fold, climate, tr, beta, k, calendar, fit_dates.copy(), role)

def design_diagnostics(model, up):
    z = model.transform.apply(up, model.fit_dates - np.timedelta64(model.k, 'D'))
    centered = z - np.mean(z, axis=0)
    s = np.linalg.svd(z, compute_uv=False)
    vif = []
    for j in range(3):
        a = np.column_stack([np.ones(len(z)), np.delete(z, j, axis=1)])
        e = z[:, j] - a @ np.linalg.pinv(a, rcond=1e-12) @ z[:, j]
        sst = np.sum(centered[:, j]**2)
        ratio = np.sum(e**2)/sst if sst > 0 else 0
        vif.append(float(1/ratio) if ratio > 1e-12 else None)
    return {'correlation': np.corrcoef(z, rowvar=False).tolist(),
            'singular_values': s.tolist(), 'condition_number': float(s[0]/s[-1]),
            'VIF': vif, 'VIF_null_means': 'undefined or effectively infinite',
            'beta': model.beta.tolist(), 'beta_signs': np.sign(model.beta).astype(int).tolist(),
            'interpretation': 'predictive coefficients; collinearity forbids individual mechanistic attribution'}

def placebo_predictions(up, labels, fold):
    """Generate every prespecified arm together, with NO evaluation labels."""
    train, dev = common_support(fold, up)
    models = {k:fit_model(up,labels,fold,k=k,placebo=True) for k in DISPLACEMENTS}
    predictions = {k:m.predict(up,dev) for k,m in models.items()}
    if any(not np.array_equal(m.fit_dates,train) for m in models.values()):
        raise ValueError('Placebo training support mismatch')
    return predictions

def placebo_summary(predictions, evaluation, train_low_threshold):
    """Descriptive per-year response only. No best-k selector or p value."""
    if set(predictions) != set(DISPLACEMENTS):
        raise ValueError('All frozen arms including k=0 required')
    d = predictions[0]['dates']
    if any(not np.array_equal(p['dates'],d) for p in predictions.values()):
        raise ValueError('Displacement score dates differ')
    p0 = predictions[0]['baseline']
    if any(not np.array_equal(p['baseline'],p0) for p in predictions.values()):
        raise ValueError('Displacement baselines differ')
    for k,p in predictions.items():
        if k < 0 and p['role'] != 'NONCAUSAL_FUTURE_UPSTREAM_PLACEBO':
            raise ValueError('Future placebo mislabeled')
    baseline = score(evaluation,d,p0,train_low_threshold)
    metrics = {k:score(evaluation,d,p['prediction'],train_low_threshold) for k,p in predictions.items()}
    if baseline['RMSE'] == 0:
        return {'baseline':baseline,'metrics':metrics,'gains':None,'reason':'zero baseline RMSE'}
    g = {k:1-s['RMSE']/baseline['RMSE'] for k,s in metrics.items()}
    near = float(np.mean([g[k] for k in (-7,-3,0,3,7)]))
    far = float(np.mean([g[k] for k in (-90,-60,60,90)]))
    return {'baseline':baseline,'metrics':metrics,'gains':g,
            'positive_minus_negative':{a:g[a]-g[-a] for a in (3,7,14,30,60,90)},
            'near_mean_minus_far_mean':near-far,
            'aligned_minus_far':{k:g[0]-g[k] for k in (-90,-60,60,90)},
            'far_mean_gain':far, 'far_over_aligned':far/g[0] if g[0]>0 else None,
            'scope':'descriptive synchronization diagnostic; not causal, no p value or best k'}

def score(labels, dates, prediction, train_low_threshold):
    if type(labels) is not EvalLabels:
        raise TypeError('Evaluation labels required only after predictions frozen')
    d = checked_dates(labels.dates)
    y = values(labels.q, len(d))[positions(d, dates)]
    p = np.asarray(prediction, float)
    if p.shape != y.shape or not np.isfinite(p).all():
        raise ValueError('Invalid prediction')
    e = p-y
    sst = np.sum((y-y.mean())**2)
    low = y <= train_low_threshold
    total = np.sum(y)
    peak_delta = int((dates[np.argmax(p)]-dates[np.argmax(y)]).astype(int))
    return {'n': len(y), 'RMSE': float(np.sqrt(np.mean(e**2))), 'MAE': float(np.mean(abs(e))),
            'NSE': float(1-np.sum(e**2)/sst) if sst > 0 else None,
            'Bias': float(e.mean()), 'PBIAS': float(100*np.sum(e)/total) if total else None,
            'numeric_daily_sum_error': float(e.sum()), 'low_n': int(low.sum()),
            'low_RMSE': float(np.sqrt(np.mean(e[low]**2))) if low.any() else None,
            'peak_date_error_days': peak_delta, 'abs_peak_date_error_days': abs(peak_delta),
            'peak_amplitude_error': float(p.max()-y.max()),
            'monthly_bias': {str(i+1): float(e[months(dates)==i].mean())
                             for i in range(12) if np.any(months(dates)==i)}}

def block_indices(dates, block, reps, rng, circular=True):
    dates = checked_dates(dates)
    if len(np.unique(dates.astype('datetime64[Y]'))) != 1:
        raise ValueError('Bootstrap input must be one year, never concatenate development years')
    n = len(dates)
    if not 1 <= block <= n or reps < 1:
        raise ValueError('Invalid block/reps')
    starts = rng.integers(0, n if circular else n-block+1, size=(reps, (n+block-1)//block))
    idx = (starts[..., None] + np.arange(block)).reshape(reps, -1)[:, :n]
    return idx % n if circular else idx

def paired_bootstrap(years, block=30, reps=10000, seed=20261011, circular=True):
    """years: list of (dates, observed, baseline, augmented); conditional on fits.
    Same indices for both models; independent block draws within each year.
    """
    seen = set()
    rng = np.random.default_rng(seed)
    gains = []
    delta_nse = []
    for d, y, p0, p1 in years:
        yy = int(np.asarray(d)[0].astype('datetime64[Y]').astype(int))
        if yy in seen:
            raise ValueError('Duplicate bootstrap year')
        seen.add(yy)
        idx = block_indices(d, block, reps, rng, circular)
        y, p0, p1 = (np.asarray(v, float) for v in (y, p0, p1))
        if any(v.shape != (len(d),) or not np.isfinite(v).all() for v in (y,p0,p1)):
            raise ValueError('Invalid bootstrap arrays')
        r0 = np.sqrt(np.mean((p0[idx]-y[idx])**2, axis=1))
        r1 = np.sqrt(np.mean((p1[idx]-y[idx])**2, axis=1))
        if np.any(r0 == 0):
            raise ValueError('Undefined relative gain: zero baseline RMSE')
        gains.append((r0-r1)/r0)
        resampled_y = y[idx]
        denominator = np.sum((resampled_y-resampled_y.mean(axis=1)[:,None])**2,axis=1)
        if np.any(denominator == 0):
            delta_nse.append(None)
        else:
            delta_nse.append(len(d)*(r0**2-r1**2)/denominator)
    if len(seen) != 3:
        raise ValueError('Registered macro bootstrap requires three development years')
    macro = np.mean(gains, axis=0)
    return {'gain_CI_95': np.quantile(macro, [0.025,0.975]).tolist(),
            'DeltaNSE_CI_95': (np.quantile(np.mean(delta_nse,axis=0),[0.025,0.975]).tolist()
                              if all(v is not None for v in delta_nse) else None),
            'reps': reps, 'seed': seed, 'block': block, 'circular': circular,
            'scope': 'descriptive, conditional on fitted models and exposed years; not future-year prediction interval'}

def primary_decision(baseline_scores, augmented_scores, ci30, ci60):
    if len(baseline_scores) != 3 or len(augmented_scores) != 3:
        raise ValueError('Three folds required')
    gains, costs = [], []
    for a,b in zip(baseline_scores, augmented_scores):
        if a['RMSE'] == 0 or any(a.get(k) is None or b.get(k) is None for k in ('PBIAS','low_RMSE')):
            return {'decision':'INSUFFICIENT_EVIDENCE', 'reason':'undefined metric'}
        gains.append((a['RMSE']-b['RMSE'])/a['RMSE'])
        if a['low_RMSE'] == 0:
            low_cost = b['low_RMSE'] > 0
        else:
            low_cost = b['low_RMSE']/a['low_RMSE'] - 1 > 0.05
        costs.append(abs(b['PBIAS'])-abs(a['PBIAS']) > 2 or low_cost)
    consistent = min(gains)>0 and np.mean(gains)>=0.02 and ci30[0]>0 and ci60[0]>0
    return {'decision':'CONSISTENT_DEVELOPMENT_GAIN' if consistent else 'MIXED_OR_UNCERTAIN',
            'macro_relative_gain':float(np.mean(gains)), 'annual_gains':gains,
            'robust_usefulness':'NOT_ROBUST_USEFULNESS' if any(costs) else 'NO_PRESET_COST_EXCEEDANCE'}
