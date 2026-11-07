from pathlib import Path
import sys
P=Path(__file__).resolve().parents[1]; ROOT=P.parent
sys.path.insert(0,str(ROOT/"code/vendor_public"))
sys.path.insert(0,str(P/"code"))
