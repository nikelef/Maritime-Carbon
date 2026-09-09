"""Add ranked strategy explanations, direct operating narration and a thank-you page."""
import asyncio
import hashlib
import json
import math
import re
import subprocess
import sys
import wave
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import edge_tts
from scripts.video.render import FFMPEG, ROOT, card, run, seconds_in_video
from scripts.video.render_single import caption_image
from scripts.video.single_voyage import OUT, VOICE
from scripts.video.pitch_opening import OPENING

REVISION = OUT / "closing-revision"
RATE, FPS = 48000, 30
SPEECH = [
    ("rank_1", "1 / TARGETED HVO · Lowest evaluated annual cost: €1,001,422.09",
     "Best: targeted H V O, with no pooling.", 5),
    ("rank_2", "2 / POOLING ALLOWED · Same cost: €1,001,422.09 · No pooling used",
     "Allowing pooling reaches the same cost here.", 4.5),
    ("rank_3", "3 / CURRENT FUELS + POOLING · €1,003,035.63 · €1,613.55 above best",
     "Current fuels plus pooling cost about sixteen hundred euros more.", 5.5),
    ("rank_4", "4 / CURRENT FUELS + PENALTIES · Highest cost: €1,038,652.88",
     "Current fuels plus penalties are the most expensive.", 5),
    ("operating", "", "The ship replaces gas oil with H V O on its intra E U leg.", 0),
    ("breakdown", "", "Annual costs include fuel and allowances. No pooling or Fuel E U penalty remains.", 0),
    ("thanks", "THANK YOU", "Thank you for watching. Maritime Carbon. Let's talk about your fleet.", 7),
]


async def prepare():
    REVISION.mkdir(exist_ok=True)
    original = {s["key"]:s for s in json.loads((OUT / "edit-timeline.json").read_text(encoding="utf-8"))}
    shots = []
    for key, caption, text, preferred in SPEECH:
        digest = hashlib.sha256((VOICE+"-4%"+text).encode()).hexdigest()[:16]
        mp3 = REVISION / f"{digest}.mp3"
        if not mp3.exists():
            await edge_tts.Communicate(text, VOICE, rate="-4%").save(str(mp3))
        wav = REVISION / f"{key}.wav"
        trim = "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse"
        run(["-i", mp3, "-af", trim, "-ar", RATE, "-ac", "1", "-c:a", "pcm_s16le", wav])
        with wave.open(str(wav), "rb") as audio:
            speech = audio.getnframes()/RATE
        frames = math.ceil(max(preferred, speech+1)*FPS)
        if key in original:
            frames = max(frames, original[key]["frames"])
        shots.append(dict(key=key, caption=caption, text=text, speech_seconds=speech,
                          lead=.5, frames=frames, duration=frames/FPS))
        print(f"VOICE {key}: {speech:.2f}s; hold {frames/FPS:.2f}s", flush=True)
    (REVISION / "plan.json").write_text(json.dumps(shots, indent=2, ensure_ascii=False), encoding="utf-8")


