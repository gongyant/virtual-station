
import json,subprocess,sys
from pathlib import Path
R=Path(r"E:\VHS_Public_Baseline_Lab");S=Path(r"C:\Users\Administrator\.codex\skills\nature-figure\scripts")
records=[]
cmd=[sys.executable,"-B",str(S/"validate_figure.py"),str(R/"code/plot_public_results.py"),"--json"]
p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8");source=json.loads(p.stdout)
(R/"evidence/FIGURE_SOURCE_FINAL_QA.json").write_text(p.stdout,encoding="utf-8")
assert p.returncode==0,p.stdout
for pdf in sorted((R/"reports/figures").glob("*.pdf")):
 p=subprocess.run([sys.executable,"-B",str(S/"audit_pdf_text.py"),str(pdf),"--min-pt","5","--json"],capture_output=True,text=True,encoding="utf-8")
 try:res=json.loads(p.stdout)
 except ValueError:res={"output":p.stdout,"stderr":p.stderr}
 records.append({"file":pdf.name,"glyph_floor_exit":p.returncode,"glyph_check":res})
 assert p.returncode==0,(pdf,p.stdout,p.stderr)
# Required rendered collision check is attempted; dependency absence must not be presented as PASS.
pdf=next((R/"reports/figures").glob("*.pdf"))
p=subprocess.run([sys.executable,"-B",str(S/"audit_figure_collisions.py"),str(pdf),"--json-out",str(R/"evidence/COLLISION_AUDIT.json")],capture_output=True,text=True,encoding="utf-8")
collision={"returncode":p.returncode,"stdout":p.stdout,"stderr":p.stderr,"status":"NOT_AUDITABLE_MISSING_PYMUPDF" if p.returncode==2 else "INSPECT_RESULT"}
qa={"source_validation":"PASS","PDF_text_floor_5pt":"PASS_ALL_6","glyph_results":records,"single_panel_alignment":"NOT_APPLICABLE; six separate one-axis figures, render manifests saved","rendered_collision_check":collision,"manual_visual_review":"All6 PNGs inspected; whole120-month sequences, correct rawOOF/observations labels, sparse missing-year gaps kept, no clipped labels observed","submission_ready_claim":False}
(R/"evidence/FIGURE_QA_SUMMARY.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"source":"PASS","PDF_text_floor":"PASS6","collision":collision["status"],"training_results_affected":False}))

