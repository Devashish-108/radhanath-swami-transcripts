import os, re, json, hashlib, urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import streamlit as st

BASE = "https://audio.iskcondesiretree.com"
ROOT_PATH = "/02_-_ISKCON_Swamis/ISKCON_Swamis_-_R_to_Y/His_Holiness_Radhanath_Swami/Lectures/00_-_Year_wise"

CACHE = Path("cache")
AUDIO_CACHE = CACHE / "audio"
TEXT_CACHE = CACHE / "transcripts"
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
TEXT_CACHE.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Radhanath-Swami-Lecture-Transcriber)",
    "Referer": BASE + "/",
}

def make_page_url(path):
    # The archive accepts the folder path in the f query parameter.
    return BASE + "/index.php?" + urllib.parse.urlencode({"q": "f", "f": path})

@st.cache_data(ttl=3600, show_spinner=False)
def get_page(path):
    r = requests.get(make_page_url(path), headers=HEADERS, timeout=45)
    r.raise_for_status()
    return r.text

def normalise_target(target):
    target = urllib.parse.unquote(target or "")
    if not target.startswith("/"):
        target = "/" + target
    return target

def parse_listing(path):
    """Read folders and MP3 files from the actual Audio ISKCON Desire Tree HTML.

    Important: the site commonly writes links as ?q=f&f=... rather than
    ?f=..., so we parse the query parameters instead of matching a literal
    string such as 'index.php?f='.
    """
    soup = BeautifulSoup(get_page(path), "html.parser")
    items = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        label = " ".join(a.get_text(" ", strip=True).split())
        if not href:
            continue

        absolute = urllib.parse.urljoin(BASE + "/", href)
        parsed = urllib.parse.urlparse(absolute)
        qs = urllib.parse.parse_qs(parsed.query)

        # Folder/file links on this archive use an f= query parameter.
        targets = qs.get("f", [])
        if targets:
            target = normalise_target(targets[0])
            if target.startswith(ROOT_PATH + "/"):
                if target.lower().endswith(".mp3"):
                    items.append(("file", label or Path(target).name, BASE + target))
                else:
                    items.append(("folder", label or Path(target).name, target))
                continue

        # Some pages can expose a direct MP3 URL.
        path_part = urllib.parse.unquote(parsed.path)
        if ".mp3" in path_part.lower():
            items.append(("file", label or Path(path_part).name, absolute))

    # Remove duplicates while preserving order.
    out, seen = [], set()
    for item in items:
        key = item[0] + "|" + item[2]
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out

@st.cache_data(ttl=3600, show_spinner=False)
def get_years():
    return [
        (label, target)
        for kind, label, target in parse_listing(ROOT_PATH)
        if kind == "folder"
    ]

@st.cache_data(ttl=3600, show_spinner=False)
def get_lectures_recursive(year_path):
    results = []
    visited = set()

    def walk(path):
        if path in visited:
            return
        visited.add(path)

        for kind, label, target in parse_listing(path):
            if kind == "file":
                results.append({"title": label, "url": target})
            else:
                walk(target)

    walk(year_path)
    return results

def safe_id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:24]

def download_audio(url, destination):
    if destination.exists() and destination.stat().st_size > 0:
        return

    with requests.get(
        url,
        headers={**HEADERS, "Referer": make_page_url(ROOT_PATH)},
        stream=True,
        timeout=120,
    ) as r:
        r.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

def transcribe(audio_path, model_name, language=None):
    from faster_whisper import WhisperModel

    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv(
        "WHISPER_COMPUTE_TYPE",
        "int8" if device == "cpu" else "float16"
    )

    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
    )

    options = {
        "beam_size": 5,
        "vad_filter": True,
    }
    if language:
        options["language"] = language

    segments, info = model.transcribe(str(audio_path), **options)

    data = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            data.append({
                "start": float(segment.start),
                "end": float(segment.end),
                "text": text,
            })

    return data, info.language

def format_time(seconds):
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

st.set_page_config(
    page_title="Radhanath Swami Lecture Transcripts",
    page_icon="🕉️",
    layout="wide",
)

