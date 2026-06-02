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
      <a href="/math">Math Playground</a>
      <a href="/architecture">Architecture</a>
      <a href="/evaluation">Evaluation</a>
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


@app.get("/math", response_class=HTMLResponse)
def math_playground() -> HTMLResponse:
    body = """
    <section class="panel stack" style="margin-bottom: 18px;">
      <h2>Math Playground For Visual Memory</h2>
      <p class="muted">
        This page explains the math used by the project in a playful way. The goal is not to memorize formulas;
        the goal is to understand what each formula lets the bot do.
      </p>
    </section>

    <section class="lesson-grid">
      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Video timestamp timeline">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <line x1="36" y1="112" x2="324" y2="112" stroke="#172033" stroke-width="3"/>
          <g fill="#2563eb">
            <circle cx="56" cy="112" r="7"/><circle cx="104" cy="112" r="7"/><circle cx="152" cy="112" r="7"/>
            <circle cx="200" cy="112" r="7"/><circle cx="248" cy="112" r="7"/><circle cx="296" cy="112" r="7"/>
          </g>
          <g font-size="12" fill="#172033">
            <text x="46" y="142">0</text><text x="94" y="142">5</text><text x="139" y="142">10</text>
            <text x="187" y="142">15</text><text x="235" y="142">20</text><text x="283" y="142">25</text>
          </g>
          <text x="60" y="58" font-size="14" fill="#172033">frame index</text>
          <text x="60" y="78" font-size="13" fill="#647085">divide by FPS to get seconds</text>
          <path d="M152 100 C164 74, 190 74, 200 100" fill="none" stroke="#ef4444" stroke-width="3"/>
          <text x="174" y="70" font-size="12" fill="#ef4444">time jump</text>
        </svg>
        <h3>1. Timestamp Math: Giving Frames A Clock</h3>
        <p>A video is a stack of frames. To make memory useful, every frame needs a time. If a video has 30 frames per second, frame 60 happened around 2 seconds in.</p>
        <div class="formula">timestamp = source_frame_index / FPS</div>
        <p>In the project, this lets the bot say: “I last saw the bottle at 14.41 seconds.” Without this math, it could only say “somewhere in the video.”</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="RGB pixel values">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <rect x="42" y="50" width="96" height="96" fill="rgb(55,126,230)" stroke="#172033"/>
          <g transform="translate(180 46)">
            <rect width="130" height="24" fill="#ef4444"/><rect y="42" width="82" height="24" fill="#22c55e"/><rect y="84" width="220" height="24" fill="#3b82f6"/>
            <text x="0" y="39" font-size="12" fill="#172033">R = 55</text>
            <text x="0" y="81" font-size="12" fill="#172033">G = 126</text>
            <text x="0" y="123" font-size="12" fill="#172033">B = 230</text>
          </g>
          <text x="42" y="174" font-size="13" fill="#172033">one pixel is three numbers</text>
        </svg>
        <h3>2. RGB Math: Color As Numbers</h3>
        <p>A pixel is not “blue” to the computer. It is numbers. In RGB, each pixel has red, green, and blue values. Bigger blue value means the pixel looks more blue.</p>
        <div class="formula">pixel = [R, G, B]</div>
        <p>The detector sees millions of these numbers and learns patterns from them. Color math is the first tiny brick in the whole vision tower.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Resize scale">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <rect x="36" y="45" width="145" height="110" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
          <rect x="235" y="72" width="82" height="62" fill="#dcfce7" stroke="#16a34a" stroke-width="2"/>
          <line x1="190" y1="100" x2="226" y2="100" stroke="#647085" marker-end="url(#scaleArrow)"/>
          <defs><marker id="scaleArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#647085"/></marker></defs>
          <text x="58" y="176" font-size="12" fill="#172033">large phone frame</text>
          <text x="230" y="156" font-size="12" fill="#172033">smaller frame</text>
          <text x="76" y="30" font-size="12" fill="#647085">keeps same shape ratio</text>
        </svg>
        <h3>3. Resize Math: Making Videos Manageable</h3>
        <p>Phone videos can be huge. Resizing makes processing faster while keeping the image shape. If width shrinks by 50%, height must also shrink by 50% so objects do not stretch.</p>
        <div class="formula">scale = target_width / original_width<br>new_height = original_height × scale</div>
        <p>This is used in video scanning so your laptop does not struggle with very large frames.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Camera projection math">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <circle cx="48" cy="114" r="10" fill="#ef4444"/>
          <rect x="166" y="52" width="6" height="128" fill="#172033"/>
          <circle cx="285" cy="80" r="14" fill="#22c55e"/>
          <line x1="48" y1="114" x2="285" y2="80" stroke="#647085" stroke-dasharray="5 5"/>
          <circle cx="169" cy="96" r="5" fill="#22c55e"/>
          <text x="26" y="144" font-size="12" fill="#172033">camera</text>
          <text x="188" y="48" font-size="12" fill="#172033">image plane</text>
          <text x="252" y="112" font-size="12" fill="#172033">3D point</text>
          <text x="188" y="100" font-size="12" fill="#16a34a">(u,v)</text>
        </svg>
        <h3>4. Projection Math: 3D World To 2D Pixel</h3>
        <p>A 3D object point gets squeezed onto a 2D image. The farther an object is, the smaller it looks. This is why one 2D image cannot perfectly reveal true 3D depth.</p>
        <div class="formula">u = fx × X/Z + cx<br>v = fy × Y/Z + cy</div>
        <p>Our current app mostly avoids this because normal video has no reliable depth. But this formula is the bridge to future 3D memory.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Bounding box geometry">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <rect x="86" y="54" width="146" height="108" fill="none" stroke="#22c55e" stroke-width="4"/>
          <circle cx="159" cy="108" r="6" fill="#ef4444"/>
          <line x1="86" y1="42" x2="232" y2="42" stroke="#2563eb" stroke-width="3"/>
          <line x1="246" y1="54" x2="246" y2="162" stroke="#2563eb" stroke-width="3"/>
          <text x="137" y="34" font-size="12" fill="#2563eb">width</text>
          <text x="252" y="112" font-size="12" fill="#2563eb">height</text>
          <text x="168" y="106" font-size="12" fill="#ef4444">center</text>
          <text x="74" y="184" font-size="12" fill="#172033">box = top-left and bottom-right pixels</text>
        </svg>
        <h3>5. Bounding Box Math: Where Is The Object?</h3>
        <p>YOLO gives a rectangle around each object. From that rectangle, we calculate width, height, center, and area.</p>
        <div class="formula">width = x2 - x1<br>height = y2 - y1<br>center = (x1 + width/2, y1 + height/2)<br>area = width × height</div>
        <p>The project stores these values in each detection record. Tracking and movement detection both depend on them.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Confidence threshold">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <line x1="42" y1="154" x2="318" y2="154" stroke="#172033" stroke-width="2"/>
          <line x1="122" y1="58" x2="122" y2="154" stroke="#ef4444" stroke-dasharray="5 5" stroke-width="3"/>
          <rect x="64" y="116" width="35" height="38" fill="#fca5a5"/>
          <rect x="145" y="86" width="35" height="68" fill="#86efac"/>
          <rect x="226" y="45" width="35" height="109" fill="#86efac"/>
          <text x="91" y="174" font-size="12">0.28</text>
          <text x="146" y="174" font-size="12">0.55</text>
          <text x="227" y="174" font-size="12">0.83</text>
          <text x="92" y="50" font-size="12" fill="#ef4444">threshold 0.35</text>
        </svg>
        <h3>6. Confidence Math: Trust But Verify</h3>
        <p>Confidence is the detector’s belief score. A threshold filters weak guesses. In this project, the default threshold is 0.35.</p>
        <div class="formula">keep detection if confidence ≥ threshold</div>
        <p>A 0.83 detection is more trustworthy than 0.36, but not guaranteed. The report image is the final reality check.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Intersection over Union">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <rect x="86" y="62" width="120" height="90" fill="#3b82f6" fill-opacity=".35" stroke="#2563eb" stroke-width="3"/>
          <rect x="148" y="92" width="120" height="90" fill="#22c55e" fill-opacity=".35" stroke="#16a34a" stroke-width="3"/>
          <rect x="148" y="92" width="58" height="60" fill="#f59e0b" fill-opacity=".65"/>
          <text x="120" y="48" font-size="12" fill="#2563eb">box A</text>
          <text x="222" y="198" font-size="12" fill="#16a34a">box B</text>
          <text x="153" y="126" font-size="12" fill="#7a4b00">overlap</text>
        </svg>
        <h3>7. IoU Math: Are These Boxes The Same Object?</h3>
        <p>IoU means Intersection over Union. It compares two boxes. High IoU means they overlap a lot, so they may be the same object in nearby frames.</p>
        <div class="formula">IoU = overlap_area / union_area</div>
        <p>The tracker uses IoU to connect a new detection to an existing track like <strong>cup_001</strong>.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Center distance">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <circle cx="112" cy="118" r="8" fill="#2563eb"/>
          <circle cx="246" cy="82" r="8" fill="#ef4444"/>
          <line x1="112" y1="118" x2="246" y2="82" stroke="#172033" stroke-width="3"/>
          <line x1="112" y1="118" x2="246" y2="118" stroke="#94a3b8" stroke-dasharray="4 4"/>
          <line x1="246" y1="118" x2="246" y2="82" stroke="#94a3b8" stroke-dasharray="4 4"/>
          <text x="166" y="134" font-size="12" fill="#647085">dx</text>
          <text x="253" y="104" font-size="12" fill="#647085">dy</text>
          <text x="139" y="84" font-size="12" fill="#172033">distance</text>
        </svg>
        <h3>8. Distance Math: How Far Did It Move?</h3>
        <p>If a box does not overlap much, the object may still be the same one if its center only moved a little. This uses the Pythagorean theorem.</p>
        <div class="formula">distance = sqrt((x2 - x1)^2 + (y2 - y1)^2)</div>
        <p>The project uses this in tracking and in moved-object detection between runs.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Tracking score">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <rect x="45" y="54" width="270" height="32" rx="6" fill="#dbeafe" stroke="#2563eb"/>
          <rect x="45" y="112" width="190" height="32" rx="6" fill="#dcfce7" stroke="#16a34a"/>
          <rect x="45" y="170" width="230" height="32" rx="6" fill="#fef3c7" stroke="#f59e0b"/>
          <text x="55" y="75" font-size="13">IoU overlap score</text>
          <text x="55" y="133" font-size="13">distance bonus</text>
          <text x="55" y="191" font-size="13">association score</text>
        </svg>
        <h3>9. Tracking Score: Picking The Best Match</h3>
        <p>When a new cup appears, the tracker compares it with active cup tracks. It picks the track with the best score.</p>
        <div class="formula">score = IoU + 0.25 × max(0, 1 - distance / max_distance)</div>
        <p>Translation: overlap matters most, but nearby movement helps. This is a small “common sense” rule written as math.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Average memory">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <circle cx="94" cy="132" r="7" fill="#2563eb"/>
          <circle cx="132" cy="102" r="7" fill="#2563eb"/>
          <circle cx="182" cy="116" r="7" fill="#2563eb"/>
          <circle cx="230" cy="84" r="7" fill="#2563eb"/>
          <circle cx="160" cy="109" r="11" fill="#ef4444"/>
          <text x="174" y="106" font-size="12" fill="#ef4444">average</text>
          <path d="M94 132 L132 102 L182 116 L230 84" stroke="#94a3b8" fill="none" stroke-dasharray="4 4"/>
          <text x="70" y="178" font-size="12" fill="#172033">many sightings become one memory summary</text>
        </svg>
        <h3>10. Memory Summary Math: Compressing Many Sightings</h3>
        <p>A track may have many detections. The summary stores useful statistics: first seen, last seen, average center, average area, and best confidence.</p>
        <div class="formula">average_center_x = sum(center_x values) / count</div>
        <p>This is how many frame-level sightings become one readable memory card.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Set difference">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <circle cx="142" cy="110" r="66" fill="#3b82f6" fill-opacity=".28" stroke="#2563eb" stroke-width="3"/>
          <circle cx="218" cy="110" r="66" fill="#22c55e" fill-opacity=".28" stroke="#16a34a" stroke-width="3"/>
          <text x="92" y="42" font-size="13" fill="#2563eb">before</text>
          <text x="238" y="42" font-size="13" fill="#16a34a">after</text>
          <text x="86" y="112" font-size="12">gone</text>
          <text x="164" y="112" font-size="12">same</text>
          <text x="244" y="112" font-size="12">new</text>
        </svg>
        <h3>11. Change Math: What Appeared Or Disappeared?</h3>
        <p>Before/after comparison uses set math. Think of each scan as a bag of labels. The overlap is what stayed. The left-only part disappeared. The right-only part appeared.</p>
        <div class="formula">appeared = after - before<br>disappeared = before - after<br>persisted = before ∩ after</div>
        <p>This powers the compare-runs feature.</p>
      </article>

      <article class="lesson-card">
        <svg class="diagram" viewBox="0 0 360 220" role="img" aria-label="Fuzzy label match">
          <rect width="360" height="220" fill="#fbfcfe"/>
          <rect x="52" y="54" width="100" height="44" rx="8" fill="#dbeafe" stroke="#2563eb"/>
          <rect x="208" y="54" width="100" height="44" rx="8" fill="#dcfce7" stroke="#16a34a"/>
          <text x="86" y="82" font-size="14">phone</text>
          <text x="226" y="82" font-size="14">cell phone</text>
          <line x1="152" y1="76" x2="208" y2="76" stroke="#647085" stroke-width="3"/>
          <rect x="76" y="140" width="208" height="28" rx="6" fill="#fef3c7" stroke="#f59e0b"/>
          <text x="108" y="159" font-size="13">similar enough to match</text>
        </svg>
        <h3>12. Query Matching Math: Understanding Similar Words</h3>
        <p>The detector may say “cell phone,” while a user types “phone.” The query system normalizes aliases and uses a similarity score for fallback matches.</p>
        <div class="formula">match if similarity(query, label) ≥ 0.55</div>
        <p>This makes simple memory questions more forgiving without needing a full chatbot yet.</p>
      </article>

      <article class="lesson-card wide">
        <h3>13. The Whole Math Story</h3>
        <p>Every formula has a job. None of the math is decoration.</p>
        <div class="formula">time tells when -> boxes tell where -> confidence tells trust -> IoU/distance tells identity -> averages summarize memory -> sets detect change</div>
        <p>That chain is the reason the project can go from a raw phone video to a sentence like: “I last saw bottle_001 at 14.41 seconds, and here is the evidence image.”</p>
      </article>
    </section>
    """
    return page("Math Playground", body)


