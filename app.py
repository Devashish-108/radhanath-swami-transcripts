import os
import re
import json
import hashlib
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import streamlit as st

# ============================================================
# CONFIGURATION
# ============================================================

AUDIO_BASE = "https://audio.iskcondesiretree.com"
AUDIO_ROOT = (
    "/02_-_ISKCON_Swamis/ISKCON_Swamis_-_R_to_Y/"
    "His_Holiness_Radhanath_Swami/Lectures/00_-_Year_wise"
)

PLAYLIST_URL = (
    "https://www.youtube.com/playlist?"
    "list=PLvKq1ZnGL6pw7xd_BD76Bvd2xJih6AzQm"
)

TRANSCRIPT_API_BASE = "https://transcriptapi.com/api/v2"

CACHE = Path("cache")
AUDIO_CACHE = CACHE / "audio"
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Radhanath-Swami-Lecture-Library)",
    "Referer": AUDIO_BASE + "/",
}

# ============================================================
# PAGE + STYLE
# ============================================================

st.set_page_config(
    page_title="Radhanath Swami Lecture Library",
    page_icon="🕉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {
    background:
      radial-gradient(circle at 0% 0%, rgba(218,170,83,.13), transparent 28%),
      radial-gradient(circle at 100% 10%, rgba(111,79,42,.08), transparent 25%),
      #faf8f4;
}
.block-container { max-width: 1200px; padding-top: 2rem; padding-bottom: 4rem; }

