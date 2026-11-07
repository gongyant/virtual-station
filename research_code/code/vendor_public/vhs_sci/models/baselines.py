"""Seven actual fit/predict baselines; synthetic-only execution boundary."""
import math
import numpy as np
from ..contracts import ScienceError, PredictionBatch, TrainingBatch, ids_hash
from ..features import validate_features, MeteorologyTransform, base_graph, FeatureSpec, FeatureGraph
VERSION = 'VHS-SCI-S2-MODELS-1.0'
ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0)
CONDITION_LIMIT = 10000000000.0

def linear_solve(X, y, penalty=None):
    """SVD least squares on centered/scaled design, no normal equations.

    Penalties act on ORIGINAL feature coefficients; scaling does not change
    the selective Ridge objective. Intercept is never penalized.
    """
    X, y = (np.asarray(X, float), np.asarray(y, float))
    if X.ndim != 2 or y.shape != (len(X),) or (not np.isfinite(X).all()) or (not np.isfinite(y).all()):
        raise ScienceError('NONFINITE_OR_MALFORMED_LINEAR_SYSTEM')
    p = np.zeros(X.shape[1]) if penalty is None else np.asarray(penalty, float)
    if p.shape != (X.shape[1],) or (p < 0).any() or (not np.isfinite(p).all()) or (p[0] != 0):
        raise ScienceError('INVALID_PENALTY')
    mu, sd = (X.mean(axis=0), X.std(axis=0))
    mu[0], sd[0] = (0.0, 1.0)
    sd[sd <= np.finfo(float).eps * np.maximum(1.0, np.max(np.abs(X), axis=0)) * 32] = 1.0
    Z = (X - mu) / sd
    unpen = Z[:, p == 0]
    if np.linalg.matrix_rank(unpen) < unpen.shape[1]:
        raise ScienceError('RANK_DEFICIENT_UNPENALIZED_DESIGN')
    aug = np.vstack([Z, np.diag(np.sqrt(p) / sd)])
    yy = np.concatenate([y, np.zeros(len(p))])
    cond = float(np.linalg.cond(aug))
    if not np.isfinite(cond) or cond > CONDITION_LIMIT:
        raise ScienceError('ILL_CONDITIONED_DESIGN', str(cond))
    theta, _, rank, _ = np.linalg.lstsq(aug, yy, rcond=None)
    if rank != X.shape[1]:
        raise ScienceError('RANK_DEFICIENT_DESIGN')
    beta = theta / sd
    beta[0] -= float(np.dot(mu, beta))
    if not np.isfinite(beta).all():
        raise ScienceError('NONFINITE_COEFFICIENT')
    return (beta, {'solver': 'SVD_AUGMENTED_SCALED', 'rank': int(rank), 'condition_scaled': cond, 'penalty_original_coefficients': p.tolist(), 'condition_limit': CONDITION_LIMIT})

def season(x):
    phase = 2 * np.pi * x.months / 12
    return np.column_stack([np.sin(phase), np.cos(phase)])

class BaseModel:
    required_fields = ()
    no_upstream = False

    def _begin(self, train):
        x = train.features
        validate_features(x, self.no_upstream)
        if not np.isfinite(train.labels).all() or (np.asarray(train.labels) < 0).any():
            raise ScienceError('INVALID_TRAINING_LABELS')
        if not set(self.required_fields) <= set(x.columns):
            raise ScienceError('MISSING_FEATURE')
        self.binding = (x.keys[0].dataset_id, x.keys[0].snapshot_id)
        self.train_ids = tuple(x.ids)
        self.train_ids_hash = ids_hash(x.ids)
        return (x, np.asarray(train.labels, float))

    def _check(self, x):
        validate_features(x, self.no_upstream)
        if not hasattr(self, 'binding'):
            raise ScienceError('MODEL_NOT_FITTED')
        if self.binding != (x.keys[0].dataset_id, x.keys[0].snapshot_id):
            raise ScienceError('DATASET_SNAPSHOT_MISMATCH')
        if not set(self.required_fields) <= set(x.columns):
            raise ScienceError('MISSING_FEATURE')

    def _prediction(self, x, raw):
        raw = np.asarray(raw, float)
        return PredictionBatch(x.keys, raw, np.maximum(raw, 0), self.model_id, self.train_ids_hash)

    def record(self):
        ds = self.binding[0]
        nodes = list(base_graph(ds).nodes.values())
        names = [n for n in self.required_fields if n != 'met_complete']
        if self.model_id in ('C0', 'E2', 'E3', 'E3n'):
            for n in ('month_sin', 'month_cos'):
                nodes.append(FeatureSpec(n, ('month',), 'DERIVED', ds))
            names.extend(('month_sin', 'month_cos') if self.model_id != 'C0' else ('month',))
        if self.model_id in ('E3', 'E3n'):
            for n in ('P', 'T'):
                names.remove(n)
                names.append(n + '_anomaly')
                nodes.append(FeatureSpec(n + '_anomaly', (n, 'month'), 'DERIVED', ds, 'train_fold', self.train_ids))
        graph = FeatureGraph(nodes)
        return {'model_id': self.model_id, 'model_version': VERSION, 'synthetic': False, 'authorization_status': 'PUBLIC_DATA_REAL_EXPERIMENT', 'train_ids_hash': self.train_ids_hash, 'train_years': sorted({int(s[-7:-3]) for s in self.train_ids}), 'constraint_rule': 'PRIMARY_RAW_SECONDARY_MAX_ZERO', 'parameters': getattr(self, 'parameters', {}), 'diagnostics': getattr(self, 'diagnostics', {}), 'input_feature_lineage': graph.check(names, ds, self.train_ids), 'parameter_label_dependency': {'uses_training_target_labels': self.model_id != 'E0', 'role': 'TRAINING_LABEL' if self.model_id != 'E0' else 'NONE', 'fit_ids_hash': self.train_ids_hash, 'held_out_labels_used': False}}

