import os
import uuid
import subprocess
import edge_tts
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp", exist_ok=True)

async def generate_vo_and_srt(text: str, voice: str, audio_path: str, srt_path: str):
    communicate = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()

    with open(audio_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    with open(srt_path, "w", encoding="utf-8") as srt_file:
        srt_file.write(submaker.get_srt())

def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    return float(result.stdout.strip())

@app.post("/process-video")
async def process_video(
    video: UploadFile = File(...),
    text: str = Form(...),
    voice: str = Form("id-ID-ArdiNeural")
):
    job_id = str(uuid.uuid4())
    input_video = f"temp/{job_id}_in.mp4"
    audio_path = f"temp/{job_id}_vo.mp3"
    srt_path = f"temp/{job_id}_sub.srt"
    output_video = f"temp/{job_id}_out.mp4"

    with open(input_video, "wb") as f:
        f.write(await video.read())

    await generate_vo_and_srt(text, voice, audio_path, srt_path)
    duration = get_audio_duration(audio_path)

    subtitle_filter = (
        f"subtitles={srt_path}:force_style="
        "'FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=40'"
    )

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", input_video,
        "-i", audio_path,
        "-t", str(duration),
        "-vf", subtitle_filter,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        output_video
    ]
    subprocess.run(ffmpeg_cmd, check=True)

    return FileResponse(output_video, media_type="video/mp4", filename="hasil_edit.mp4")
