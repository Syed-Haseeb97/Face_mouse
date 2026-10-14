# Face Mouse

Hands-free mouse for Windows 10/11 using any webcam. Your head moves the cursor; winking one eye clicks; holding one eye closed holds the mouse button (drag and drop). Everything runs locally; frames are processed in memory and never written to disk.

## Requirements

* Windows 10/11, **Python 3.10, 3.11 or 3.12** (64-bit) from python.org
* A webcam (built-in, USB, or a phone camera that Windows exposes as a camera)
* Packages in `requirements.txt` (MediaPipe, OpenCV, NumPy, pygrabber). Tkinter ships with python.org Python.

Note: `mediapipe` must be 0.10.x below 0.10.22 (pinned) because the app uses its FaceMesh "solutions" API, which newer releases removed.

## Install (PowerShell)

```powershell
cd path\to\face_mouse
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks the activate script: `Set-ExecutionPolicy -Scope Process Bypass`, then activate again.

## Launch

```powershell
python main.py
python main.py --list-cameras
python main.py --dry-run
```

Settings are stored in `%APPDATA%\FaceMouse\config.json`.

## First run

1. Pick your camera in the **Camera** drop-down. The choice is saved and reused next launch; if it is missing the app falls back to another camera and says which one is active.
2. Click **Calibrate...** and follow the prompts: centre your face, look at the screen with eyes open, optionally close only the left and right eye for wink samples, then tune sensitivity, hold duration, smoothing and dead zone.
3. Click **Start**. Turn **Preview** off for normal use to save CPU.

## Gestures

| Gesture | Result |
|---|---|
| Move head (left/right/up/down) | Cursor moves that way. Speed grows with distance from neutral; inside the dead zone it does not move. |
| Close only left eye ~0.1-0.45 s | One left click |
| Close only right eye ~0.1-0.45 s | One right click |
| Normal two-eye blink | Ignored |
| Hold left eye closed >0.6 s | Left button DOWN; move head to drag; open eye to release |
| Hold right eye closed >0.6 s | Right button DOWN until eye opens; can be disabled |

## Safety

* **Emergency stop: `Ctrl+Alt+F12`** releases both buttons, blocks mouse output and disables gestures.
* `Ctrl+Alt+F11` pauses/resumes control; `Ctrl+Alt+F10` recentres.
* Buttons are released on exit, camera failure/disconnect, prolonged face loss, processing exceptions, watchdog timeout, pausing and Ctrl+C.

## Configuration

The Settings window exposes cursor, eye, gesture and system controls. Important defaults include sensitivity 5, dead zone 0.025, smoothing 0.6, click duration 90-450 ms, hold duration 600 ms, cooldown 300 ms, face-loss release 500 ms, and yaw limit 0.5.

## Running tests

```powershell
python -m unittest discover -s tests -t . -v
```

Tests use fake mouse/camera backends and scripted landmarks, so they do not move your real cursor or open a real camera.

## Troubleshooting

* **Camera list shows Camera 0/1 instead of names:** install `pygrabber comtypes`.
* **Phone camera not listed:** the app lists whatever Windows exposes as a normal video-capture device. Make sure the phone camera is active, click **Refresh**, and try the `msmf` backend.
* **Camera cannot open/no frames:** close Teams, Zoom, Camera, etc., and check Windows camera privacy permissions.
* **MediaPipe has no solutions:** install the pinned 0.10.x release.
* **Clicks fail in elevated windows:** run Face Mouse as administrator for those windows.
* **Accidental/missed winks:** rerun calibration and adjust the eye thresholds, click timing, or other-eye threshold.
* **Cursor drifts:** increase dead zone or use recenter.

## Known limitations

* Cursor control is rate-based rather than absolute pointing, so sensitivity/dead-zone tuning is personal.
* Winking is difficult for some users, especially if the other eye squints too.
* Looking strongly downward can make both eyes appear closed and is treated as a normal blink.
* Camera identity uses the Windows device name, with `#2` for duplicates.
* A forcibly killed process while holding a button can leave the OS mouse button logically down; a physical click clears it.
* The current implementation uses a compact control window rather than a tray icon.
