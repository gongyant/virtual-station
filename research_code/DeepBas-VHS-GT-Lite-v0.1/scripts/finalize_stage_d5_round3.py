"""Create the final non-circular Stage D5 round-3 freeze manifest."""

from __future__ import print_function

import datetime
import hashlib
import json
import os


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
OUT = os.path.join(ROOT,"outputs","diagnosis_2005_snapshot","stage_d5_round3")
MANIFEST = os.path.join(OUT,"stage_d5_round3_manifest.json")


def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def main():
    files=[]
    for base,dirs,names in os.walk(OUT):
        dirs.sort()
        for name in sorted(names):
            path=os.path.join(base,name)
            if os.path.abspath(path)==os.path.abspath(MANIFEST) or name.endswith(".inspect.ndjson"):
                continue
            files.append({"file_path":os.path.relpath(path,ROOT).replace(os.sep,"/"),"sha256":sha256(path),"file_size":os.path.getsize(path)})
    payload={
        "stage":"D5_round3","status":"complete_and_frozen","frozen_at":datetime.datetime.now().isoformat(),
        "scope":"M2 reparameterization, memory, annual bias attribution, and additional-input admission audit",
        "round2_decision_unchanged":"reject_current_single_upstream_model_family",
        "selected_next_branch":"M2C_single_storage_plus_interval_weather",
        "frozen_single_candidate_variable":"interval_snowmelt_mm_antecedent_14d",
        "constraints_confirmed":{"new_model_trained":False,"new_model_nse_generated":False,"2011_used_for_selection":False,"M3_authorized":False,"GNN_used":False,"round2_overwritten":False},
        "file_count":len(files),"files":files,
    }
    with open(MANIFEST,"w") as handle:
        json.dump(payload,handle,ensure_ascii=False,indent=2,sort_keys=True);handle.write("\n")
    print(MANIFEST);print(sha256(MANIFEST))


if __name__=="__main__":
    main()
