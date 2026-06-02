from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from evm.cli import (
    DEFAULT_RUNS_DIR,
    run_detection_for_dir,
    run_tracking_for_dir,
)
from evm.query import find_best_track
from evm.report import build_run_report
from evm.sources import VideoFileSource
from evm.storage import RunWriter
from evm.tracking import TrackSummary, summarize_tracks
from evm.cli import load_tracks


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "data" / "runs"
VIDEOS_DIR = PROJECT_ROOT / "data" / "videos"
UPLOADS_DIR = VIDEOS_DIR / "uploads"

app = FastAPI(title="Embodied Visual Memory")
app.mount("/runs", StaticFiles(directory=RUNS_DIR), name="runs")


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #647085;
      --line: #d9e0ea;
      --panel: #ffffff;
      --bg: #f5f7fa;
      --accent: #2563eb;
      --accent-dark: #1746a2;
      --ok: #166534;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    header {{
      padding: 18px 28px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    header a {{ color: var(--ink); text-decoration: none; }}
    nav {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }}
    nav a {{
      padding: 8px 10px;
      border-radius: 6px;
      background: #eef2f7;
      border: 1px solid var(--line);
      font-size: 13px;
      font-weight: 700;
    }}
    h1 {{ margin: 0; font-size: 22px; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 18px;
      align-items: start;
    }}
    .panel, .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .stack {{ display: grid; gap: 12px; }}
    label {{ display: block; font-weight: 700; font-size: 13px; margin-bottom: 6px; }}
    input, select {{
      width: 100%;
      border: 1px solid #c6d0df;
      border-radius: 6px;
      padding: 10px 11px;
      font-size: 14px;
      background: #fff;
    }}
    button, .button {{
      border: 0;
      border-radius: 6px;
      padding: 10px 12px;
      font-weight: 700;
      color: white;
      background: var(--accent);
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
    }}
    button:hover, .button:hover {{ background: var(--accent-dark); }}
    .button.secondary {{
      background: #eef2f7;
      color: var(--ink);
      border: 1px solid var(--line);
    }}
    .muted {{ color: var(--muted); font-size: 13px; line-height: 1.4; }}
    .run-list {{ display: grid; gap: 8px; }}
    .run-link {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fafbfc;
      color: var(--ink);
      text-decoration: none;
    }}
    .memory-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 14px;
    }}
    .memory-card img {{
      width: 100%;
      aspect-ratio: 16 / 10;
      object-fit: cover;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #eef2f7;
      margin-bottom: 10px;
    }}
    .memory-card h3 {{ margin: 0 0 8px; font-size: 17px; }}
    .memory-card p {{ margin: 4px 0; font-size: 13px; line-height: 1.35; }}
    .answer {{
      border-left: 4px solid var(--ok);
      background: #f0fdf4;
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 14px;
    }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    video.preview {{
      width: 100%;
      aspect-ratio: 16 / 10;
      object-fit: cover;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0f172a;
    }}
    .status {{
      min-height: 20px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }}
    .lesson-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 16px;
    }}
    .lesson-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .lesson-card p, .lesson-card li {{
      font-size: 14px;
      line-height: 1.45;
      color: #2b3648;
    }}
    .diagram {{
      width: 100%;
      min-height: 190px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      margin-bottom: 12px;
      overflow: hidden;
    }}
    .formula {{
      font-family: Consolas, monospace;
      background: #f1f5f9;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      font-size: 13px;
      overflow-x: auto;
    }}
    .wide {{
      grid-column: 1 / -1;
    }}
    @media (max-width: 860px) {{
      header {{ position: static; align-items: flex-start; flex-direction: column; }}
      main {{ padding: 14px; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <a href="/"><h1>Embodied Visual Memory</h1></a>
    <nav>
      <a href="/">Dashboard</a>
      <a href="/learn">Learn CV Basics</a>
    </nav>
  </header>
  <main>{body}</main>
</body>
</html>"""
    )


def run_names() -> list[str]:
    if not RUNS_DIR.exists():
        return []
    return sorted([path.name for path in RUNS_DIR.iterdir() if path.is_dir()], reverse=True)


def load_track_summaries(run_name: str) -> list[TrackSummary]:
    run_dir = RUNS_DIR / run_name
    tracks_path = run_dir / "tracks.jsonl"
    if not tracks_path.exists():
        return []
    return summarize_tracks(load_tracks(run_dir))


def run_list_html(selected: str | None = None) -> str:
    items = []
    for name in run_names():
        marker = "selected" if name == selected else ""
        items.append(f'<a class="run-link" href="/runs-view/{name}"><span>{name}</span><span>{marker}</span></a>')
    return "\n".join(items) if items else '<p class="muted">No runs yet. Scan a video to create one.</p>'


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    body = f"""
    <div class="grid">
      <section class="panel stack">
        <h2>Open Webcam And Scan</h2>
        <video id="webcamPreview" class="preview" autoplay muted playsinline></video>
        <div>
          <label for="webcam_run_name">Run name</label>
          <input id="webcam_run_name" value="webcam_demo">
        </div>
        <div class="actions">
          <button type="button" id="startWebcam">Open Webcam</button>
          <button type="button" id="record3">Record 3 Sec</button>
          <button type="button" id="record5">Record 5 Sec</button>
        </div>
        <p id="webcamStatus" class="status">Open the webcam, then record a short clip. The app will upload and scan it automatically.</p>
      </section>
      <section class="panel stack">
        <h2>Upload And Scan A Video</h2>
        <form class="stack" action="/upload-video" method="post" enctype="multipart/form-data">
          <div>
            <label for="video_file">Video file</label>
            <input id="video_file" name="video_file" type="file" accept="video/*" required>
          </div>
          <div>
            <label for="upload_run_name">Run name</label>
            <input id="upload_run_name" name="run_name" value="uploaded_demo">
          </div>
          <button type="submit">Upload And Scan</button>
          <p class="muted">Choose an MP4, MOV, or WebM from this PC. The app saves it locally, scans it, and opens the memory results.</p>
        </form>
      </section>
      <section class="panel stack">
        <h2>Scan A Video Path</h2>
        <form class="stack" action="/scan-video" method="post">
          <div>
            <label for="video_path">Video path</label>
            <input id="video_path" name="video_path" value="D:\\02bdec3c-263f-42b4-a3ba-25e914dbc44a.mp4">
          </div>
          <div>
            <label for="run_name">Run name</label>
            <input id="run_name" name="run_name" value="mobile_demo">
          </div>
          <button type="submit">Scan Video</button>
          <p class="muted">This runs the existing Python pipeline. It may take a little while for longer videos.</p>
        </form>
      </section>
      <section class="panel stack">
        <h2>Saved Runs</h2>
        <div class="run-list">{run_list_html()}</div>
      </section>
    </div>
    <script>
      const preview = document.getElementById('webcamPreview');
      const statusText = document.getElementById('webcamStatus');
      const startButton = document.getElementById('startWebcam');
      const record3Button = document.getElementById('record3');
      const record5Button = document.getElementById('record5');
      let webcamStream = null;

      function setStatus(message) {{
        statusText.textContent = message;
      }}

      async function openWebcam() {{
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
          throw new Error('This browser does not expose webcam access. Try Chrome/Edge on localhost.');
        }}
        if (webcamStream) {{
          return webcamStream;
        }}
        webcamStream = await navigator.mediaDevices.getUserMedia({{ video: true, audio: false }});
        preview.srcObject = webcamStream;
        setStatus('Webcam is open. Choose 3 or 5 seconds to record.');
        return webcamStream;
      }}

      function chooseMimeType() {{
        if (typeof MediaRecorder === 'undefined') {{
          return null;
        }}
        const candidates = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
        return candidates.find(type => MediaRecorder.isTypeSupported(type)) || '';
      }}

      async function recordAndUpload(seconds) {{
        try {{
          if (typeof MediaRecorder === 'undefined') {{
            throw new Error('This browser cannot record webcam video. Try Chrome/Edge.');
          }}
          const stream = await openWebcam();
          const chunks = [];
          const mimeType = chooseMimeType();
          const recorder = new MediaRecorder(stream, mimeType ? {{ mimeType }} : undefined);
          recorder.ondataavailable = event => {{
            if (event.data && event.data.size > 0) {{
              chunks.push(event.data);
            }}
          }};
          const stopped = new Promise(resolve => {{
            recorder.onstop = resolve;
          }});
          recorder.start();
          setStatus(`Recording ${{seconds}} seconds...`);
          await new Promise(resolve => setTimeout(resolve, seconds * 1000));
          recorder.stop();
          await stopped;
          const blob = new Blob(chunks, {{ type: mimeType || 'video/webm' }});
          const runNameInput = document.getElementById('webcam_run_name');
          const runName = (runNameInput.value || 'webcam_demo').trim();
          const data = new FormData();
          data.append('run_name', runName);
          data.append('video_file', blob, `${{runName}}.webm`);
          setStatus('Uploading and scanning. This may take a little while...');
          const response = await fetch('/upload-video', {{
            method: 'POST',
            body: data,
            redirect: 'follow'
          }});
          window.location.href = response.url || `/runs-view/${{encodeURIComponent(runName)}}`;
        }} catch (error) {{
          setStatus(`Webcam scan failed: ${{error.message}}`);
        }}
      }}

      startButton.addEventListener('click', () => {{
        openWebcam().catch(error => setStatus(`Could not open webcam: ${{error.message}}`));
      }});
      record3Button.addEventListener('click', () => recordAndUpload(3));
      record5Button.addEventListener('click', () => recordAndUpload(5));
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === 'undefined') {{
        setStatus('Webcam recording is not available in this browser. Upload a video file instead, or use Chrome/Edge on localhost.');
      }}
    </script>
    """
    return page("Embodied Visual Memory", body)


@app.get("/learn", response_class=HTMLResponse)
def learn() -> HTMLResponse:
    body = """
    <section class="panel stack" style="margin-bottom: 18px;">
      <h2>Computer Vision Basics For This Project</h2>
      <p class="muted">
        This page explains the core ideas behind the visual-memory bot from the ground up:
        pixels, color, 3D-to-2D projection, edges, convolution, neural networks, detection,
        segmentation, depth, embeddings, tracking, and how they connect.
      </p>
    </section>

    <section class="lesson-grid">
      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Pixel grid">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <g transform="translate(38 28)">
            <rect width="144" height="144" fill="#e5edf7" stroke="#9fb0c7"/>
            <g stroke="#9fb0c7">
              <path d="M36 0v144M72 0v144M108 0v144M0 36h144M0 72h144M0 108h144"/>
            </g>
            <rect x="72" y="36" width="36" height="36" fill="#2563eb"/>
            <text x="72" y="170" font-size="13" fill="#172033">An image is a grid of pixels</text>
          </g>
          <g transform="translate(230 58)">
            <rect width="78" height="78" fill="#2563eb"/>
            <text x="-8" y="105" font-size="13" fill="#172033">one pixel</text>
            <text x="-18" y="124" font-size="12" fill="#647085">stores color values</text>
          </g>
        </svg>
        <h3>1. What Is An Image?</h3>
        <p>An image is just a rectangular grid of tiny squares called pixels. Each pixel stores numbers. Computer vision starts by reading those numbers, not by “seeing” like a human.</p>
        <div class="formula">image = height x width x color_channels</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="RGB color channels">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <circle cx="110" cy="92" r="48" fill="#ef4444" fill-opacity=".75"/>
          <circle cx="170" cy="92" r="48" fill="#22c55e" fill-opacity=".75"/>
          <circle cx="140" cy="142" r="48" fill="#3b82f6" fill-opacity=".75"/>
          <text x="100" y="92" font-size="16" fill="#fff" font-weight="700">R</text>
          <text x="166" y="92" font-size="16" fill="#fff" font-weight="700">G</text>
          <text x="136" y="148" font-size="16" fill="#fff" font-weight="700">B</text>
          <text x="225" y="82" font-size="13" fill="#172033">red channel</text>
          <text x="225" y="108" font-size="13" fill="#172033">green channel</text>
          <text x="225" y="134" font-size="13" fill="#172033">blue channel</text>
        </svg>
        <h3>2. Color And Channels</h3>
        <p>Most camera images use RGB: red, green, and blue. A pixel might be stored as three numbers, such as R=40, G=120, B=230. Different combinations create different colors.</p>
        <div class="formula">pixel = [R, G, B]</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="3D to 2D camera projection">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <polygon points="45,105 170,45 170,165" fill="#dbeafe" stroke="#2563eb"/>
          <rect x="170" y="45" width="6" height="120" fill="#172033"/>
          <circle cx="45" cy="105" r="10" fill="#ef4444"/>
          <circle cx="270" cy="85" r="14" fill="#22c55e"/>
          <circle cx="270" cy="135" r="14" fill="#f59e0b"/>
          <line x1="45" y1="105" x2="270" y2="85" stroke="#647085" stroke-dasharray="4 4"/>
          <line x1="45" y1="105" x2="270" y2="135" stroke="#647085" stroke-dasharray="4 4"/>
          <circle cx="174" cy="100" r="4" fill="#22c55e"/>
          <circle cx="174" cy="116" r="4" fill="#f59e0b"/>
          <text x="20" y="135" font-size="12" fill="#172033">camera</text>
          <text x="192" y="34" font-size="12" fill="#172033">2D image plane</text>
          <text x="246" y="165" font-size="12" fill="#172033">3D world objects</text>
        </svg>
        <h3>3. Cameras Project 3D Into 2D</h3>
        <p>A real room is 3D, but a normal camera produces a flat 2D image. Many different 3D scenes can create similar 2D images, which is why depth is hard.</p>
        <div class="formula">3D point (X,Y,Z) -> 2D pixel (u,v)</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Camera intrinsics">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <rect x="68" y="38" width="224" height="134" fill="#eef2f7" stroke="#94a3b8"/>
          <line x1="180" y1="38" x2="180" y2="172" stroke="#647085" stroke-dasharray="5 5"/>
          <line x1="68" y1="105" x2="292" y2="105" stroke="#647085" stroke-dasharray="5 5"/>
          <circle cx="180" cy="105" r="6" fill="#2563eb"/>
          <path d="M180 105 C210 70, 240 55, 270 48" stroke="#ef4444" fill="none" stroke-width="3"/>
          <text x="190" y="101" font-size="12" fill="#172033">principal point</text>
          <text x="212" y="70" font-size="12" fill="#172033">focal behavior</text>
          <text x="78" y="190" font-size="12" fill="#172033">intrinsics describe the camera's internal geometry</text>
        </svg>
        <h3>4. Camera Intrinsics</h3>
        <p>Camera intrinsics are numbers that describe the camera itself: focal length, image center, and distortion. They matter when converting pixels into rays or estimating 3D position.</p>
        <div class="formula">K = [[fx,0,cx], [0,fy,cy], [0,0,1]]</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Edges and gradients">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <rect x="50" y="45" width="110" height="120" fill="#172033"/>
          <rect x="160" y="45" width="110" height="120" fill="#e2e8f0"/>
          <line x1="160" y1="35" x2="160" y2="178" stroke="#ef4444" stroke-width="5"/>
          <path d="M60 185 h30 l20 -40 l18 22 l26 -58 l24 76 h34" fill="none" stroke="#2563eb" stroke-width="3"/>
          <text x="55" y="30" font-size="13" fill="#172033">dark</text>
          <text x="222" y="30" font-size="13" fill="#172033">bright</text>
          <text x="175" y="190" font-size="12" fill="#172033">big intensity change = edge</text>
        </svg>
        <h3>5. Edges And Gradients</h3>
        <p>An edge is where pixel values change sharply. A gradient measures how fast brightness or color changes. Older CV systems relied heavily on edges; modern neural nets still learn edge-like patterns early.</p>
        <div class="formula">gradient ≈ change in pixel value / change in position</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Convolution kernel">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <g transform="translate(38 40)">
            <rect width="108" height="108" fill="#eef2f7" stroke="#94a3b8"/>
            <g stroke="#94a3b8"><path d="M36 0v108M72 0v108M0 36h108M0 72h108"/></g>
            <text x="18" y="62" font-size="14">pixels</text>
          </g>
          <text x="166" y="98" font-size="28" fill="#172033">×</text>
          <g transform="translate(205 40)">
            <rect width="108" height="108" fill="#dbeafe" stroke="#2563eb"/>
            <g stroke="#2563eb"><path d="M36 0v108M72 0v108M0 36h108M0 72h108"/></g>
            <text x="14" y="62" font-size="14">kernel</text>
          </g>
          <text x="93" y="180" font-size="13" fill="#172033">slide small filter across image to find patterns</text>
        </svg>
        <h3>6. Convolution</h3>
        <p>Convolution is the core operation behind many vision networks. A small filter slides across the image and responds to patterns like edges, corners, textures, or object parts.</p>
        <div class="formula">output pixel = sum(image patch × kernel weights)</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Neural network vision hierarchy">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <g fill="#dbeafe" stroke="#2563eb">
            <rect x="24" y="65" width="58" height="80" rx="6"/>
            <rect x="116" y="50" width="58" height="110" rx="6"/>
            <rect x="208" y="38" width="58" height="134" rx="6"/>
            <rect x="300" y="70" width="36" height="70" rx="6"/>
          </g>
          <g stroke="#647085" marker-end="url(#arrow)">
            <line x1="82" y1="105" x2="116" y2="105"/>
            <line x1="174" y1="105" x2="208" y2="105"/>
            <line x1="266" y1="105" x2="300" y2="105"/>
          </g>
          <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#647085"/></marker></defs>
          <text x="31" y="103" font-size="12">edges</text>
          <text x="123" y="103" font-size="12">parts</text>
          <text x="214" y="103" font-size="12">objects</text>
          <text x="304" y="103" font-size="12">label</text>
        </svg>
        <h3>7. How Neural Networks See</h3>
        <p>Early layers learn simple patterns like edges. Middle layers learn parts and textures. Later layers combine those features into object-level understanding.</p>
        <div class="formula">pixels -> features -> object prediction</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Object detection box">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <rect x="45" y="35" width="260" height="140" fill="#eef2f7" stroke="#cbd5e1"/>
          <rect x="118" y="60" width="86" height="92" fill="none" stroke="#22c55e" stroke-width="4"/>
          <text x="118" y="52" font-size="14" fill="#166534" font-weight="700">cup 0.71</text>
          <rect x="224" y="84" width="58" height="82" fill="none" stroke="#2563eb" stroke-width="4"/>
          <text x="224" y="78" font-size="14" fill="#1746a2" font-weight="700">book 0.62</text>
        </svg>
        <h3>8. Object Detection</h3>
        <p>Object detection predicts what objects are present and where they are. In this project, YOLO outputs a label, confidence score, and bounding box coordinates.</p>
        <div class="formula">detection = label + confidence + [x1,y1,x2,y2]</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Segmentation mask">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <rect x="50" y="38" width="260" height="142" fill="#eef2f7" stroke="#cbd5e1"/>
          <path d="M142 60 C188 46, 232 76, 222 124 C210 172, 142 172, 124 132 C106 92, 114 70, 142 60Z" fill="#22c55e" fill-opacity=".55" stroke="#166534" stroke-width="3"/>
          <text x="92" y="194" font-size="13" fill="#172033">segmentation marks object pixels, not just a box</text>
        </svg>
        <h3>9. Segmentation</h3>
        <p>Segmentation finds the exact pixels belonging to an object. Our current project uses boxes, not masks. Segmentation would be a future upgrade for cleaner object shapes.</p>
        <div class="formula">mask pixel = object or background</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Depth map">
          <defs>
            <linearGradient id="depth" x1="0" x2="1">
              <stop offset="0" stop-color="#1e3a8a"/>
              <stop offset=".5" stop-color="#22c55e"/>
              <stop offset="1" stop-color="#f59e0b"/>
            </linearGradient>
          </defs>
          <rect width="360" height="210" fill="#fbfcfe"/>
          <rect x="54" y="42" width="250" height="128" fill="url(#depth)" stroke="#94a3b8"/>
          <circle cx="105" cy="110" r="28" fill="#f59e0b" fill-opacity=".9"/>
          <circle cx="245" cy="92" r="32" fill="#1e3a8a" fill-opacity=".85"/>
          <text x="65" y="190" font-size="12" fill="#172033">warm = closer, blue = farther (example depth visualization)</text>
        </svg>
        <h3>10. Depth And 3D Position</h3>
        <p>Depth tells how far each pixel/object is from the camera. Normal phone video does not provide reliable depth by default, so our current project mostly works in 2D image space.</p>
        <div class="formula">with depth: pixel (u,v) + depth Z -> 3D point</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Embeddings vectors">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <rect x="34" y="70" width="74" height="64" rx="6" fill="#dbeafe" stroke="#2563eb"/>
          <text x="48" y="106" font-size="13">image</text>
          <line x1="116" y1="102" x2="178" y2="102" stroke="#647085" marker-end="url(#embArrow)"/>
          <defs><marker id="embArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#647085"/></marker></defs>
          <rect x="190" y="57" width="132" height="92" rx="6" fill="#eef2f7" stroke="#94a3b8"/>
          <text x="205" y="82" font-size="12">[0.12, -0.44,</text>
          <text x="205" y="104" font-size="12"> 0.88, 0.03,</text>
          <text x="205" y="126" font-size="12"> ...]</text>
        </svg>
        <h3>11. Embeddings</h3>
        <p>An embedding turns an image or object crop into a vector of numbers. Similar images should have similar vectors. This is useful for stronger identity tracking later.</p>
        <div class="formula">image crop -> vector -> compare similarity</div>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 210" role="img" aria-label="Object tracking over time">
          <rect width="360" height="210" fill="#fbfcfe"/>
          <g fill="#eef2f7" stroke="#cbd5e1">
            <rect x="28" y="44" width="84" height="112"/>
            <rect x="132" y="44" width="84" height="112"/>
            <rect x="236" y="44" width="84" height="112"/>
          </g>
          <g fill="none" stroke="#22c55e" stroke-width="3">
            <rect x="50" y="82" width="28" height="42"/>
            <rect x="160" y="86" width="28" height="42"/>
            <rect x="270" y="92" width="28" height="42"/>
          </g>
          <path d="M78 103 C112 98, 128 103, 160 107" stroke="#2563eb" fill="none" stroke-width="3"/>
          <path d="M188 107 C220 108, 242 112, 270 113" stroke="#2563eb" fill="none" stroke-width="3"/>
          <text x="43" y="174" font-size="12">frame 1</text>
          <text x="147" y="174" font-size="12">frame 2</text>
          <text x="251" y="174" font-size="12">frame 3</text>
          <text x="122" y="30" font-size="13" fill="#172033">same object gets one track ID</text>
        </svg>
        <h3>12. Tracking Objects Over Time</h3>
        <p>Tracking connects detections across frames. This project uses label matching, box overlap, center distance, and frame gap to create IDs like cup_001.</p>
        <div class="formula">detections over time -> track_id</div>
      </article>

      <article class="lesson-card wide">
        <h3>13. How It All Connects In Our Project</h3>
        <p>The project is built as a chain. Each stage creates evidence for the next one.</p>
        <div class="formula">VideoSource -> ObservationRecord -> DetectionRecord -> TrackRecord -> TrackSummary -> Query/Compare/Report</div>
        <ul>
          <li><strong>sources.py</strong> reads webcam or video frames.</li>
          <li><strong>storage.py</strong> saves frames and timestamps.</li>
          <li><strong>detection.py</strong> runs YOLO and creates object boxes.</li>
          <li><strong>tracking.py</strong> connects boxes over time into object IDs.</li>
          <li><strong>query.py</strong> answers what was last seen.</li>
          <li><strong>change.py</strong> compares before/after runs.</li>
          <li><strong>report.py and web.py</strong> turn memory into something humans can inspect.</li>
        </ul>
      </article>
    </section>
    """
    return page("Learn CV Basics", body)


def safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in Path(name).name)
    return cleaned or "uploaded_video.mp4"


def scan_video_file(video_path: str, run_name: str) -> None:
    run_dir = DEFAULT_RUNS_DIR / run_name
    if run_dir.exists() and any(run_dir.iterdir()):
        return

    source = VideoFileSource(video_path=video_path, frame_stride=5, resize_width=1280)
    source.open()
    try:
        with RunWriter(run_dir=run_dir, source="video") as writer:
            while True:
                packet = source.next()
                if packet is None:
                    break
                writer.write_frame(packet.frame_id, packet.timestamp, packet.frame_bgr, packet.metadata)
    finally:
        source.close()
    run_detection_for_dir(run_dir, model="yolov8n.pt", confidence=0.35, frame_stride=1, annotate=True)
    run_tracking_for_dir(run_dir, iou_threshold=0.25, max_center_distance=180.0, max_frame_gap=10)


@app.post("/upload-video")
def upload_video(video_file: UploadFile = File(...), run_name: str = Form(...)) -> RedirectResponse:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(video_file.filename or "uploaded_video.mp4")
    saved_path = UPLOADS_DIR / filename
    with saved_path.open("wb") as output:
        shutil.copyfileobj(video_file.file, output)

    scan_video_file(str(saved_path), run_name)
    return RedirectResponse(f"/runs-view/{run_name}", status_code=303)


@app.post("/scan-video")
def scan_video(video_path: str = Form(...), run_name: str = Form(...)) -> RedirectResponse:
    scan_video_file(video_path, run_name)
    return RedirectResponse(f"/runs-view/{run_name}", status_code=303)


@app.get("/runs-view/{run_name}", response_class=HTMLResponse)
def run_view(run_name: str, q: str | None = None) -> HTMLResponse:
    run_dir = RUNS_DIR / run_name
    summaries = load_track_summaries(run_name)
    report_path = run_dir / "report.html"
    if summaries and not report_path.exists():
        build_run_report(run_dir, summaries, report_path)

    answer_html = ""
    if q:
        result = find_best_track(run_dir, q, summaries)
        answer_html = f'<div class="answer"><strong>Query:</strong> {q}<br>{result.answer}</div>'

    cards = []
    for track in summaries:
        evidence = f"/runs/{run_name}/annotated_frames/{Path(track.last_rgb_path).name}"
        raw_evidence = f"/runs/{run_name}/{track.last_rgb_path.replace(chr(92), '/')}"
        cards.append(
            f"""
            <article class="card memory-card">
              <img src="{evidence}" onerror="this.src='{raw_evidence}'" alt="{track.track_id}">
              <h3>{track.track_id}</h3>
              <p><strong>Label:</strong> {track.label}</p>
              <p><strong>Last seen:</strong> {track.last_seen_timestamp:.2f}s, frame {track.last_seen_frame}</p>
              <p><strong>Detections:</strong> {track.detection_count}</p>
              <p><strong>Best confidence:</strong> {track.best_confidence:.2f}</p>
            </article>
            """
        )
    cards_html = "\n".join(cards) if cards else '<p class="muted">No tracked memory for this run yet.</p>'
    body = f"""
    <div class="grid">
      <aside class="panel stack">
        <h2>Runs</h2>
        <div class="run-list">{run_list_html(run_name)}</div>
      </aside>
      <section class="stack">
        <div class="panel stack">
          <h2>{run_name}</h2>
          <form class="stack" action="/runs-view/{run_name}" method="get">
            <div>
              <label for="q">Ask what it last saw</label>
              <input id="q" name="q" placeholder="bottle, cup, chair" value="{q or ''}">
            </div>
            <div class="actions">
              <button type="submit">Query Memory</button>
              <a class="button secondary" href="/runs/{run_name}/report.html" target="_blank">Open HTML Report</a>
              <a class="button secondary" href="/runs/{run_name}/track_summary.json" target="_blank">Track JSON</a>
            </div>
          </form>
          {answer_html}
        </div>
        <div class="memory-grid">{cards_html}</div>
      </section>
    </div>
    """
    return page(f"{run_name} - Visual Memory", body)
