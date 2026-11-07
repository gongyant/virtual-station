"""Calendar-year folds, exact snapshot binding and support membership."""
from dataclasses import dataclass, asdict
from .contracts import ScienceError, digest, ids_hash, GROUP_A, GROUP_B


@dataclass(frozen=True)
class FoldSpec:
    fold_id: str
    validation: str
    dataset_id: str
    snapshot_id: str
    experiment_group: str
    quality_scheme: str
    train_ids: tuple
    test_ids: tuple
    train_years: tuple
    test_years: tuple
    buffer_years: int
    ledger_hash: str

    def record(self):
        d = asdict(self)
        d.update(train_ids_hash=ids_hash(self.train_ids), test_ids_hash=ids_hash(self.test_ids))
        d["fold_hash"] = digest(d)
        return d


def support(rows, group, scheme="claude_core"):
    if group not in (GROUP_A, GROUP_B):
        raise ScienceError("UNKNOWN_EXPERIMENT_GROUP")
    out = []
    for r in rows:
        ok = r.get("common_pair_" + scheme, False) if group == GROUP_A else r.get("down_" + scheme + "_usable", False)
        # Both groups include meteorology models; define identical within-group support.
        if ok and r.get("meteorology_valid", False):
            y, m = r["year"], r["month"]
            if not isinstance(y, int) or not isinstance(m, int) or not 1 <= m <= 12:
                raise ScienceError("INVALID_CALENDAR_KEY")
            if not r["station_id"].startswith(r["dataset_id"] + ":") or r["sample_id"] != f"{r['station_id']}:{y:04d}-{m:02d}":
                raise ScienceError("LEDGER_SAMPLE_KEY_MISMATCH")
            out.append(r)
    return sorted(out, key=lambda r: (r["year"], r["month"], r["sample_id"]))


def consecutive_groups(years):
    groups = []
    for y in sorted(set(years)):
        if not groups or y != groups[-1][-1] + 1:
            groups.append([y])
        else:
            groups[-1].append(y)
    return groups


def validate_fold(fold, legal_rows):
    index = {r["sample_id"]: r for r in legal_rows}
    if len(index) != len(legal_rows):
        raise ScienceError("DUPLICATE_LEDGER_ID")
    if set(fold.train_ids) & set(fold.test_ids) or set(fold.train_years) & set(fold.test_years):
        raise ScienceError("TRAIN_TEST_OVERLAP")
    if not fold.train_ids or not fold.test_ids:
        raise ScienceError("EMPTY_FOLD")
    for part, years in ((fold.train_ids, fold.train_years), (fold.test_ids, fold.test_years)):
        if len(set(part)) != len(part) or not set(part) <= set(index):
            raise ScienceError("ILLEGAL_FOLD_MEMBERSHIP")
        if {index[s]["year"] for s in part} != set(years):
            raise ScienceError("FOLD_YEAR_MISMATCH")
        for sid in part:
            r = index[sid]
            if r["dataset_id"] != fold.dataset_id or r["data_snapshot_id"] != fold.snapshot_id:
                raise ScienceError("DATASET_SNAPSHOT_MISMATCH")


def make_folds(rows, group, scheme="claude_core", validation="LOYO", buffer_years=1, min_forward_train_years=4):
    legal = support(rows, group, scheme)
    if not legal:
        raise ScienceError("NO_ADMISSIBLE_SUPPORT")
    if len({r["sample_id"] for r in legal}) != len(legal):
        raise ScienceError("DUPLICATE_LEDGER_ID")
    bindings = {(r["dataset_id"], r["data_snapshot_id"]) for r in legal}
    if len(bindings) != 1:
        raise ScienceError("DATASET_SNAPSHOT_MISMATCH")
    ds, snap = next(iter(bindings))
    years = sorted({r["year"] for r in legal})
    if validation == "LEAVE_CONTIGUOUS_RUN_OUT":
        tests = consecutive_groups(years)
    elif validation in ("LOYO", "BUFFERED_LOYO"):
        tests = [[y] for y in years]
    elif validation == "FORWARD_SPLIT":
        if not isinstance(min_forward_train_years, int) or min_forward_train_years < 1:
            raise ScienceError("INVALID_FORWARD_MIN_TRAIN_YEARS")
        tests = [[y] for y in years[min_forward_train_years:]]
    else:
        raise ScienceError("UNKNOWN_VALIDATION")
    ledger_hash = digest(legal)
    folds = []
    for held in tests:
        train_y = [y for y in years if y not in held]
        if validation == "BUFFERED_LOYO":
            if not isinstance(buffer_years, int) or buffer_years < 0:
                raise ScienceError("INVALID_BUFFER")
            train_y = [y for y in train_y if all(abs(y - h) > buffer_years for h in held)]
        if validation == "FORWARD_SPLIT":
            train_y = [y for y in train_y if y < min(held)]
        f = FoldSpec(f"{validation}-{'_'.join(map(str, held))}", validation, ds, snap, group, scheme,
                     tuple(r["sample_id"] for r in legal if r["year"] in train_y),
                     tuple(r["sample_id"] for r in legal if r["year"] in held),
                     tuple(train_y), tuple(held), buffer_years if validation == "BUFFERED_LOYO" else 0, ledger_hash)
        validate_fold(f, legal); folds.append(f)
    return folds


def lag1_ids(rows, usable_key):
    """Only the preceding actual calendar month; never previous table row."""
    idx = {(r["year"], r["month"]): r for r in rows if r.get(usable_key)}
    out = {}
    for r in rows:
        y, m = r["year"], r["month"]
        previous = (y, m - 1) if m > 1 else (y - 1, 12)
        out[r["sample_id"]] = idx[previous]["sample_id"] if previous in idx else None
    return out
