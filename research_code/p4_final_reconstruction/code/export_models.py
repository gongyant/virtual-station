"""Portable NumPy-only inference release, no original data or fitting dependencies."""
from common import *
import shutil,subprocess
out=P/"release/P4_PUBLIC_V2";out.mkdir(parents=True,exist_ok=False);(out/"runtime").mkdir()
for mf in jl(P/"P4_V2_MODEL_MANIFEST.json")["models"]:
 target=out/"models"/f'ID_{mf["gauge_id"]}'/mf["model_id"].replace("+","_");shutil.copytree(mf["path"],target)
shutil.copyfile(P/"P4_PROTOCOL.json",out/"P4_PROTOCOL.json");shutil.copyfile(P/"P4_RELEASE_INDEX.json",out/"RELEASE_INDEX.json")
common=(P/"code/common.py").read_text(encoding="utf-8")
(out/"runtime/common.py").write_text(common,encoding="utf-8")
api=(P/"code/inference.py").read_text(encoding="utf-8")
old='assert self.meta["math_sha256"]==sha(P2/"P2_MODEL_CODE/models.py"),"MATH_VERSION_CHANGED"'
new='assert self.meta["math_sha256"]=="'+jl(P/"P4_PROTOCOL.json")["spec"]["math_sha256"]+'","MATH_VERSION_CHANGED"'
assert old in api
(out/"runtime/inference.py").write_text(api.replace(old,new),encoding="utf-8")
# Package example includes meteorology only; no Q or teacher data.
shutil.copyfile(P/"evidence/FRESH_PROCESS_MET_ONLY.json",out/"example_MET_ID2.json")
(out/"README_ZH.md").write_text("""# P4公开流域月径流重建模型
只需Python与NumPy，无需P2/P3源码、原始Q或训练过程。LamaH-CE v1.0，DOI 10.5281/zenodo.5153305。依据原来源说明遵守CC BY-SA 4.0归属与共享条件，ERA5-Land流域气象；不得称为锡尔河成绩。
先按SHA256SUMS.txt核验发布包。模型.json内绝对路径仅为历史来源证据，推理不会打开它们。
输入为date、gauge_id、P(mm/月)、T(°C)，L1模型必须含前一自然月P。未提供、非有限、单位错、跨站及目标Q字段均拒绝。
示例（在此目录执行）：
python -B runtime/inference.py --model models/ID_2/P2-L1 --met example_MET_ID2.json --start 2016-01 --end 2016-12 --output example_predictions.csv
该例仅演示V2磁盘推理，V2已经使用这些年份标签，绝不可将示例预测作为新的样本外成绩。独立遮蔽精度请见P4主目录MASKED_DEMO产物。
API: 将runtime目录加入sys.path，from inference import load_model,predict_month,predict_range。
每月输出风险及资格；DEFAULT仅在气象完整、区间有效、非HIGH_EXTRAPOLATION时适用，不保证单站提升或严格区间覆盖。
""",encoding="utf-8")
seal(out);verify(out)
res=P/"evidence/PORTABLE_V2_FRESH_PROCESS.csv"
cp=subprocess.run([sys.executable,"-B",str(out/"runtime/inference.py"),"--model",str(out/"models/ID_2/P2-L1"),"--met",str(out/"example_MET_ID2.json"),"--start","2016-01","--end","2016-12","--output",str(res)],cwd=str(P),capture_output=True,text=True,check=True)
jw(P/"evidence/PORTABLE_RELEASE_VERIFICATION.json",{"UTC":now(),"release":str(out),"seal":sha(out/"SHA256SUMS.txt"),"all_models":54,"fresh_process_returncode":cp.returncode,"stdout":cp.stdout,"not_sample_out_prediction":True,"original_Q_not_required":True,"training_code_not_imported":True,"api_difference":"only pinned expected P2 math hash instead of opening original math source file"})
shutil.make_archive(str(P/"release/P4_PUBLIC_V2"),"zip",root_dir=out)
print(json.dumps({"portable_models":54,"zip_bytes":(P/"release/P4_PUBLIC_V2.zip").stat().st_size,"fresh_process":cp.stdout.strip()}))
