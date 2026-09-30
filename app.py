
import os,json,uuid,subprocess,shutil,re
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,Form,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel
import edge_tts
from deep_translator import GoogleTranslator

B=Path(__file__).parent; W=B/"work"; W.mkdir(exist_ok=True)
MAX_MB=int(os.getenv("MAX_UPLOAD_MB","200"))
MAX_BYTES=MAX_MB*1024*1024
app=FastAPI(title="VideoBridge AI V9")
@app.get("/health")
def health():
 return {"ok":True,"app":"VideoBridge AI V9"}; app.mount("/static",StaticFiles(directory=B/"static"),name="static")
MODEL=None
VOICES={
"ko":{"female":"ko-KR-SunHiNeural","male":"ko-KR-InJoonNeural"},
"zh":{"female":"zh-CN-XiaoxiaoNeural","male":"zh-CN-YunxiNeural"},
"en":{"female":"en-US-JennyNeural","male":"en-US-GuyNeural"}}
LANG={"ko":"ko","zh":"zh-CN","en":"en"}

def run(*a):
 p=subprocess.run(["ffmpeg","-y",*map(str,a)],capture_output=True,text=True)
 if p.returncode: raise RuntimeError(p.stderr[-2500:])
def duration(p):
 q=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(p)],capture_output=True,text=True)
 return max(.1,float(q.stdout.strip() or 1))
def tempo(x): return f"atempo={max(.5,min(2.0,x)):.5f}"
def srt_time(s):
 ms=int(round(s*1000)); h=ms//3600000; ms%=3600000; m=ms//60000; ms%=60000; sec=ms//1000; ms%=1000
 return f"{h:02}:{m:02}:{sec:02},{ms:03}"

@app.get("/")
def home(): return FileResponse(B/"index.html")

@app.post("/api/process")
async def process(video:UploadFile=File(...),source:str=Form("ko"),target:str=Form("zh"),gender:str=Form("female"),terms:str=Form("")):
 global MODEL
 jid=uuid.uuid4().hex; d=W/jid; d.mkdir(); src=d/"input.mp4"
 with src.open("wb") as f: shutil.copyfileobj(video.file,f)
 if src.stat().st_size > MAX_BYTES:
  src.unlink(missing_ok=True)
  raise HTTPException(413,f"Video exceeds {MAX_MB} MB upload limit")
 wav=d/"speech.wav"; run("-i",src,"-vn","-ac","1","-ar","16000",wav)
 if MODEL is None: MODEL=WhisperModel(os.getenv("WHISPER_MODEL","tiny"),device="cpu",compute_type="int8")
 sg,_=MODEL.transcribe(str(wav),language=source,vad_filter=True)
 term={}
 for line in terms.splitlines():
  if "=" in line:
   a,b=line.split("=",1); term[a.strip()]=b.strip()
 translator=GoogleTranslator(source=LANG[source],target=LANG[target])
 out=[]
 for s in sg:
  text=s.text.strip()
  translated=translator.translate(text) if text else ""
  for a,b in term.items():
   if source=="ko" and target=="zh": translated=translated.replace(a,b)
   if source=="zh" and target=="ko": translated=translated.replace(b,a)
  out.append({"start":round(s.start,3),"end":round(s.end,3),"source":text,"translation":translated})
 (d/"segments.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 return {"job":jid,"segments":out,"voice":VOICES[target][gender],
 "model":os.getenv("WHISPER_MODEL","tiny"),"duration":duration(src)}

@app.post("/api/render")
async def render(job:str=Form(...),target:str=Form(...),gender:str=Form("female"),segments:str=Form(...),original_volume:float=Form(.12),dub_volume:float=Form(1.0),subtitle_mode:str=Form("translation")):
 d=W/job; src=d/"input.mp4"
 if not src.exists(): raise HTTPException(404,"job not found")
 sg=json.loads(segments); clips=[]
 voice=VOICES[target][gender]
 for i,s in enumerate(sg):
  text=(s.get("translation") or "").strip()
  if not text: continue
  mp3=d/f"tts{i}.mp3"; await edge_tts.Communicate(text,voice).save(str(mp3))
  wanted=max(.35,float(s["end"])-float(s["start"])); actual=duration(mp3); ratio=actual/wanted
  wav=d/f"fit{i}.wav"
  # two-stage if ratio exceeds atempo range
  if ratio>2:
   run("-i",mp3,"-filter:a",f"atempo=2.0,atempo={min(2,ratio/2):.5f}","-ar","48000","-ac","2",wav)
  else: run("-i",mp3,"-filter:a",tempo(ratio),"-ar","48000","-ac","2",wav)
  clips.append((wav,int(float(s["start"])*1000)))
 inputs=[]; fs=[]
 for n,(f,delay) in enumerate(clips):
  inputs+=["-i",str(f)]; fs.append(f"[{n}:a]adelay={delay}|{delay},volume={dub_volume}[d{n}]")
 if not clips: raise HTTPException(400,"No dubbing")
 mix="".join(f"[d{i}]" for i in range(len(clips)))+f"amix=inputs={len(clips)}:normalize=0[dub]"
 dub=d/"dub.wav"; run(*inputs,"-filter_complex",";".join(fs+[mix]),"-map","[dub]",dub)
 # subtitles
 srt=d/"sub.srt"; rows=[]
 for i,s in enumerate(sg,1):
  if subtitle_mode=="dual": txt=f'{s["source"]}\n{s["translation"]}'
  elif subtitle_mode=="source": txt=s["source"]
  else: txt=s["translation"]
  rows.append(f'{i}\n{srt_time(float(s["start"]))} --> {srt_time(float(s["end"]))}\n{txt}\n')
 srt.write_text("\n".join(rows),encoding="utf-8")
 out=d/"final.mp4"
 # burn subtitles + mix original and dub, encode H264/AAC
 filt=f"[0:a]volume={original_volume}[o];[o][1:a]amix=inputs=2:duration=first:normalize=0[a];[0:v]subtitles='{str(srt).replace(chr(92),chr(47))}':force_style='FontSize=18,Outline=2,Alignment=2'[v]"
 run("-i",src,"-i",dub,"-filter_complex",filt,"-map","[v]","-map","[a]","-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-b:a","192k","-movflags","+faststart",out)
 return FileResponse(out,media_type="video/mp4",filename="VideoBridge_V6_dubbed.mp4")
