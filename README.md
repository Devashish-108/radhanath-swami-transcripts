# Radhanath Swami Lecture Library

## Sections

### Section 1
Exact Audio ISKCON Desire Tree year-wise archive for HH Radhanath Swami.
Select year -> lecture -> original MP3 -> local Whisper transcription.

### Section 2
The supplied YouTube playlist is loaded through TranscriptAPI:
- playlist videos are shown in the API/playlist order
- select a lecture
- the selected YouTube URL is sent server-side to TranscriptAPI
- the transcript is displayed inside this Streamlit app

## Streamlit Secret required

Add this secret in Streamlit Cloud:

`TRANSCRIPT_API_KEY = "your_key_here"`

Never put the API key in `app.py` or commit it to GitHub.

TranscriptAPI documents:
- GET /api/v2/youtube/playlist/videos
- GET /api/v2/youtube/transcript

The API key is deliberately read from Streamlit Secrets.
