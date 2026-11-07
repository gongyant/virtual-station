from pathlib import Path
import sys
P=Path(__file__).resolve().parents[1];R=P.parent
sys.path.insert(0,str(R/"code/vendor_public"))
sys.path.insert(0,str(P/"P2_MODEL_CODE"))