.hero {
    background: linear-gradient(135deg,#fff7e7,#f3eadc);
    border: 1px solid #eadcc7;
    border-radius: 24px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.4rem;
    box-shadow: 0 12px 32px rgba(65,45,25,.07);
}
.kicker { color:#95672a; font-size:.78rem; font-weight:800; letter-spacing:.15em; text-transform:uppercase; }
.hero h1 { color:#3d2b1d; font-size:2.35rem; margin:.25rem 0 .5rem; }
.hero p { color:#6f5c49; margin:0; line-height:1.6; }

.card {
    background:#fff;
    border:1px solid #e9dfd3;
    border-radius:20px;
    padding:1.35rem;
    box-shadow:0 8px 24px rgba(70,50,30,.05);
    margin-bottom:1rem;
}
.title { color:#443325; font-size:1.4rem; font-weight:800; }
.caption { color:#796b5d; margin:.2rem 0 1rem; }
.pill {
    display:inline-block; padding:.28rem .65rem; border-radius:999px;
    background:#f5ead8; color:#875d26; font-size:.76rem; font-weight:750;
    margin-right:.35rem;
}
.info {
    background:#fbf7f0; border:1px solid #eee2d2; border-radius:14px;
    padding:.9rem 1rem; color:#665748; line-height:1.55;
}
.sidebar-label {
    color:#8b5e25; font-size:.75rem; font-weight:800;
    letter-spacing:.12em; text-transform:uppercase;
}
div[data-testid="stSidebar"] {
    background: #f6f1e8;
    border-right: 1px solid #e5d9c9;
}
div[data-testid="stSidebar"] .stRadio label { font-weight:700; }
button { border-radius:12px !important; }
.footer { text-align:center; color:#8b7b6b; font-size:.8rem; padding-top:2rem; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# AUDIO ARCHIVE
# ============================================================

def audio_page_url(path):
    return AUDIO_BASE + "/index.php?" + urllib.parse.urlencode({"q":"f","f":path})

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_audio_page(path):
    r = requests.get(audio_page_url(path), headers=HEADERS, timeout=45)
    r.raise_for_status()
    return r.text

def normalize_path(value):
    value = urllib.parse.unquote(value or "")
    return value if value.startswith("/") else "/" + value

def parse_audio_listing(path):
    soup = BeautifulSoup(fetch_audio_page(path), "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        label = " ".join(a.get_text(" ", strip=True).split())
        absolute = urllib.parse.urljoin(AUDIO_BASE + "/", href)
        parsed = urllib.parse.urlparse(absolute)
        qs = urllib.parse.parse_qs(parsed.query)

        for target0 in qs.get("f", []):
            target = normalize_path(target0)
            if target.startswith(AUDIO_ROOT + "/"):
                if target.lower().endswith(".mp3"):
                    results.append(("file", label or Path(target).name, AUDIO_BASE + target))
                else:
                    results.append(("folder", label or Path(target).name, target))
                break

    seen, unique = set(), []
    for x in results:
        key = x[0] + "|" + x[2]
        if key not in seen:
            seen.add(key); unique.append(x)
    return unique

@st.cache_data(ttl=3600, show_spinner=False)
def get_years():
    years = [(l,t) for k,l,t in parse_audio_listing(AUDIO_ROOT) if k=="folder"]
    years.sort(key=lambda x: (0 if re.search(r"(19|20)\d{2}",x[0]) else 1, x[0].lower()))
    return years

@st.cache_data(ttl=3600, show_spinner=False)
def get_year_lectures(year_path):
    found, visited = [], set()
    def walk(path):
        if path in visited: return
        visited.add(path)
        for kind,label,target in parse_audio_listing(path):
            if kind == "file":
                found.append({"title":label,"url":target})
            else:
                walk(target)
    walk(year_path)
    return found

def download_audio(url, dest):
    if dest.exists() and dest.stat().st_size > 0: return
    with requests.get(url, headers=HEADERS, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(dest,"wb") as f:
            for chunk in r.iter_content(1024*1024):
                if chunk: f.write(chunk)

def transcribe_audio(path, model, language=None):
    from faster_whisper import WhisperModel
    device = os.getenv("WHISPER_DEVICE","cpu")
    compute = os.getenv("WHISPER_COMPUTE_TYPE","int8" if device=="cpu" else "float16")
    wm = WhisperModel(model, device=device, compute_type=compute)
    opts = {"beam_size":5,"vad_filter":True}
    if language: opts["language"] = language
    segments, info = wm.transcribe(str(path), **opts)
    return [
        {"start":float(s.start),"text":s.text.strip()}
        for s in segments if s.text.strip()
    ], info.language

def fmt_time(sec):
    sec=int(sec); h,rem=divmod(sec,3600); m,s=divmod(rem,60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# ============================================================
# TRANSCRIPT API
# ============================================================

def get_api_key():
    # Streamlit Secrets is the safe production location.
    for key in ("TRANSCRIPT_API_KEY", "TRANSCRIPTAPI_KEY"):
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
        if os.getenv(key):
            return os.getenv(key)
    return None

@st.cache_data(ttl=1800, show_spinner=False)
def playlist_page(playlist_url, api_key, continuation=None):
    headers = {"Authorization": f"Bearer {api_key}"}
    if continuation:
        params = {"continuation": continuation}
    else:
        params = {"playlist": playlist_url}
    r = requests.get(
        f"{TRANSCRIPT_API_BASE}/youtube/playlist/videos",
        headers=headers,
        params=params,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()

def load_all_playlist_videos(api_key):
    results = []
    continuation = None
    page_guard = set()

    for _ in range(30):  # safety cap; enough for very large playlists
        data = playlist_page(PLAYLIST_URL, api_key, continuation)
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        continuation = data.get("continuation_token")
        if not continuation or continuation in page_guard:
            break
        page_guard.add(continuation)

    # Preserve API/playlist order; don't alphabetize.
    return results

def get_youtube_transcript(video_url, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "video_url": video_url,
        "format": "json",
        "include_timestamp": "true",
        "send_metadata": "true",
    }
    r = requests.get(
        f"{TRANSCRIPT_API_BASE}/youtube/transcript",
        headers=headers,
        params=params,
        timeout=90,
    )
    if r.status_code == 401:
        raise RuntimeError("The TranscriptAPI key is invalid or not authorized.")
    if r.status_code == 402:
        raise RuntimeError("TranscriptAPI credits/plan are exhausted.")
    if r.status_code == 404:
        raise RuntimeError("This YouTube video has no transcript/captions available.")
    if r.status_code == 429:
        raise RuntimeError("TranscriptAPI rate limit reached. Please try again later.")
    r.raise_for_status()
    return r.json()

# ============================================================
# HEADER
# ============================================================

st.markdown("""
<div class="hero">
  <div class="kicker">Lecture Library</div>
  <h1>🕉️ HH Radhanath Swami</h1>
  <p>Explore the original audio archive and the selected YouTube lecture collection,
  with transcripts brought together in one simple interface.</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:
    st.markdown('<div class="sidebar-label">Library</div>', unsafe_allow_html=True)
    section = st.radio(
        "Choose a section",
        ["🕉️ Section 1 — Audio Archive", "▶️ Section 2 — YouTube Lectures"],
        label_visibility="collapsed",
    )
    st.divider()

    if section.startswith("🕉️"):
        st.markdown("### ⚙️ Audio transcription")
        st.selectbox("Whisper model", ["tiny","base","small","medium"], index=1, key="whisper_model")
        st.selectbox("Language", ["Auto-detect","English","Hindi","Marathi"], index=0, key="audio_language_name")
        lang_map = {"Auto-detect":None,"English":"en","Hindi":"hi","Marathi":"mr"}
        st.session_state["audio_language"] = lang_map[st.session_state["audio_language_name"]]
    else:
        st.markdown("### 🔐 YouTube transcript API")
        if get_api_key():
            st.success("API key detected.")
        else:
            st.warning("API key not configured.")
            st.caption("Add TRANSCRIPT_API_KEY to Streamlit Secrets to enable the playlist and transcripts.")

# ============================================================
# SECTION 1
# ============================================================

if section.startswith("🕉️"):
    st.markdown("""
    <div class="card">
      <div class="title">Audio ISKCON Desire Tree</div>
      <div class="caption">The exact year-wise archive you supplied.</div>
      <span class="pill">Original MP3</span>
      <span class="pill">Year-wise</span>
      <span class="pill">Whisper</span>
    </div>
    """, unsafe_allow_html=True)

    try:
        years = get_years()
    except Exception as e:
        st.error(f"Could not read the audio archive: {e}")
        years = []

    if years:
        year_labels = [x[0] for x in years]
        selected_year = st.selectbox("Choose a year", year_labels, key="audio_year")
        year_path = dict(years)[selected_year]

        with st.spinner("Loading lectures…"):
            lectures = get_year_lectures(year_path)

        st.caption(f"{len(lectures)} recordings found in {selected_year}.")
        q = st.text_input("Search lectures", placeholder="Title, date, place, topic…", key="audio_search")

        if q.strip():
            lectures = [x for x in lectures if q.lower() in x["title"].lower()]

        lectures.sort(key=lambda x:x["title"].lower())

        if lectures:
            title = st.selectbox("Choose a lecture", [x["title"] for x in lectures], key="audio_lecture")
            lecture = next(x for x in lectures if x["title"] == title)

            st.markdown(f'<div class="info"><strong>{lecture["title"]}</strong></div>', unsafe_allow_html=True)
            st.audio(lecture["url"])

            c1,c2 = st.columns(2)
            with c1:
                go = st.button("📝 Generate transcript", type="primary", use_container_width=True)
            with c2:
                st.link_button("🔗 Open original MP3", lecture["url"], use_container_width=True)

            if go:
                sid = hashlib.sha256(lecture["url"].encode()).hexdigest()[:24]
                audio_path = AUDIO_CACHE / f"{sid}.mp3"
                try:
                    with st.spinner("Downloading original MP3…"):
                        download_audio(lecture["url"], audio_path)
                    with st.spinner("Transcribing with Whisper…"):
                        segs, detected = transcribe_audio(
                            audio_path,
                            st.session_state.get("whisper_model","base"),
                            st.session_state.get("audio_language"),
                        )
                    st.session_state["audio_result"] = {
                        "url":lecture["url"], "title":lecture["title"],
                        "language":detected, "segments":segs
                    }
                except Exception as e:
                    st.error(f"Transcription failed: {e}")

            result = st.session_state.get("audio_result")
            if result and result["url"] == lecture["url"]:
                st.divider()
                st.subheader("Transcript")
                st.caption(f"Detected language: {result['language']}")
                plain = "\n\n".join(x["text"] for x in result["segments"])
                timed = "\n".join(f"[{fmt_time(x['start'])}] {x['text']}" for x in result["segments"])
                a,b = st.tabs(["Readable","Timestamps"])
                with a: st.text_area("Transcript",plain,height=560)
                with b: st.text_area("Timestamped transcript",timed,height=560)
                d1,d2=st.columns(2)
                with d1: st.download_button("⬇️ Download TXT",plain,"radhanath_transcript.txt","text/plain",use_container_width=True)
                with d2: st.download_button("⬇️ Download timestamps",timed,"radhanath_transcript_timestamps.txt","text/plain",use_container_width=True)
        else:
            st.warning("No lectures matched the search.")
    else:
        st.warning("No year folders were detected.")

# ============================================================
# SECTION 2
# ============================================================

else:
    st.markdown("""
    <div class="card">
      <div class="title">YouTube Lecture Collection</div>
      <div class="caption">The supplied playlist, shown in its original order.</div>
      <span class="pill">Playlist order</span>
      <span class="pill">TranscriptAPI</span>
      <span class="pill">Transcript in this app</span>
    </div>
    """, unsafe_allow_html=True)

    api_key = get_api_key()

    if not api_key:
        st.error("Section 2 is not connected yet.")
        st.markdown("""
        <div class="info">
        Add a Streamlit secret named <strong>TRANSCRIPT_API_KEY</strong>.
        Do not put the key in <code>app.py</code> or commit it to GitHub.
        </div>
        """, unsafe_allow_html=True)
        st.link_button("Open TranscriptAPI", "https://transcriptapi.com/")
        st.stop()

    if "yt_videos" not in st.session_state:
        with st.spinner("Loading the playlist from TranscriptAPI…"):
            try:
                st.session_state["yt_videos"] = load_all_playlist_videos(api_key)
            except Exception as e:
                st.error(f"Could not load the playlist: {e}")
                st.stop()

    videos = st.session_state["yt_videos"]
    st.success(f"{len(videos)} lectures loaded in playlist order.")

    q = st.text_input(
        "Search lectures",
        placeholder="Search by lecture title…",
        key="yt_search",
    )
    visible = videos
    if q.strip():
        visible = [v for v in videos if q.lower() in v.get("title","").lower()]

    if not visible:
        st.warning("No lectures matched the search.")
        st.stop()

    selected_index = st.selectbox(
        "Select a lecture",
        range(len(visible)),
        format_func=lambda i: f"{i+1}. {visible[i].get('title','Untitled lecture')}",
        key="yt_lecture",
    )
    video = visible[selected_index]
    video_url = "https://www.youtube.com/watch?v=" + video["video_id"]

    st.markdown(
        f'<div class="info"><strong>{video.get("title","Untitled lecture")}</strong><br>'
        f'<span style="color:#887969">{video_url}</span></div>',
        unsafe_allow_html=True,
    )

    st.video(video_url)

    if st.button("📝 Get transcript", type="primary", use_container_width=True):
        with st.spinner("Getting transcript from TranscriptAPI…"):
            try:
                data = get_youtube_transcript(video_url, api_key)
                st.session_state["yt_result"] = {
                    "url": video_url,
                    "title": video.get("title",""),
                    "data": data,
                }
            except Exception as e:
                st.error(str(e))

    result = st.session_state.get("yt_result")
    if result and result["url"] == video_url:
        data = result["data"]
        st.divider()
        st.subheader("Transcript")

        items = data.get("transcript", [])
        plain = "\n\n".join(x.get("text","") for x in items)
        timed = "\n".join(
            f"[{fmt_time(x.get('start',0))}] {x.get('text','')}"
            for x in items
        )

        t1,t2 = st.tabs(["Readable","Timestamps"])
        with t1:
            st.text_area("Transcript", plain, height=600)
        with t2:
            st.text_area("Timestamped transcript", timed, height=600)

        d1,d2=st.columns(2)
        with d1:
            st.download_button(
                "⬇️ Download TXT", plain,
                file_name="youtube_lecture_transcript.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                "⬇️ Download timestamps", timed,
                file_name="youtube_lecture_transcript_timestamps.txt",
                mime="text/plain",
                use_container_width=True,
            )

st.markdown(
    '<div class="footer">Section 1 source: Audio ISKCON Desire Tree · '
    'Section 2 source: supplied YouTube playlist · '
    'YouTube transcripts: TranscriptAPI</div>',
    unsafe_allow_html=True,
)