@app.get("/architecture", response_class=HTMLResponse)
def architecture() -> HTMLResponse:
    body = """
    <section class="panel stack" style="margin-bottom: 18px;">
      <h2>Project Architecture</h2>
      <p class="muted">
        This page explains how the visual-memory bot is assembled: what enters the system,
        which module handles it, what files are produced, and how the frontend displays the result.
      </p>
    </section>

    <section class="lesson-grid">
      <article class="lesson-card wide">
        <svg class="diagram" viewBox="0 0 920 230" role="img" aria-label="System architecture pipeline">
          <rect width="920" height="230" fill="#fbfcfe"/>
          <defs>
            <marker id="archArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#647085"/></marker>
          </defs>
          <g font-family="Arial" font-size="13">
            <g transform="translate(25 70)">
              <rect width="105" height="70" rx="8" fill="#dbeafe" stroke="#2563eb"/><text x="18" y="30">Webcam</text><text x="18" y="50">or video</text>
            </g>
            <g transform="translate(165 70)">
              <rect width="115" height="70" rx="8" fill="#eef2f7" stroke="#94a3b8"/><text x="18" y="30">sources.py</text><text x="15" y="50">FramePacket</text>
            </g>
            <g transform="translate(315 70)">
              <rect width="120" height="70" rx="8" fill="#eef2f7" stroke="#94a3b8"/><text x="18" y="30">storage.py</text><text x="15" y="50">run folder</text>
            </g>
            <g transform="translate(470 70)">
              <rect width="125" height="70" rx="8" fill="#dcfce7" stroke="#16a34a"/><text x="18" y="30">detection.py</text><text x="14" y="50">YOLO boxes</text>
            </g>
            <g transform="translate(630 70)">
              <rect width="120" height="70" rx="8" fill="#fef3c7" stroke="#f59e0b"/><text x="18" y="30">tracking.py</text><text x="14" y="50">track IDs</text>
            </g>
            <g transform="translate(785 70)">
              <rect width="110" height="70" rx="8" fill="#fae8ff" stroke="#a855f7"/><text x="18" y="30">web.py</text><text x="14" y="50">dashboard</text>
            </g>
          </g>
          <g stroke="#647085" stroke-width="3" marker-end="url(#archArrow)">
            <line x1="130" y1="105" x2="165" y2="105"/><line x1="280" y1="105" x2="315" y2="105"/>
            <line x1="435" y1="105" x2="470" y2="105"/><line x1="595" y1="105" x2="630" y2="105"/>
            <line x1="750" y1="105" x2="785" y2="105"/>
          </g>
          <text x="30" y="185" font-size="14" fill="#172033">The project is a chain: each step writes useful evidence for the next step.</text>
        </svg>
        <h3>1. The Big Architecture Idea</h3>
        <p>The app is intentionally built as a pipeline. It does not hide everything inside one giant script. Each stage produces files that can be inspected, reused, and explained.</p>
        <div class="formula">input -> observations -> detections -> tracks -> memory -> report/frontend</div>
      </article>

      <article class="lesson-card">
        <h3>2. Input Layer</h3>
        <p><strong>sources.py</strong> turns live webcam frames or video-file frames into a common object called a frame packet.</p>
        <ul>
          <li>WebcamSource reads laptop camera frames.</li>
          <li>VideoFileSource reads phone-recorded videos.</li>
          <li>Each frame gets an ID, timestamp, image data, and metadata.</li>
        </ul>
        <div class="formula">camera/video -> FramePacket</div>
      </article>

      <article class="lesson-card">
        <h3>3. Storage Layer</h3>
        <p><strong>storage.py</strong> creates a run folder. A run is one scan session.</p>
        <ul>
          <li>frames/ stores saved images.</li>
          <li>observations.jsonl stores frame metadata.</li>
          <li>manifest.json stores run summary.</li>
        </ul>
        <div class="formula">FramePacket -> frames + observations.jsonl</div>
      </article>

      <article class="lesson-card">
        <h3>4. Detection Layer</h3>
        <p><strong>detection.py</strong> runs YOLO. It asks: “What objects are in this frame, and where are they?”</p>
        <ul>
          <li>Produces labels.</li>
          <li>Produces confidence scores.</li>
          <li>Produces bounding boxes.</li>
          <li>Creates annotated frames for visual proof.</li>
        </ul>
        <div class="formula">frame -> DetectionRecord</div>
      </article>

      <article class="lesson-card">
        <h3>5. Tracking Layer</h3>
        <p><strong>tracking.py</strong> connects repeated detections over time. It asks: “Is this cup probably the same cup from the previous frames?”</p>
        <ul>
          <li>Uses label matching.</li>
          <li>Uses IoU overlap.</li>
          <li>Uses center-distance movement.</li>
          <li>Creates IDs like cup_001.</li>
        </ul>
        <div class="formula">DetectionRecord list -> TrackRecord list</div>
      </article>

      <article class="lesson-card">
        <h3>6. Memory And Query Layer</h3>
        <p><strong>memory.py</strong> summarizes what was seen. <strong>query.py</strong> lets users ask about it.</p>
        <ul>
          <li>first seen</li>
          <li>last seen</li>
          <li>detection count</li>
          <li>best confidence</li>
          <li>supporting evidence frame</li>
        </ul>
        <div class="formula">tracks -> answer: “last saw bottle at 14.41s”</div>
      </article>

      <article class="lesson-card">
        <h3>7. Compare And Report Layer</h3>
        <p><strong>change.py</strong> compares two runs. <strong>report.py</strong> creates the visual HTML report.</p>
        <ul>
          <li>appeared objects</li>
          <li>disappeared objects</li>
          <li>still-present objects</li>
          <li>moved objects</li>
          <li>memory cards with images</li>
        </ul>
        <div class="formula">before + after -> change_report.json</div>
      </article>

      <article class="lesson-card">
        <h3>8. Frontend Layer</h3>
        <p><strong>web.py</strong> is the localhost web app. It is the presentation and interaction layer.</p>
        <ul>
          <li>Upload and scan a video.</li>
          <li>Open webcam and record 3-5 seconds.</li>
          <li>Show saved runs.</li>
          <li>Show memory cards.</li>
          <li>Query visual memory.</li>
          <li>Teach basics and math through tabs.</li>
        </ul>
        <div class="formula">backend files -> human-friendly dashboard</div>
      </article>

      <article class="lesson-card wide">
        <h3>9. Output Files And What They Mean</h3>
        <div class="formula">frames = visual evidence<br>observations.jsonl = frame timeline<br>detections.jsonl = object guesses<br>tracks.jsonl = object identity over time<br>track_summary.json = readable memory<br>report.html = visual result page</div>
        <p>If the group understands these files, they understand the whole project. The frontend is just a friendly way to view and trigger these pipeline outputs.</p>
      </article>
    </section>
    """
    return page("Architecture", body)


