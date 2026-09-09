"""Encode the pitch and teaser from real browser footage; no application data is changed.

Dependencies: Pillow and imageio-ffmpeg (or FFMPEG_EXE).
Run from the repository root: python scripts/video/render.py
"""
import json
import math
import os
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video-artifacts"
FFMPEG = os.environ.get("FFMPEG_EXE") or imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30
INK = "#102e32"
GREEN = "#c8eea0"
FONT_DIR = Path(os.environ.get("VIDEO_FONT_DIR", "C:/Windows/Fonts"))


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ("segoeuib.ttf" if bold else "segoeui.ttf")), size)


def wrap(draw, text, face, width):
    lines, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=face) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + [current]


def card(kind):
    path = OUT / "graphics" / f"{kind}.png"
    im = Image.new("RGB", (1920, 1080), INK)
    d = ImageDraw.Draw(im)
    for radius in (250, 390, 540, 690, 840):
        d.ellipse((1780-radius, 1050-radius, 1780+radius, 1050+radius), outline="#23494b", width=2)
    for i, width in enumerate((74, 59, 44)):
        d.rounded_rectangle((138, 95+i*16, 138+width, 101+i*16), radius=2, fill=GREEN)
    d.text((240, 88), "MARITIME CARBON", font=font(40, True), fill="white")
    if kind == "intro":
        d.text((140, 244), "A FLEET DECISION, MADE VISIBLE", font=font(23, True), fill=GREEN)
        d.multiline_text((132, 316), "Which fuel.\nWhich voyage leg.\nAt what cost?", font=font(100, True), fill="white", spacing=7)
        d.text((140, 750), "FuelEU Maritime + EU ETS", font=font(38), fill="#c1d8d2")
        d.text((140, 815), "Two fictional vessels. A real app walkthrough.", font=font(30), fill="#c1d8d2")
    else:
        d.text((140, 288), "FROM INPUTS TO ACTION", font=font(24, True), fill=GREEN)
        d.multiline_text((134, 362), "A traceable decision\nfor your fleet.", font=font(92, True), fill="white", spacing=18)
        d.rounded_rectangle((140, 657, 833, 755), radius=10, fill=GREEN)
        d.text((179, 675), "Let’s talk about your fleet.", font=font(38, True), fill=INK)
        d.text((140, 812), "Maritime Carbon · FuelEU + EU ETS planning", font=font(29), fill="#c1d8d2")
    d.text((140, 980), "Illustrative case · Planning assumptions · Lowest evaluated option, not a guaranteed global minimum",
           font=font(22), fill="#a8c3bc")
    im.save(path)
    return path


def overlay(index, caption):
    path = OUT / "graphics" / f"caption-{index:02d}.png"
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 960, 1920, 1080), fill=INK)
    d.rectangle((0, 960, 1920, 963), fill=GREEN)
    d.text((42, 977), "ILLUSTRATIVE 2026 FLEET  /  PLANNING ASSUMPTIONS", font=font(17, True), fill=GREEN)
    face = font(30)
    lines = wrap(d, caption, face, 1640)
    assert len(lines) <= 2, caption
    d.multiline_text((40, 1005), "\n".join(lines), font=face, fill="white", spacing=0)
    d.line((1742, 984, 1742, 1056), fill="#42635d", width=2)
    d.multiline_text((1780, 996), "MARITIME\nCARBON", font=font(19, True), fill="white", spacing=0)
    im.save(path)
    return path


def run(args):
    result = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])


def seconds_in_video(path):
    output = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    match = re.search(r"Duration: (\d+):(\d+):([\d.]+)", output)
    assert match, output
    hours, minutes, seconds = map(float, match.groups())
    return hours*3600 + minutes*60 + seconds