class UpstreamIdentity(BaseModel):
    model_id, required_fields = ('E0', ('Qu',))

    def fit(self, train):
        self._begin(train)
        self.parameters = {'fixed_slope': 1.0, 'n_fitted_parameters': 0}
        return self

    def predict(self, features_test):
        validate_features(features_test)
        if 'Qu' not in features_test.columns:
            raise ScienceError('MISSING_UPSTREAM_Q')
        if hasattr(self, 'binding'):
            self._check(features_test)
        else:
            self.binding = (features_test.keys[0].dataset_id, features_test.keys[0].snapshot_id)
            self.train_ids = ()
            self.train_ids_hash = ids_hash([])
            self.parameters = {'fixed_slope': 1.0, 'n_fitted_parameters': 0}
        return self._prediction(features_test, np.asarray(features_test.columns['Qu']).copy())

class MonthlyClimatology(BaseModel):
    model_id, no_upstream = ('C0', True)

    def fit(self, train):
        x, y = self._begin(train)
        self.climate = {}
        for m in range(1, 13):
            mask = x.months == m
            if mask.sum() < 3 or len(set(x.years[mask])) < 3:
                raise ScienceError('C0_INSUFFICIENT_MONTH_SUPPORT', str(m))
            self.climate[m] = float(np.mean(y[mask]))
        self.parameters = {str(k): v for k, v in self.climate.items()}
        return self

    def predict(self, features_test):
        self._check(features_test)
        return self._prediction(features_test, [self.climate[k.month] for k in features_test.keys])

class RatioBaseline(BaseModel):
    model_id, required_fields = ('E1a', ('Qu',))

    def fit(self, train):
        x, y = self._begin(train)
        denominator = float(np.sum(x.columns['Qu']))
        if not math.isfinite(denominator) or abs(denominator) <= 1e-12:
            raise ScienceError('INVALID_RATIO_DENOMINATOR')
        self.ratio = float(np.sum(y) / denominator)
        if not math.isfinite(self.ratio):
            raise ScienceError('NONFINITE_RATIO')
        self.parameters = {'ratio': self.ratio}
        return self

    def predict(self, features_test):
        self._check(features_test)
        return self._prediction(features_test, self.ratio * features_test.columns['Qu'])

class UpstreamOLS(BaseModel):
    model_id, required_fields = ('E1b', ('Qu',))

    def design(self, x):
        return np.column_stack([np.ones(len(x.keys)), x.columns['Qu']])

    def fit(self, train):
        x, y = self._begin(train)
        self.beta, self.diagnostics = linear_solve(self.design(x), y)
        self.parameters = {'coefficients': self.beta.tolist()}
        return self

    def predict(self, features_test):
        self._check(features_test)
        return self._prediction(features_test, self.design(features_test) @ self.beta)

class SeasonalOLS(UpstreamOLS):
    model_id = 'E2'

    def __init__(self, parameterization='direct'):
        if parameterization not in ('direct', 'delta'):
            raise ScienceError('UNKNOWN_PARAMETERIZATION')
        self.parameterization = parameterization

    def design(self, x):
        return np.column_stack([np.ones(len(x.keys)), x.columns['Qu'], season(x)])

    def fit(self, train):
        x, y = self._begin(train)
        target = y - x.columns['Qu'] if self.parameterization == 'delta' else y
        self.beta, self.diagnostics = linear_solve(self.design(x), target)
        if self.parameterization == 'delta':
            self.beta[1] += 1.0
        self.parameters = {'coefficients_Qd_scale': self.beta.tolist(), 'parameterization': self.parameterization, 'delta_interpretation': 'NET_FLOW_CHANGE_NOT_WITHDRAWAL'}
        return self