@app.get("/evaluation", response_class=HTMLResponse)
def evaluation() -> HTMLResponse:
    body = """
    <section class="panel stack" style="margin-bottom: 18px;">
      <h2>Evaluation: How To Know If The AI Actually Saw Correctly</h2>
      <p class="muted">
        Computer vision systems can sound confident and still be wrong. This page teaches how to inspect the evidence,
        judge detections, and explain limitations honestly.
      </p>
    </section>

    <section class="lesson-grid">
      <article class="lesson-card wide">
        <svg class="diagram" viewBox="0 0 920 230" role="img" aria-label="Evaluation ladder">
          <rect width="920" height="230" fill="#fbfcfe"/>
          <g font-family="Arial" font-size="14">
            <rect x="40" y="70" width="150" height="70" rx="8" fill="#dcfce7" stroke="#16a34a"/>
            <text x="65" y="100">Label correct</text><text x="65" y="122">Box correct</text>
            <rect x="230" y="70" width="150" height="70" rx="8" fill="#fef3c7" stroke="#f59e0b"/>
            <text x="250" y="100">Label wrong</text><text x="250" y="122">Box useful</text>
            <rect x="420" y="70" width="150" height="70" rx="8" fill="#fee2e2" stroke="#ef4444"/>
            <text x="448" y="100">False object</text><text x="448" y="122">Bad box</text>
            <rect x="610" y="70" width="150" height="70" rx="8" fill="#e0e7ff" stroke="#6366f1"/>
            <text x="632" y="100">Missed object</text><text x="632" y="122">No box</text>
          </g>
          <text x="40" y="184" font-size="14" fill="#172033">Evaluation means looking at the image evidence, not trusting the label blindly.</text>
        </svg>
        <h3>1. The Golden Rule</h3>
        <p>Never judge the system only from text output. Always check the evidence image. A detection is good only when the label and the box make sense together.</p>
      </article>

      <article class="lesson-card">
        <h3>2. Good Detection</h3>
        <p>A good detection has:</p>
        <ul>
          <li>correct label</li>
          <li>box tightly around the object</li>
          <li>reasonable confidence</li>
          <li>repeated detections across frames</li>
        </ul>
        <div class="formula">good = correct label + correct box + repeated evidence</div>
      </article>

      <article class="lesson-card">
        <h3>3. Wrong Label But Useful Box</h3>
        <p>Sometimes the box points to a real object, but the label is wrong. Example: a bowl might be called vase. This is still useful for debugging because the model found “something,” but guessed the category wrong.</p>
        <div class="formula">box good, label bad -> detector classification error</div>
      </article>

      <article class="lesson-card">
        <h3>4. False Positive</h3>
        <p>A false positive is when the model sees an object that is not really there. These often happen with clutter, reflections, partial objects, or unusual camera angles.</p>
        <div class="formula">model says object exists, but evidence image says no</div>
      </article>

      <article class="lesson-card">
        <h3>5. Missed Object</h3>
        <p>A missed object is when a real object is visible, but the model does not detect it. This can happen if the object is small, blurry, partly hidden, or outside YOLO's known classes.</p>
        <div class="formula">object exists, but no detection record appears</div>
      </article>

      <article class="lesson-card">
        <h3>6. Confidence Is Not Truth</h3>
        <p>Confidence is useful, but it is not a promise. A high-confidence wrong answer can still happen. A low-confidence correct answer can also happen.</p>
        <ul>
          <li>0.70+ is usually stronger.</li>
          <li>0.35-0.50 needs careful inspection.</li>
          <li>one detection is weaker than many detections.</li>
        </ul>
        <div class="formula">confidence = model belief, not reality</div>
      </article>

      <article class="lesson-card">
        <h3>7. Track Quality</h3>
        <p>A good track follows the same object over time. A bad track may split one object into multiple IDs or merge multiple objects into one ID.</p>
        <ul>
          <li>Many consistent detections = stronger track.</li>
          <li>Duplicate boxes can create duplicate tracks.</li>
          <li>Fast camera movement can break tracks.</li>
        </ul>
        <div class="formula">good track = stable label + stable motion + repeated frames</div>
      </article>

      <article class="lesson-card">
        <h3>8. Mobile Video Quality Checklist</h3>
        <ul>
          <li>Move slowly.</li>
          <li>Keep the camera steady.</li>
          <li>Use good lighting.</li>
          <li>Show objects clearly for at least 2-3 seconds.</li>
          <li>Avoid fast pans and motion blur.</li>
          <li>Keep important objects large enough in the frame.</li>
        </ul>
        <div class="formula">better video -> better detections -> better memory</div>
      </article>

      <article class="lesson-card">
        <h3>9. How To Evaluate A Run</h3>
        <ol>
          <li>Open the run page.</li>
          <li>Check memory cards with many detections first.</li>
          <li>Open the evidence images.</li>
          <li>Mark labels as correct, wrong, or uncertain.</li>
          <li>Look for duplicate tracks.</li>
          <li>Query one or two known objects.</li>
          <li>Explain at least one success and one failure.</li>
        </ol>
      </article>

      <article class="lesson-card">
        <h3>10. What To Say In A Presentation</h3>
        <p>Good explanation sounds like this:</p>
        <div class="formula">“The model believes it saw a cup 22 times. The best confidence is 0.71. The evidence image shows the box is correct, so this is a reliable memory.”</div>
        <p>That is much stronger than saying, “The AI saw a cup.”</p>
      </article>

      <article class="lesson-card wide">
        <h3>11. Evaluation Scorecard</h3>
        <div class="formula">A = label and box correct, repeated often<br>B = label correct but box loose, or few detections<br>C = real object but wrong label<br>D = false positive or useless track<br>Missing = real object not detected</div>
        <p>Use this simple scorecard when reviewing demo runs with your group. It makes the project feel serious because you are showing how engineers evaluate AI, not just how they run it.</p>
      </article>
    </section>
    """
    return page("Evaluation", body)


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