def srt_timestamp(value):
    ms = round(value * 1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def encode_card(source, destination, seconds):
    run(["-loop", "1", "-framerate", FPS, "-i", source, "-frames:v", round(seconds*FPS),
         "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", destination])


def main():
    for folder in ("graphics", "clips", "qa"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    manifest = json.loads((OUT / "capture.json").read_text(encoding="utf-8"))
    source = OUT / "raw" / "walkthrough.webm"
    # Recording starts on the first delivered frame, slightly after new_page().
    # End-to-end wall time lets us remove that initial recorder offset.
    recording_duration = seconds_in_video(source)
    offset = max(0, manifest["recording_wall_seconds"] - recording_duration)
    assert offset < 2, f"Unexpected recording timestamp offset: {offset}"
    print(f"RAW duration={recording_duration:.2f}s; recorder offset={offset:.3f}s", flush=True)
    clips, subtitles, cut_list = [], [], []
    elapsed = 0.0

    def append(clip, seconds, caption, key):
        nonlocal elapsed
        clips.append(clip)
        subtitles.append(f"{len(subtitles)+1}\n{srt_timestamp(elapsed)} --> {srt_timestamp(elapsed+seconds)}\n{caption}\n")
        cut_list.append(dict(key=key, start=elapsed, end=elapsed+seconds, caption=caption, file=clip.name))
        elapsed += seconds

    intro = OUT / "clips" / "00-intro.mp4"
    encode_card(card("intro"), intro, 4)
    append(intro, 4, "Maritime Carbon. Which fuel, which voyage leg, at what cost?", "intro")
    for index, scene in enumerate(manifest["scenes"], 1):
        duration = round((scene["end"]-scene["start"])*FPS)/FPS
        frames = round(duration*FPS)
        z = scene["zoom"]
        ramp = 21
        enter = f"min(1,on/{ramp})"
        leave = f"min(1,({frames}-1-on)/{ramp})"
        zoom = f"1+{z-1:.4f}*({enter})*({enter})*(3-2*({enter}))*({leave})*({leave})*(3-2*({leave}))"
        fx, fy = scene["focus"]
        filters = (f"[0:v]fps={FPS},scale=3200:1600,zoompan=z='{zoom}':"
                   f"x='max(0,min(iw-iw/zoom,{fx*2}-iw/zoom/2))':"
                   f"y='max(0,min(ih-ih/zoom,{fy*2}-ih/zoom/2))':d=1:s=1920x960:fps={FPS},"
                   f"pad=1920:1080:0:0:color=0x102e32[screen];[screen][1:v]overlay=0:0:format=auto,format=yuv420p[v]")
        target = OUT / "clips" / f"{index:02d}-{scene['key']}.mp4"
        run(["-ss", max(0, scene["start"]-offset), "-i", source,
             "-loop", "1", "-framerate", FPS, "-i", overlay(index, scene["caption"]),
             "-filter_complex", filters, "-map", "[v]", "-frames:v", frames,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "4", "-an", target])
        append(target, duration, scene["caption"], scene["key"])
        print(f"ENCODED {scene['key']}: {duration:.2f}s", flush=True)
    outro = OUT / "clips" / "99-outro.mp4"
    encode_card(card("outro"), outro, 4)
    append(outro, 4, "From annual consumption to a traceable fleet decision. Let’s talk about your fleet.", "outro")
    playlist = OUT / "master-concat.txt"
    playlist.write_text("".join(f"file 'clips/{p.name}'\n" for p in clips), encoding="utf-8")
    master = OUT / "Maritime_Carbon_Desktop_Demo.mp4"
    run(["-f", "concat", "-safe", "0", "-i", playlist, "-c", "copy", "-movflags", "+faststart", master])
    (OUT / "Maritime_Carbon_Desktop_Demo.srt").write_text("\n".join(subtitles), encoding="utf-8")
    (OUT / "edit-timeline.json").write_text(json.dumps(cut_list, indent=2, ensure_ascii=False), encoding="utf-8")
    assert 75 <= elapsed <= 90, f"Review required: master length is {elapsed:.2f}s"

    # The teaser is assembled from the same verified case, footage and captions.
    teaser_choices = [("intro", 3), ("fleet", 3), ("atlas_legs", 4), ("alternative", 3),
                      ("calculate", 3), ("best_result", 4), ("leg_remarks", 6), ("outro", 4)]
    teaser_clips, teaser_srt = [], []
    teaser_elapsed = 0
    for index, (key, duration) in enumerate(teaser_choices):
        item = next(c for c in cut_list if c["key"] == key)
        target = OUT / "clips" / f"teaser-{index:02d}.mp4"
        original = OUT / "clips" / item["file"]
        # Pad only the last real frame if a source shot is shorter than its teaser hold.
        run(["-i", original, "-vf", "tpad=stop_mode=clone:stop_duration=3", "-frames:v", duration*FPS,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", target])
        teaser_clips.append(target)
        teaser_srt.append(f"{index+1}\n{srt_timestamp(teaser_elapsed)} --> {srt_timestamp(teaser_elapsed+duration)}\n{item['caption']}\n")
        teaser_elapsed += duration
    assert teaser_elapsed == 30
    playlist = OUT / "teaser-concat.txt"
    playlist.write_text("".join(f"file 'clips/{p.name}'\n" for p in teaser_clips), encoding="utf-8")
    teaser = OUT / "Maritime_Carbon_Teaser_30s.mp4"
    run(["-f", "concat", "-safe", "0", "-i", playlist, "-c", "copy", "-movflags", "+faststart", teaser])
    (OUT / "Maritime_Carbon_Teaser_30s.srt").write_text("\n".join(teaser_srt), encoding="utf-8")
    for target in (master, teaser):
        # Decode the complete output, including every frame at each cut.
        run(["-i", target, "-f", "null", "-"])
        print(f"DELIVERABLE {target.name}: {seconds_in_video(target):.2f}s; {target.stat().st_size/1e6:.1f} MB", flush=True)
    for index, item in enumerate(cut_list):
        t = (item["start"] + item["end"])/2
        run(["-ss", t, "-i", master, "-frames:v", "1", OUT / "qa" / f"{index:02d}-{item['key']}.png"])
    print("Rendering and full decode verification complete.", flush=True)


if __name__ == "__main__":
    main()
