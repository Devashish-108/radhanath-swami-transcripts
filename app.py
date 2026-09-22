
import os, re, io, json, hashlib, urllib.parse
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import streamlit as st

BASE = "https://audio.iskcondesiretree.com"
ROOT_PATH = "/02_-_ISKCON_Swamis/ISKCON_Swamis_-_R_to_Y/His_Holiness_Radhanath_Swami/Lectures/00_-_Year_wise"
ROOT_URL = BASE + "/index.php?f=" + urllib.parse.quote(ROOT_PATH, safe="/") + "&q=f"

CACHE = Path("cache")
AUDIO_CACHE = CACHE / "audio"
TEXT_CACHE = CACHE / "transcripts"
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
TEXT_CACHE.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Radhanath-Swami-Lecture-Transcriber/1.0"}

def page_url(path):
    return BASE + "/index.php?f=" + urllib.parse.quote(path, safe="/") + "&q=f"

@st.cache_data(ttl=3600, show_spinner=False)
def get_page(path):
    r = requests.get(page_url(path), headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def parse_listing(path):
    html = get_page(path)
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        label = " ".join(a.get_text(" ", strip=True).split())
        if not label:
            continue
        # Site uses both index.php?f=... and direct MP3 URLs.
        if ".mp3" in href.lower():
            url = urllib.parse.urljoin(BASE + "/", href)
            items.append(("file", label, url))
        elif "index.php?f=" in href:
            parsed = urllib.parse.urlparse(href)
            qs = urllib.parse.parse_qs(parsed.query)
            target = qs.get("f", [None])[0]
            if target:
                target = urllib.parse.unquote(target)
                if target.startswith(ROOT_PATH + "/"):
                    items.append(("folder", label, target))
    # De-duplicate while preserving order
    out, seen = [], set()
    for x in items:
        k = x[0] + "|" + x[2]
        if k not in seen:
            seen.add(k); out.append(x)
    return out

@st.cache_data(ttl=3600, show_spinner=False)
def get_years():
    return [(label, target) for kind, label, target in parse_listing(ROOT_PATH) if kind == "folder"]

@st.cache_data(ttl=3600, show_spinner=False)
def get_lectures_recursive(year_path):
    results = []
    seen = set()
    def walk(path):
        if path in seen:
            return
        seen.add(path)
        for kind, label, target in parse_listing(path):
            if kind == "file":
                results.append({"title": label, "url": target})
            else:
                walk(target)
    walk(year_path)
    return results

def safe_id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:24]

def download_audio(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return
    with requests.get(url, headers=HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)

def transcribe(audio_path, model_name, language=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        st.error("faster-whisper is not installed. Run: pip install -r requirements.txt")
        st.stop()
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute = os.getenv("WHISPER_COMPUTE_TYPE", "int8" if device == "cpu" else "float16")
    model = WhisperModel(model_name, device=device, compute_type=compute)
    kwargs = {"beam_size": 5, "vad_filter": True}
    if language:
        kwargs["language"] = language
    segments, info = model.transcribe(str(audio_path), **kwargs)
    segs = []
    for s in segments:
        segs.append({
            "start": float(s.start),
            "end": float(s.end),
            "text": s.text.strip()
        })
    return segs, info.language

def fmt_time(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

st.set_page_config(page_title="Radhanath Swami Lecture Transcriber", page_icon="🕉️", layout="wide")
st.title("🕉️ HH Radhanath Swami — Lecture Transcriber")
st.caption("Source: Audio ISKCON Desire Tree • Year-wise lecture archive")

with st.sidebar:
    st.header("Settings")
    model = st.selectbox(
        "Whisper model",
        ["tiny", "base", "small", "medium"],
        index=1,
        help="Runs locally. Larger models are slower but generally more accurate."
    )
    language = st.selectbox("Language", ["Auto-detect", "English", "Hindi", "Marathi", "Other"], index=0)
    lang_map = {"Auto-detect": None, "English": "en", "Hindi": "hi", "Marathi": "mr", "Other": None}
    st.info("No YouTube is used. The app reads the exact year-wise Radhanath Swami archive and downloads the original MP3 directly.")

try:
    years = get_years()
except Exception as e:
    st.error(f"Could not read the archive: {e}")
    st.stop()

year_labels = [x[0] for x in years]
if not year_labels:
    st.error("No year folders were found.")
    st.stop()

selected_label = st.selectbox("1. Select a year", year_labels)
year_path = dict(years)[selected_label]

with st.spinner(f"Loading lectures for {selected_label}…"):
    try:
        lectures = get_lectures_recursive(year_path)
    except Exception as e:
        st.error(f"Could not load that year: {e}")
        st.stop()

st.write(f"**{len(lectures)} recordings found**")
search = st.text_input("2. Search within this year", placeholder="e.g. Bhagavad Gita, humility, Chaitanya, questions…")
filtered = lectures
if search.strip():
    q = search.lower()
    filtered = [x for x in lectures if q in x["title"].lower()]

titles = [x["title"] for x in filtered]
if not titles:
    st.warning("No lectures matched that search.")
    st.stop()

selected_title = st.selectbox("3. Select a lecture", titles)
lecture = next(x for x in filtered if x["title"] == selected_title)
st.write("**Source file:**", lecture["title"])
st.audio(lecture["url"])

if st.button("📝 Generate full transcript", type="primary"):
    sid = safe_id(lecture["url"])
    audio_path = AUDIO_CACHE / f"{sid}.mp3"
    txt_path = TEXT_CACHE / f"{sid}.json"

    try:
        with st.spinner("Downloading the original MP3…"):
            download_audio(lecture["url"], audio_path)
        with st.spinner(f"Transcribing locally with Whisper ({model})…"):
            segs, detected = transcribe(audio_path, model, lang_map[language])
        data = {"title": lecture["title"], "url": lecture["url"], "language": detected, "segments": segs}
        txt_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        st.session_state["transcript_data"] = data
    except Exception as e:
        st.error(f"Transcription failed: {e}")
        st.stop()

data = st.session_state.get("transcript_data")
if data and data.get("url") == lecture["url"]:
    st.divider()
    st.subheader("Transcript")
    st.caption(f"Detected language: {data.get('language', 'unknown')}")
    plain = "\n\n".join(s["text"] for s in data["segments"])
    timed = "\n".join(f"[{fmt_time(s['start'])}] {s['text']}" for s in data["segments"])
    tab1, tab2 = st.tabs(["Readable transcript", "Timestamped transcript"])
    with tab1:
        st.text_area("Transcript", plain, height=600)
    with tab2:
        st.text_area("Transcript with timestamps", timed, height=600)
    st.download_button("⬇️ Download TXT", plain, file_name="radhanath_swami_transcript.txt", mime="text/plain")
    st.download_button("⬇️ Download timestamped TXT", timed, file_name="radhanath_swami_transcript_timestamps.txt", mime="text/plain")
    st.markdown(f"[Open original Audio ISKCON Desire Tree file]({data['url']})")
