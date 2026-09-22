# Radhanath Swami Lecture Library

Two-section Streamlit website:

1. Audio ISKCON Desire Tree year-wise Radhanath Swami archive
   - Year -> lecture -> original MP3 -> Whisper transcript
2. Supplied YouTube playlist
   - Playlist order -> lecture -> YouTube video -> YouTubeToTranscript link

Deploy on Streamlit Community Cloud using `app.py`.

Note: Section 2 uses the public YouTube playlist page and provides the
selected video URL to the YouTubeToTranscript workflow. It does not download
YouTube audio or run Whisper on those videos.