def render():
    plan = {s["key"]:s for s in json.loads((REVISION / "plan.json").read_text(encoding="utf-8"))}
    capture = json.loads((REVISION / "capture.json").read_text())
    raw = REVISION / "walkthrough.webm"
    offset = capture["recording_wall_seconds"]-seconds_in_video(raw)
    assert abs(offset)<2
    for scene in capture["scenes"]:
        s = plan[scene["key"]]
        # No crop: retain the strategy list and annual cost context together.
        run(["-ss", max(0,scene["start"]-offset), "-i", raw,
             "-loop", "1", "-framerate", FPS, "-i", caption_image(s),
             "-filter_complex", "[0:v]fps=30,scale=1920:960,pad=1920:1080:0:0:color=0x102e32[v];[v][1:v]overlay=0:0:format=auto,format=yuv420p[out]",
             "-map", "[out]", "-frames:v", s["frames"], "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "4", "-an", REVISION / f"{s['key']}.mp4"])
        print(f"ENCODE {s['key']}", flush=True)
    thanks = plan["thanks"]
    picture = card("thanks", destination=REVISION / "thanks.png")
    run(["-loop", "1", "-framerate", FPS, "-i", picture, "-frames:v", thanks["frames"],
         "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", REVISION / "thanks.mp4"])
    pieces = []
    def append(s, clip, speech):
        pieces.append(dict(s) | dict(clip=str(clip), wav=str(speech)))
    for s in json.loads((OPENING / "plan.json").read_text()):
        append(s, OPENING / f"{s['key']}.mp4", OPENING / f"{s['key']}.wav")
    original = json.loads((OUT / "edit-timeline.json").read_text(encoding="utf-8"))
    for index, s in enumerate(original):
        key = s["key"]
        if key == "best":
            for rank in range(1,5):
                r = plan[f"rank_{rank}"]
                append(r, REVISION / f"{r['key']}.mp4", REVISION / f"{r['key']}.wav")
        clip = OUT / "clips" / f"{index:02}-{key}.mp4"
        speech = OUT / "speech" / f"{key}.wav"
        if key in ("operating", "breakdown"):
            updated = plan[key]
            if updated["frames"]>s["frames"]:
                held = REVISION / f"{key}.mp4"
                run(["-i", clip, "-vf", "tpad=stop_mode=clone:stop_duration=10", "-frames:v", updated["frames"],
                     "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", held])
                clip = held
            s = s | {k:v for k,v in updated.items() if k!="caption"}
            speech = REVISION / f"{key}.wav"
        append(s, clip, speech)
    append(thanks, REVISION / "thanks.mp4", REVISION / "thanks.wav")
    assert all("section three" not in s["text"].lower() and "section four" not in s["text"].lower() for s in pieces)
    duration = sum(s["frames"] for s in pieces)/FPS
    track = bytearray(round(duration*RATE)*2)
    elapsed_frames = 0
    for s in pieces:
        elapsed = elapsed_frames/FPS
        with wave.open(s["wav"], "rb") as audio:
            pcm = audio.readframes(audio.getnframes())
        begin = round((elapsed+s["lead"])*RATE)*2
        assert s["lead"]+len(pcm)/(RATE*2)+.35 <= s["duration"]
        track[begin:begin+len(pcm)] = pcm
        s.update(output_start=elapsed, output_end=elapsed+s["duration"])
        elapsed_frames += s["frames"]
    playlist = REVISION / "concat.txt"
    playlist.write_text("".join("file '"+s["clip"].replace("\\","/")+"'\n" for s in pieces), encoding="utf-8")
    silent = REVISION / "picture.mp4"
    run(["-f", "concat", "-safe", "0", "-i", playlist, "-c", "copy", silent])
    wav = REVISION / "narration.wav"
    with wave.open(str(wav), "wb") as audio:
        audio.setparams((1,2,RATE,0,"NONE","not compressed"))
        audio.writeframes(track)
    final = OUT / "Maritime_Carbon_One_Voyage_2026_Final.mp4"
    run(["-i", silent, "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", RATE, "-ac", "2", "-af", "loudnorm=I=-16:TP=-1.5:LRA=7",
         "-t", duration, "-sn", "-movflags", "+faststart", final])
    run(["-i", final, "-f", "null", "-"])
    assert abs(seconds_in_video(final)-duration)<.05
    meta = subprocess.run([FFMPEG,"-hide_banner","-i",str(final)],capture_output=True,text=True).stderr
    assert re.findall(r"Stream #0:\d+.*?: (Video|Audio|Subtitle):", meta)==["Video","Audio"]
    assert "1920x1080" in meta and "30 fps" in meta
    (REVISION / "edit-timeline.json").write_text(json.dumps(pieces,indent=2,ensure_ascii=False),encoding="utf-8")
    transcript = REVISION / "Narration.txt"
    transcript.write_text("Synthetic British English narration. One visible caption layer.\n\n"+"\n\n".join(s["text"] for s in pieces),encoding="utf-8")
    for s in pieces:
        if s["key"].startswith("rank_") or s["key"] in ("best","operating","breakdown","thanks"):
            run(["-ss", (s["output_start"]+s["output_end"])/2,"-i",final,"-frames:v","1",REVISION / f"qa-{s['key']}.png"])
    package = OUT / "Maritime_Carbon_One_Voyage_2026_Final_Review.zip"
    with ZipFile(package,"w") as archive:
        for p in (final,transcript,OUT/"demo-inputs.json",OUT/"demo-audit.json",ROOT/"docs"/"VIDEO_SINGLE_VOYAGE_REVIEW.md"):
            archive.write(p,p.name,compress_type=ZIP_STORED if p.suffix==".mp4" else ZIP_DEFLATED)
    print(f"READY: {duration:.2f}s; {final}",flush=True)


if __name__=="__main__":
    if sys.argv[1]=="prepare":
        asyncio.run(prepare())
    elif sys.argv[1]=="render":
        render()
