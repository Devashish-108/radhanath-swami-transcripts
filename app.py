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
# Configuration
# ============================================================

AUDIO_BASE = "https://audio.iskcondesiretree.com"
AUDIO_ROOT = (
    "/02_-_ISKCON_Swamis/ISKCON_Swamis_-_R_to_Y/"
    "His_Holiness_Radhanath_Swami/Lectures/00_-_Year_wise"
)

YOUTUBE_PLAYLIST_ID = "PLvKq1ZnGL6pw7xd_BD76Bvd2xJih6AzQm"
YOUTUBE_PLAYLIST_URL = (
    "https://www.youtube.com/playlist?list=" + YOUTUBE_PLAYLIST_ID
)
YTT_URL = "https://youtubetotranscript.com/transcript"

CACHE = Path("cache")
AUDIO_CACHE = CACHE / "audio"
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Radhanath-Swami-Lecture-Library)",
    "Referer": AUDIO_BASE + "/",
}

# ============================================================
# Styling
# ============================================================

st.set_page_config(
    page_title="Radhanath Swami Lecture Library",
    page_icon="🕉️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(243, 180, 75, .12), transparent 30%),
            radial-gradient(circle at 95% 10%, rgba(112, 84, 46, .10), transparent 28%),
            #fbfaf7;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    .hero {
        padding: 2.2rem 2rem;
        border-radius: 24px;
        background: linear-gradient(135deg, #fff8e8 0%, #f7eee0 55%, #eee3d3 100%);
        border: 1px solid #eadbc4;
        box-shadow: 0 12px 35px rgba(80, 55, 25, .08);
        margin-bottom: 1.4rem;
    }

    .hero-kicker {
        color: #9a6b28;
        font-size: .85rem;
        font-weight: 800;
        letter-spacing: .12em;
        text-transform: uppercase;
        margin-bottom: .45rem;
    }

    .hero-title {
        color: #3f2c1c;
        font-size: 2.45rem;
        line-height: 1.08;
        font-weight: 800;
        margin: 0;
    }

    .hero-subtitle {
        color: #705e4c;
        font-size: 1.05rem;
        margin-top: .75rem;
        max-width: 800px;
        line-height: 1.6;
    }

    .section-card {
        background: white;
        border: 1px solid #eadfd2;
        border-radius: 20px;
        padding: 1.25rem 1.35rem;
        box-shadow: 0 8px 24px rgba(70, 50, 30, .055);
        margin-bottom: 1rem;
    }

    .section-title {
        color: #453323;
        font-size: 1.35rem;
        font-weight: 800;
        margin-bottom: .2rem;
    }

    .section-caption {
        color: #766756;
        font-size: .95rem;
        margin-bottom: .8rem;
    }

    .badge {
        display: inline-block;
        background: #f6ead6;
        color: #8a5e23;
        padding: .28rem .65rem;
        border-radius: 999px;
        font-size: .78rem;
        font-weight: 700;
        margin-right: .35rem;
    }

    .info-box {
        padding: .9rem 1rem;
        border-radius: 14px;
        background: #faf6ef;
        border: 1px solid #eee2d2;
        color: #665748;
        font-size: .92rem;
        line-height: 1.55;
    }

    .transcript-box {
        padding: 1.25rem;
        border-radius: 16px;
        background: #fff;
        border: 1px solid #e8ded1;
        line-height: 1.75;
        color: #3f3a35;
        white-space: pre-wrap;
    }

    div[data-testid="stButton"] button {
        border-radius: 12px;
        font-weight: 700;
    }

    .footer-note {
        text-align: center;
        color: #887969;
        font-size: .82rem;
        padding-top: 2rem;
    }

    @media (max-width: 700px) {
        .hero-title { font-size: 1.85rem; }
        .hero { padding: 1.5rem; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Helpers: Audio ISKCON Desire Tree
# ============================================================

def audio_page_url(path):
    return AUDIO_BASE + "/index.php?" + urllib.parse.urlencode({
        "q": "f",
        "f": path,
    })

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_audio_page(path):
    response = requests.get(
        audio_page_url(path),
        headers=HEADERS,
        timeout=45,
    )
    response.raise_for_status()
    return response.text

def normalize_path(value):
    value = urllib.parse.unquote(value or "")
    if not value.startswith("/"):
        value = "/" + value
    return value

def parse_audio_listing(path):
    soup = BeautifulSoup(fetch_audio_page(path), "html.parser")
    results = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        label = " ".join(link.get_text(" ", strip=True).split())
        absolute = urllib.parse.urljoin(AUDIO_BASE + "/", href)
        parsed = urllib.parse.urlparse(absolute)
        query = urllib.parse.parse_qs(parsed.query)

        targets = query.get("f", [])
        if targets:
            target = normalize_path(targets[0])

            if target.startswith(AUDIO_ROOT + "/"):
                if target.lower().endswith(".mp3"):
                    results.append((
                        "file",
                        label or Path(target).name,
                        AUDIO_BASE + target
                    ))
                else:
                    results.append((
                        "folder",
                        label or Path(target).name,
                        target
                    ))
                continue

        path_part = urllib.parse.unquote(parsed.path)
        if ".mp3" in path_part.lower():
            results.append((
                "file",
                label or Path(path_part).name,
                absolute
            ))

    seen = set()
    unique = []
    for item in results:
        key = item[0] + "|" + item[2]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

@st.cache_data(ttl=3600, show_spinner=False)
def get_audio_years():
    return [
        (label, target)
        for kind, label, target in parse_audio_listing(AUDIO_ROOT)
        if kind == "folder"
    ]

@st.cache_data(ttl=3600, show_spinner=False)
def get_year_lectures(year_path):
    found = []
    visited = set()

    def walk(path):
        if path in visited:
            return
        visited.add(path)

        for kind, label, target in parse_audio_listing(path):
            if kind == "file":
                found.append({
                    "title": label,
                    "url": target,
                })
            else:
                walk(target)

    walk(year_path)
    return found

def safe_filename(url):
    return hashlib.sha256(url.encode()).hexdigest()[:24] + ".mp3"

def download_audio(url, destination):
    if destination.exists() and destination.stat().st_size:
        return

    with requests.get(
        url,
        headers={**HEADERS, "Referer": audio_page_url(AUDIO_ROOT)},
        stream=True,
        timeout=180,
    ) as response:
        response.raise_for_status()
        with open(destination, "wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    output.write(chunk)

def transcribe_audio(audio_path, model_name, language=None):
    from faster_whisper import WhisperModel

    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute = os.getenv(
        "WHISPER_COMPUTE_TYPE",
        "int8" if device == "cpu" else "float16"
    )

    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute,
    )

    options = {
        "beam_size": 5,
        "vad_filter": True,
    }

    if language:
        options["language"] = language

    segments, info = model.transcribe(
        str(audio_path),
        **options,
    )

    output = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            output.append({
                "start": float(segment.start),
                "end": float(segment.end),
                "text": text,
            })

    return output, info.language

def timestamp(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# ============================================================
# Helpers: YouTube playlist
# ============================================================

@st.cache_data(ttl=1800, show_spinner=False)
def get_youtube_playlist_videos(playlist_id):
    """Best-effort playlist reader using YouTube's public watch page.

    This deliberately does not use YouTube's private/internal API.
    If YouTube changes the page format, the user can still use the
    playlist URL directly.
    """
    url = "https://www.youtube.com/playlist?list=" + urllib.parse.quote(
        playlist_id
    )

    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=45,
    )
    response.raise_for_status()
    html = response.text

    # YouTube embeds initial data in ytInitialData.
    match = re.search(
        r'var ytInitialData\s*=\s*(\{.*?\});</script>',
        html,
        flags=re.S,
    )

    if not match:
        # Some page versions use ytInitialData = JSON;
        match = re.search(
            r'ytInitialData"\s*:\s*(\{.*?\})\s*,\s*"',
            html,
            flags=re.S,
        )

    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except Exception:
        return []

    videos = []
    seen = set()

    def walk(obj):
        if isinstance(obj, dict):
            renderer = obj.get("playlistVideoRenderer")
            if renderer:
                video_id = renderer.get("videoId")
                title_runs = renderer.get("title", {}).get("runs", [])
                title = "".join(
                    run.get("text", "")
                    for run in title_runs
                    if isinstance(run, dict)
                ).strip()

                if video_id and video_id not in seen:
                    seen.add(video_id)
                    videos.append({
                        "title": title or video_id,
                        "video_id": video_id,
                        "url": "https://www.youtube.com/watch?v=" + video_id,
                    })

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(data)
    return videos

# ============================================================
# UI
# ============================================================

st.markdown("""
<div class="hero">
    <div class="hero-kicker">Lecture Library</div>
    <div class="hero-title">🕉️ HH Radhanath Swami</div>
    <div class="hero-subtitle">
        Explore the year-wise audio archive and the selected YouTube lecture
        collection — then read or generate transcripts in one place.
    </div>
</div>
""", unsafe_allow_html=True)

section1, section2 = st.tabs([
    "🕉️ Audio Archive",
    "▶️ YouTube Lectures",
])

# ------------------------------------------------------------
# Section 1
# ------------------------------------------------------------

with section1:
    st.markdown("""
    <div class="section-card">
        <div class="section-title">Audio ISKCON Desire Tree</div>
        <div class="section-caption">
            The original year-wise archive of HH Radhanath Swami's recordings.
        </div>
        <span class="badge">Original MP3</span>
        <span class="badge">Year-wise</span>
        <span class="badge">Whisper transcription</span>
    </div>
    """, unsafe_allow_html=True)

    try:
        years = get_audio_years()
    except Exception as exc:
        st.error(f"Could not read the audio archive: {exc}")
        years = []

    if years:
        # Numeric years first, preserving sensible chronology.
        years.sort(key=lambda x: (
            0 if re.search(r"\b(?:19|20)\d{2}\b", x[0]) else 1,
            x[0].lower()
        ))

        year_labels = [x[0] for x in years]
        selected_year = st.selectbox(
            "Choose a year",
            year_labels,
            key="audio_year",
        )
        year_path = dict(years)[selected_year]

        with st.spinner("Loading lectures…"):
            lectures = get_year_lectures(year_path)

        st.caption(f"{len(lectures)} recordings found in {selected_year}")

        search = st.text_input(
            "Search this year's lectures",
            placeholder="Search by title, date, place or topic…",
            key="audio_search",
        )

        if search.strip():
            q = search.lower()
            lectures = [
                x for x in lectures
                if q in x["title"].lower()
            ]

        if lectures:
            lectures.sort(key=lambda x: x["title"].lower())

            selected_title = st.selectbox(
                "Choose a lecture",
                [x["title"] for x in lectures],
                key="audio_lecture",
            )
            lecture = next(
                x for x in lectures
                if x["title"] == selected_title
            )

            st.markdown(
                f'<div class="info-box"><strong>Selected lecture:</strong> '
                f'{lecture["title"]}</div>',
                unsafe_allow_html=True,
            )

            st.audio(lecture["url"])

            col1, col2 = st.columns([1, 1])
            with col1:
                transcribe_clicked = st.button(
                    "📝 Generate transcript",
                    type="primary",
                    use_container_width=True,
                    key="audio_transcribe",
                )
            with col2:
                st.link_button(
                    "🔗 Open original recording",
                    lecture["url"],
                    use_container_width=True,
                )

            if transcribe_clicked:
                model = st.session_state.get("audio_model", "base")

                sid = hashlib.sha256(
                    lecture["url"].encode()
                ).hexdigest()[:24]
                audio_path = AUDIO_CACHE / f"{sid}.mp3"

                try:
                    with st.spinner("Downloading the original MP3…"):
                        download_audio(
                            lecture["url"],
                            audio_path,
                        )

                    with st.spinner(
                        f"Transcribing with Whisper ({model})…"
                    ):
                        segments, detected = transcribe_audio(
                            audio_path,
                            model,
                            st.session_state.get(
                                "audio_language"
                            ),
                        )

                    st.session_state["audio_transcript"] = {
                        "url": lecture["url"],
                        "title": lecture["title"],
                        "language": detected,
                        "segments": segments,
                    }

                except Exception as exc:
                    st.error(f"Transcription failed: {exc}")

            transcript = st.session_state.get("audio_transcript")

            if transcript and transcript["url"] == lecture["url"]:
                st.divider()
                st.subheader("Transcript")
                st.caption(
                    f"Detected language: {transcript['language']}"
                )

                plain = "\n\n".join(
                    x["text"]
                    for x in transcript["segments"]
                )
                timed = "\n".join(
                    f"[{timestamp(x['start'])}] {x['text']}"
                    for x in transcript["segments"]
                )

                t1, t2 = st.tabs([
                    "Readable",
                    "With timestamps",
                ])

                with t1:
                    st.text_area(
                        "Transcript",
                        plain,
                        height=550,
                        key="audio_plain",
                    )

                with t2:
                    st.text_area(
                        "Timestamped transcript",
                        timed,
                        height=550,
                        key="audio_timed",
                    )

                c1, c2 = st.columns(2)
                with c1:
                    st.download_button(
                        "⬇️ Download TXT",
                        plain,
                        file_name="radhanath_swami_transcript.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )
                with c2:
                    st.download_button(
                        "⬇️ Download timestamped TXT",
                        timed,
                        file_name="radhanath_swami_transcript_timestamps.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

    else:
        st.warning(
            "No year folders were detected. Refresh the app and try again."
        )

# ------------------------------------------------------------
# Section 2
# ------------------------------------------------------------

with section2:
    st.markdown("""
    <div class="section-card">
        <div class="section-title">YouTube Lecture Collection</div>
        <div class="section-caption">
            Lectures from the supplied YouTube playlist, kept in playlist order.
        </div>
        <span class="badge">YouTube playlist</span>
        <span class="badge">Original order</span>
        <span class="badge">YouTube transcript workflow</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f'<div class="info-box">Playlist: '
        f'<a href="{YOUTUBE_PLAYLIST_URL}" target="_blank">'
        f'{YOUTUBE_PLAYLIST_URL}</a></div>',
        unsafe_allow_html=True,
    )

    st.write("")

    with st.spinner("Loading playlist lectures…"):
        try:
            youtube_videos = get_youtube_playlist_videos(
                YOUTUBE_PLAYLIST_ID
            )
        except Exception as exc:
            youtube_videos = []
            st.warning(
                f"Could not automatically read the playlist right now: {exc}"
            )

    if youtube_videos:
        st.success(
            f"{len(youtube_videos)} lectures loaded in playlist order."
        )

        yt_search = st.text_input(
            "Search playlist",
            placeholder="Search lecture titles…",
            key="yt_search",
        )

        visible = youtube_videos
        if yt_search.strip():
            q = yt_search.lower()
            visible = [
                x for x in youtube_videos
                if q in x["title"].lower()
            ]

        selected = st.selectbox(
            "Choose a YouTube lecture",
            range(len(visible)),
            format_func=lambda i: visible[i]["title"],
            key="yt_selected",
        )

        video = visible[selected]

        st.markdown(
            f'<div class="info-box"><strong>Selected lecture:</strong> '
            f'{video["title"]}</div>',
            unsafe_allow_html=True,
        )

        st.video(video["url"])

        st.markdown(
            """
            <div class="info-box">
            <strong>Transcript method:</strong>
            This section uses the selected YouTube video URL with the
            YouTube transcript workflow, rather than downloading the video
            and running Whisper.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.link_button(
            "📝 Open this lecture in YouTubeToTranscript",
            YTT_URL + "?url=" + urllib.parse.quote(
                video["url"],
                safe=""
            ),
            use_container_width=True,
        )

        st.caption(
            "If the transcript service changes its URL format or requires "
            "manual submission, paste the selected YouTube URL into its "
            "transcript box."
        )

    else:
        st.warning(
            "The playlist could not be read automatically from YouTube. "
            "The playlist itself is still available below."
        )
        st.link_button(
            "▶️ Open the YouTube playlist",
            YOUTUBE_PLAYLIST_URL,
            use_container_width=True,
        )
        st.info(
            "This fallback is intentional: the app does not invent lecture "
            "titles when YouTube does not expose the playlist data."
        )

# ------------------------------------------------------------
# Sidebar controls
# ------------------------------------------------------------

with st.sidebar:
    st.markdown("### ⚙️ Transcription settings")
    st.selectbox(
        "Whisper model",
        ["tiny", "base", "small", "medium"],
        index=1,
        key="audio_model",
    )
    st.selectbox(
        "Audio language",
        ["Auto-detect", "English", "Hindi", "Marathi"],
        index=0,
        key="audio_language_name",
    )

    language_name = st.session_state.get(
        "audio_language_name",
        "Auto-detect",
    )
    st.session_state["audio_language"] = {
        "Auto-detect": None,
        "English": "en",
        "Hindi": "hi",
        "Marathi": "mr",
    }[language_name]

st.markdown("""
<div class="footer-note">
Source for Section 1: Audio ISKCON Desire Tree •
Section 2: supplied YouTube playlist
</div>
""", unsafe_allow_html=True)
