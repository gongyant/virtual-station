"""Freeze Stage D5 round 4 after the single authorized development run."""

from __future__ import print_function

import datetime
import hashlib
import json
import os


ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir))
OUT=os.path.join(ROOT,"outputs","diagnosis_2005_snapshot","stage_d5_round4")
MANIFEST=os.path.join(OUT,"stage_d5_round4_manifest.json")


def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()


def main():
    decision=json.load(open(os.path.join(OUT,"m2c_development_promotion_decision.json"),encoding="utf-8"))
    if decision["decision"]!="reject_M2C_interval_snowmelt" or decision["transfer_authorized"]:
        raise SystemExit("unexpected decision; manifest stop logic not applicable")
    forbidden=["m2r_frozen_parameters_1978_1983.json","m2c_frozen_parameters_1978_1983.json","retro_transfer_predictions_frozen.csv","retro_transfer_metrics.csv"]
    if any(os.path.exists(os.path.join(OUT,x)) for x in forbidden):raise SystemExit("unauthorized transfer artifact exists")
    files=[]
    for base,dirs,names in os.walk(OUT):
        dirs.sort()
        for name in sorted(names):
            path=os.path.join(base,name)
            if os.path.abspath(path)==os.path.abspath(MANIFEST) or name.endswith(".inspect.ndjson"):continue
            files.append({"file_path":os.path.relpath(path,ROOT).replace(os.sep,"/"),"sha256":sha256(path),"file_size":os.path.getsize(path)})
    payload={"stage":"D5_round4","status":"complete_rejected_and_frozen","frozen_at":datetime.datetime.now().isoformat(),"evaluation_identity":"M2C developmental nested leave-one-year-out robustness evaluation","decision":"reject_M2C_interval_snowmelt","promotion_gates_passed":11,"promotion_gates_total":12,"failed_gate":"year_1979_underestimate_relieved","transfer_authorized":False,"transfer_predictions_generated":False,"transfer_labels_read":False,"other_candidates_tried":False,"M3_authorized":False,"upstream_round2_round3_overwritten":False,"file_count":len(files),"files":files}
    with open(MANIFEST,"w") as f:json.dump(payload,f,ensure_ascii=False,indent=2,sort_keys=True);f.write("\n")
    print(MANIFEST);print(sha256(MANIFEST))


if __name__=="__main__":main()
