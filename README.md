# HH Radhanath Swami Lecture Transcriber

A free/local Streamlit app that uses ONLY the year-wise HH Radhanath Swami lecture archive at Audio ISKCON Desire Tree.

## What it does
1. Select a year.
2. Lists all MP3 recordings in that year, including nested folders.
3. Search within the year.
4. Select a lecture and play the original MP3.
5. Download the original MP3 and transcribe it locally with Whisper.
6. Show readable and timestamped transcripts.
7. Download the transcript as TXT.

YouTube is not used.

## Run it
Install Python 3.10+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

The first transcription downloads the selected Whisper model. After that, the model is cached by faster-whisper. Audio and transcript files are cached in `cache/`.

## Optional GPU
For NVIDIA CUDA:
```bash
set WHISPER_DEVICE=cuda
set WHISPER_COMPUTE_TYPE=float16
streamlit run app.py
```
On macOS/Linux use `export` instead of `set`.

## Notes
- `tiny`/`base` are fastest; `small`/`medium` are generally more accurate.
- A long lecture can take a while on CPU.
- The app only follows the exact Radhanath Swami year-wise archive supplied by the user.