class MeteorologyRidge(BaseModel):

    def __init__(self, use_upstream=True, alpha=None):
        self.use_upstream, self.alpha = (use_upstream, alpha)
        self.model_id = 'E3' if use_upstream else 'E3n'
        self.no_upstream = not use_upstream
        self.required_fields = (('Qu',) if use_upstream else ()) + ('P', 'T', 'met_complete')
        if alpha is not None and (not math.isfinite(alpha) or alpha <= 0):
            raise ScienceError('INVALID_ALPHA')

    def design(self, x):
        parts = [np.ones((len(x.keys), 1))]
        if self.use_upstream:
            parts.append(np.asarray(x.columns['Qu']).reshape(-1, 1))
        parts += [season(x), self.transformer.transform(x)]
        return np.column_stack(parts)

    def fit(self, train):
        x, y = self._begin(train)
        self.cv_trace = []
        if self.alpha is None:
            years = sorted(set(x.years.tolist()))
            if len(years) < 4:
                raise ScienceError('RIDGE_INSUFFICIENT_INNER_YEARS')
            for alpha in ALPHAS:
                losses, records = ([], [])
                for held in years:
                    itrain = [k.sample_id for k in x.keys if k.year != held]
                    ival = [k.sample_id for k in x.keys if k.year == held]
                    tx, vx = (x.take(itrain), x.take(ival))
                    inner = MeteorologyRidge(self.use_upstream, alpha).fit(TrainingBatch(tx, y[x.years != held]))
                    prediction = inner.predict(vx).raw
                    losses.append(float(np.mean((prediction - y[x.years == held]) ** 2)))
                    records.append({'held_year': held, 'train_ids_hash': inner.train_ids_hash, 'validation_ids_hash': ids_hash(vx.ids), 'transform_fit_ids_hash': inner.transformer.record()['fit_ids_hash'], 'transform_fit_years': sorted(set(tx.years.tolist()))})
                mean = float(np.mean(losses))
                se = float(np.std(losses, ddof=1) / np.sqrt(len(losses)))
                self.cv_trace.append({'alpha': alpha, 'mean_year_MSE_raw': mean, 'standard_error': se, 'year_losses': losses, 'folds': records})
            best = min(self.cv_trace, key=lambda r: (r['mean_year_MSE_raw'], r['alpha']))
            cutoff = best['mean_year_MSE_raw'] + best['standard_error']
            tol = 1e-12 * max(1.0, abs(cutoff))
            self.selected_alpha = max((r['alpha'] for r in self.cv_trace if r['mean_year_MSE_raw'] <= cutoff + tol))
            self.selection = {'rule': 'ONE_STANDARD_ERROR_LARGEST_ALPHA', 'best_alpha': best['alpha'], 'cutoff': cutoff, 'comparison_tolerance': tol, 'best_tie_rule': 'LOWEST_MEAN_THEN_SMALLEST_ALPHA', 'selected_alpha': self.selected_alpha}
        else:
            self.selected_alpha = float(self.alpha)
            self.selection = {'rule': 'FIXED_ALPHA', 'selected_alpha': self.selected_alpha}
        self.transformer = MeteorologyTransform().fit(train)
        X = self.design(x)
        penalty = np.zeros(X.shape[1])
        penalty[-2:] = self.selected_alpha
        self.beta, self.diagnostics = linear_solve(X, y, penalty)
        self.parameters = {'coefficients': self.beta.tolist(), 'selection': self.selection, 'penalty_scope': 'METEOROLOGY_ONLY', 'no_upstream_Q': not self.use_upstream}
        return self

    def predict(self, features_test):
        self._check(features_test)
        return self._prediction(features_test, self.design(features_test) @ self.beta)

    def record(self):
        return {**super().record(), 'meteorology_transform': self.transformer.record(), 'nested_CV': self.cv_trace}

def model_factory(model_id, alpha=None):
    constructors = {'E0': UpstreamIdentity, 'C0': MonthlyClimatology, 'E1a': RatioBaseline, 'E1b': UpstreamOLS, 'E2': SeasonalOLS, 'E3': lambda: MeteorologyRidge(True, alpha), 'E3n': lambda: MeteorologyRidge(False, alpha)}
    if model_id not in constructors:
        raise ScienceError('UNKNOWN_MODEL')
    return constructors[model_id]()
