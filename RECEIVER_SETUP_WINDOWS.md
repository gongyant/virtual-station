# Receiver setup (Windows)

1. Unzip to any folder, e.g. `D:\VHS_FULL_HANDOFF\`.
2. Need Python 3.10+ with stdlib only for the website host (original server is stdlib HTTP).
3. Optional: point `-Python` at an existing venv that already has project scientific deps if you will run research_code (do **not** pip install from internet in locked labs unless allowed).
4. Run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\check_prereqs.ps1
   powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1 -Port 8805
   ```
5. Open `http://127.0.0.1:8805/`
6. Stop: `.\scripts\stop_windows.ps1`

Does **not** require original `E:\` lab paths or ports 8794/8795.
