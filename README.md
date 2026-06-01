# Embodied Visual Memory

Step 1 builds the visual input pipeline: laptop webcam capture, timestamped observations, saved frame runs, and replay.

## What you do

1. Open the project folder: `D:\embodied-visual-memory`
2. Install dependencies once:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Capture a short webcam run:

   ```powershell
   python -m evm.cli capture-webcam --run-name first_webcam_test --seconds 10
   ```

4. Replay it:

   ```powershell
   python -m evm.cli replay data\runs\first_webcam_test
   ```

## Controls

- Capture: press `q` to stop early.
- Replay: press `space` to pause, `n` for next frame while paused, `q` to quit.

## Output

Each run is saved under `data\runs\<run-name>` with:

- `frames\*.jpg`: captured images
- `observations.jsonl`: one observation record per frame
- `manifest.json`: run summary

## Step 2: Detect Objects

Run object detection on a saved capture:

```powershell
python -m evm.cli detect data\runs\my_first_test --frame-stride 5
```

Show the memory summary:

```powershell
python -m evm.cli summarize data\runs\my_first_test
```

Step 2 adds:

- `detections.jsonl`: one object detection record per detected object
- `annotated_frames\*.jpg`: frames with bounding boxes drawn
- `memory_summary.json`: simple object memory by label

## Step 3: Track Object Identity

Group repeated detections into likely same-object tracks:

```powershell
python -m evm.cli track data\runs\my_first_test
python -m evm.cli summarize-tracks data\runs\my_first_test
```

Step 3 adds:

- `tracks.jsonl`: detection records with stable track IDs like `bottle_001`
- `track_summary.json`: first/last seen summary for each tracked object instance

## Step 4: Query Visual Memory

List everything the run remembers:

```powershell
python -m evm.cli list-memory data\runs\my_first_test
```

Ask where an object was last seen:

```powershell
python -m evm.cli query-memory data\runs\my_first_test bottle
```

Step 4 reads the tracked visual memory and answers with:

- matched object label and track ID
- last-seen timestamp and frame
- supporting frame path

## Step 5: Compare Two Runs

Compare a before scan and an after scan:

```powershell
python -m evm.cli compare-runs data\runs\before_scan data\runs\after_scan
```

Step 5 adds `change_report.json` to the after-run folder with:

- appeared objects
- disappeared objects
- still-present objects
- moved objects based on image-center shift

## Step 6: One-Command Webcam Scan

Capture, detect, track, annotate, and prepare memory in one command:

```powershell
python -m evm.cli scan-webcam --run-name desk_scan --seconds 10
```

Then query it:

```powershell
python -m evm.cli list-memory data\runs\desk_scan
python -m evm.cli query-memory data\runs\desk_scan bottle
```
