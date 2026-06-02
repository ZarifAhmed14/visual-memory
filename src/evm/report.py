from __future__ import annotations

from html import escape
from pathlib import Path

from evm.tracking import TrackSummary


def relative_path(from_path: Path, target: Path) -> str:
    return target.resolve().relative_to(from_path.resolve().parent).as_posix()


def build_run_report(run_dir: Path, tracks: list[TrackSummary], output_path: Path) -> None:
    rows = []
    for track in tracks:
        evidence_path = run_dir / track.last_rgb_path
        evidence_rel = relative_path(output_path, evidence_path)
        annotated_path = run_dir / "annotated_frames" / Path(track.last_rgb_path).name
        annotated_rel = relative_path(output_path, annotated_path) if annotated_path.exists() else evidence_rel
        rows.append(
            f"""
            <article class="memory-card">
              <img src="{escape(annotated_rel)}" alt="{escape(track.track_id)} evidence">
              <div>
                <h2>{escape(track.track_id)}</h2>
                <p><strong>Label:</strong> {escape(track.label)}</p>
                <p><strong>Last seen:</strong> {track.last_seen_timestamp:.2f}s, frame {track.last_seen_frame}</p>
                <p><strong>Detections:</strong> {track.detection_count}</p>
                <p><strong>Best confidence:</strong> {track.best_confidence:.2f}</p>
                <p><strong>Last center:</strong> ({track.last_center_xy[0]:.1f}, {track.last_center_xy[1]:.1f})</p>
              </div>
            </article>
            """
        )

    cards = "\n".join(rows) if rows else '<p class="empty">No tracked objects found.</p>'
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visual Memory Report</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      color: #172033;
      background: #f6f7f9;
    }}
    header {{
      padding: 28px 32px 18px;
      background: #ffffff;
      border-bottom: 1px solid #d8dee8;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 28px;
    }}
    .meta {{
      color: #596579;
      margin: 0;
    }}
    main {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px;
    }}
    .memory-card {{
      display: grid;
      grid-template-columns: minmax(260px, 420px) 1fr;
      gap: 18px;
      align-items: start;
      padding: 16px;
      margin-bottom: 16px;
      background: #ffffff;
      border: 1px solid #d8dee8;
      border-radius: 8px;
    }}
    .memory-card img {{
      width: 100%;
      border-radius: 6px;
      border: 1px solid #d8dee8;
      background: #eef1f5;
    }}
    .memory-card h2 {{
      margin: 0 0 10px;
      font-size: 20px;
    }}
    .memory-card p {{
      margin: 6px 0;
      line-height: 1.35;
    }}
    .empty {{
      padding: 16px;
      background: #fff;
      border: 1px solid #d8dee8;
      border-radius: 8px;
    }}
    @media (max-width: 760px) {{
      .memory-card {{
        grid-template-columns: 1fr;
      }}
      header {{
        padding: 22px 20px 14px;
      }}
      main {{
        padding: 16px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Visual Memory Report</h1>
    <p class="meta">Run: {escape(str(run_dir))} · Tracks: {len(tracks)}</p>
  </header>
  <main>
    {cards}
  </main>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
