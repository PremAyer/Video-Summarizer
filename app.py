import streamlit as st
import os
import tempfile
import atexit
import shutil
import yt_dlp
import pandas as pd

from summary import (
    transcribe_audio,
    summarize_text,
    text_to_audio,
    detect_scenes_fast,
    select_key_scenes,
    create_video_summary_ffmpeg
)

# ------------------------ CONFIG ------------------------
st.set_page_config(
    page_title="AI Video Summarizer",
    layout="wide",
    page_icon="🎬"
)

@st.cache_resource
def get_temp_dir():
    temp_dir = tempfile.mkdtemp()
    atexit.register(cleanup_dir, temp_dir=temp_dir)
    return temp_dir

def cleanup_dir(temp_dir):
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

temp_dir = get_temp_dir()

def download_video_from_url(url, save_dir, cookies_path=None):
    try:
        st.info("Preparing to download audio...")
        file_path_template = os.path.join(save_dir, '%(title)s.%(ext)s')

        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": file_path_template,
            "quiet": True,
            "noplaylist": True,
        }

        if cookies_path:
            ydl_opts["cookies"] = cookies_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        st.success(f"Downloaded: {info.get('title')}")
        return filename

    except Exception as e:
        st.error(f"❌ Error downloading audio: {e}")
        return None


def download_full_video(url, save_dir, cookies_path=None):
    try:
        st.info("Downloading full video for scene summary...")
        file_template = os.path.join(save_dir, "%(title)s_full.%(ext)s")

        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": file_template,
            "quiet": True,
            "noplaylist": True,
        }

        if cookies_path:
            ydl_opts["cookies"] = cookies_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        st.success("Full video downloaded successfully.")
        return filename

    except Exception as e:
        st.error(f"❌ Error downloading full video: {e}")
        return None

# ------------------------ UI ------------------------

st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3208/3208759.png", width=120)
st.sidebar.title("🎥 Video Summarizer")
st.sidebar.markdown("**Powered by AI 🤖**")
st.sidebar.divider()

cookies_file = st.sidebar.file_uploader("Upload cookies.txt (optional)", type=["txt"])
cookies_path = None

if cookies_file:
    temp_cookie = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    temp_cookie.write(cookies_file.read())
    temp_cookie.flush()
    cookies_path = temp_cookie.name
    st.sidebar.success("Cookies loaded")

st.markdown("<h1 style='text-align:center;'>🎥 AI-Powered Video Summarization</h1>", unsafe_allow_html=True)
st.divider()

video_url = st.text_input("Paste a video URL...", help="Supports YouTube URLs only")

summary_choice = st.radio(
    "Pick one:",
    ("📝 Text Summary", "🎧 Audio Summary", "🎬 Video Summary"),
    horizontal=True
)

if video_url:
    if st.button(f"🚀 Generate {summary_choice}", use_container_width=True):
        progress = st.progress(0, "Starting...")
        with st.spinner("⚡ Processing... Please wait"):

            if "Text" in summary_choice or "Audio" in summary_choice:
                progress.progress(10, "Downloading audio...")
                temp_video_path = download_video_from_url(video_url, temp_dir, cookies_path)

                if temp_video_path is None:
                    st.stop()

                progress.progress(25, "Transcribing audio...")
                transcribed_text, detected_lang = transcribe_audio(temp_video_path, temp_dir)

                if not transcribed_text:
                    st.error("⚠ Could not transcribe audio")
                    st.stop()

                progress.progress(60, "Summarizing text...")
                summary_text = summarize_text(transcribed_text, source_lang=detected_lang)

                if not summary_text:
                    st.error("⚠ Summarization failed")
                    st.stop()

                if "Text" in summary_choice:
                    progress.progress(100, "Done 🎉")
                    st.success("Text Summary Ready!")
                    tab1, tab2 = st.tabs(["✨ Summary", "📜 Full Transcript"])
                    tab1.write(summary_text)
                    tab2.write(transcribed_text)

                else:
                    progress.progress(75, "Converting summary to speech...")
                    audio_path = os.path.join(temp_dir, "summary.mp3")

                    if text_to_audio(summary_text, audio_path):
                        progress.progress(100, "Done 🎉")
                        st.success("Audio Summary Ready!")
                        st.audio(audio_path)
                        with st.expander("Show Summary Text"):
                            st.write(summary_text)

            elif "Video" in summary_choice:
                progress.progress(10, "Downloading full video...")
                full_video_path = download_full_video(video_url, temp_dir, cookies_path)

                if full_video_path is None:
                    st.stop()

                progress.progr
