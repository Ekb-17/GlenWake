# GlenWake

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the staged roadmap, current implementation status, and required validation. The ZIP is milestone 1 only; later AI capabilities remain planned until implemented and tested.

GlenWake is a video-based cleanup evidence and verification project, separate from EarthRelay. Its end goal is to distinguish leftover, moved, newly deposited, and unresolved waste through inspectable evidence, corrections, and reviewed reports. These later capabilities are planned.

The current application is a local workspace for reviewing cleanup recordings. This first milestone lets you upload a video, draw a fixed monitoring area, mark the cleanup start and end, add timestamped observations, save the review, and reopen it. Annotations are **manual**. Automated waste detection, coverage percentages, event attribution and accuracy claims are not implemented yet.

## Run on Windows in Cursor

Open the **GlenWake** folder in Cursor. Open a terminal with **Terminal → New Terminal**. These commands are for PowerShell; enter one line at a time. You need Python 3.12 and Node.js/npm installed.

Terminal 1 (API):

```powershell
cd backend
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
```

Keep that terminal open. Open **a second terminal** with Terminal → New Terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173` in your browser. If a new terminal starts somewhere other than the GlenWake folder, use Cursor's **File → Open Folder** to open GlenWake first. To stop either server, press `Ctrl+C` in its terminal.

Upload an MP4 or WebM recording under 200 MB. MOV upload is supported, but some MOV codecs cannot play in a browser; convert such a clip to H.264 MP4 before review. For now use footage from a fixed camera. Play and pause, draw the monitoring rectangle, mark the cleanup times, add observations, and press **Save review**. Refresh the page or choose the session again to check persistence. Each observation's time button seeks the video to that moment.

Videos and reviews are stored locally in `backend/data/`. That folder is ignored by Git; do not add private footage to source control. If you delete it, you delete those local sessions. This is a single-user development app; do not expose the API to the public internet.

## Run checks

From the `backend` folder, after creating the virtual environment above:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

The backend test covers upload, saving and reopening reviews, video streaming/range requests, and rejection of invalid time markers and file extensions. It uses a temporary data folder.

From the `frontend` folder:

```powershell
npm.cmd ci
npm.cmd run build
```

The frontend check compiles TypeScript and creates the production bundle; it does not test browser interactions.

## Implementation status

- `frontend/`: React, TypeScript and Vite review screen.
- `backend/`: FastAPI, SQLite metadata and local video files.
- Next milestones: validate real litter segmentation on held-out footage, measure coverage only from verified masks inside the marked area, then add evidence-linked event attribution, revisions, reviewed report export, and held-out comparisons. Never infer successful cleanup merely because something left the camera view.

If `python` or `py` is missing on this computer, the explicit Python path above uses the working Python 3.12 install. In PowerShell, `npm.cmd` avoids the `npm.ps1` execution-policy issue. In Command Prompt, use `npm` instead.