st.title("🕉️ HH Radhanath Swami — Lecture Transcriber")
st.caption(
    "Uses only the year-wise HH Radhanath Swami lecture archive "
    "at Audio ISKCON Desire Tree. YouTube is not used."
)

with st.sidebar:
    st.header("Transcription settings")
    model = st.selectbox(
        "Whisper model",
        ["tiny", "base", "small", "medium"],
        index=1,
        help="Larger models can be more accurate but require more memory/time."
    )
    language_name = st.selectbox(
        "Language",
        ["Auto-detect", "English", "Hindi", "Marathi"],
        index=0,
    )
    language = {
        "Auto-detect": None,
        "English": "en",
        "Hindi": "hi",
        "Marathi": "mr",
    }[language_name]

try:
    years = get_years()
except Exception as exc:
    st.error(f"Could not read the Audio ISKCON Desire Tree archive: {exc}")
    st.stop()

if not years:
    st.error(
        "The archive was reached, but no year folders were detected. "
        "Please refresh the app. If the problem persists, the source website "
        "may have changed its page format."
    )
    st.stop()

# Prefer actual numeric year folders first.
years.sort(key=lambda x: (
    0 if re.search(r"\b(?:19|20)\d{2}\b", x[0]) else 1,
    x[0].lower()
))

year_labels = [label for label, _ in years]
selected_year = st.selectbox("1. Select a year", year_labels)
year_path = dict(years)[selected_year]

with st.spinner(f"Loading recordings for {selected_year}…"):
    lectures = get_lectures_recursive(year_path)

st.write(f"**{len(lectures)} recordings found**")

search = st.text_input(
    "2. Search this year",
    placeholder="Search by lecture title, date, place, topic…"
)

if search.strip():
    query = search.lower()
    lectures = [x for x in lectures if query in x["title"].lower()]

if not lectures:
    st.warning("No recordings matched your search.")
    st.stop()

lectures.sort(key=lambda x: x["title"].lower())

selected_title = st.selectbox(
    "3. Select a lecture",
    [x["title"] for x in lectures],
)
lecture = next(x for x in lectures if x["title"] == selected_title)

st.markdown(f"**Selected:** {lecture['title']}")
st.audio(lecture["url"])

if st.button("📝 Generate full transcript", type="primary"):
    sid = safe_id(lecture["url"])
    audio_path = AUDIO_CACHE / f"{sid}.mp3"

    try:
        with st.spinner("Downloading the original MP3…"):
            download_audio(lecture["url"], audio_path)

        with st.spinner(
            f"Transcribing locally with Whisper ({model})… "
            "A long lecture can take some time."
        ):
            segments, detected_language = transcribe(
                audio_path,
                model,
                language,
            )

        data = {
            "title": lecture["title"],
            "url": lecture["url"],
            "language": detected_language,
            "segments": segments,
        }
        st.session_state["transcript"] = data

    except Exception as exc:
        st.error(f"Transcription failed: {exc}")
        st.stop()

data = st.session_state.get("transcript")

if data and data["url"] == lecture["url"]:
    st.divider()
    st.subheader("Transcript")
    st.caption(f"Detected language: {data['language']}")

    plain = "\n\n".join(s["text"] for s in data["segments"])
    timestamped = "\n".join(
        f"[{format_time(s['start'])}] {s['text']}"
        for s in data["segments"]
    )

    tab1, tab2 = st.tabs(["Readable transcript", "Timestamped transcript"])

    with tab1:
        st.text_area("Transcript", plain, height=600)

    with tab2:
        st.text_area("Transcript with timestamps", timestamped, height=600)

    st.download_button(
        "⬇️ Download TXT",
        plain,
        file_name="radhanath_swami_transcript.txt",
        mime="text/plain",
    )

    st.download_button(
        "⬇️ Download timestamped TXT",
        timestamped,
        file_name="radhanath_swami_transcript_timestamps.txt",
        mime="text/plain",
    )

    st.markdown(
        f"[Open the original recording on Audio ISKCON Desire Tree]({data['url']})"
    )
