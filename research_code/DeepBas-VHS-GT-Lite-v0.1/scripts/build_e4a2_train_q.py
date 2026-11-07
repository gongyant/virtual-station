import pandas as pd
src = "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
df = pd.read_csv(src, parse_dates=["date"])
df = df.loc[df.date.between("1978-01-01","1981-12-31"), ["date","Q_input_byblk","Q_target_dsk"]].copy()
df = df.sort_values("date")
df["date"] = df["date"].dt.strftime("%Y-%m-%d")
out = df.rename(columns={"Q_input_byblk":"Q_BYBLK","Q_target_dsk":"Q_DSK"})
assert len(out)==1461, len(out)
assert out.date.is_unique
assert out.date.tolist()==pd.date_range("1978-01-01","1981-12-31").strftime("%Y-%m-%d").tolist()
assert out.Q_BYBLK.notna().all() and out.Q_DSK.notna().all()
import numpy as np
assert np.isfinite(out.Q_BYBLK.to_numpy(float)).all() and np.isfinite(out.Q_DSK.to_numpy(float)).all()
out.to_csv("outputs/vhs_bd1m/experiments/e4a2_train_daily_q.csv", index=False)
print("OK", len(out))
