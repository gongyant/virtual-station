from pathlib import Path
import sys
P=Path(__file__).resolve().parents[1];R=P.parent;P2=R/"p2_antecedent_snow_features"
sys.path.insert(0,str(R/"code/vendor_public"))
sys.path.insert(0,str(P2/"P2_MODEL_CODE"))
sys.path.insert(0,str(P/"code"))
