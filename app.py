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

st.set_page_config(
    page_title="AI Video Summarizer",
    layout="wide",
    page_icon="🎬"
)

@st.cache_resource
def get_temp_dir():
    temp_dir = tempfile.mkdtemp()
    print(f"Created temp directory: {temp_dir}")
    atexit.register(cleanup_dir, temp_dir=temp_dir)
    return temp_dir

def cleanup_dir(temp_dir):
    if os.path.exists(temp_dir):
        print(f"Cleaning up temp directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)

temp_dir = get_temp_dir()

def download_video_from_url(url, save_dir, cookies_path=None):
    try:
        st.info(f"Accessing link with yt-dlp...")

        file_path_template = os.path.join(save_dir, '%(title)s.%(ext)s')

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': file_path_template,
            'quiet': True,
            'noplaylist': True,
        }

        if cookies_path:
            ydl_opts["cookies"] = cookies_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        st.success(f"Download complete: {info.get('title')}")
        return filename

    except Exception as e:
        st.error(f"Error downloading with yt-dlp: {e}")
        return None


def download_full_video(url, save_dir, cookies_path=None):
    try:
        st.info("Downloading full video for visual summary...")
        file_template = os.path.join(save_dir, "%(title)s.%(ext)s")

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': file_template,
            'quiet': True,
            'noplaylist': True
        }

        if cookies_path:
            ydl_opts["cookies"] = cookies_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        st.success("Full video downloaded.")
        return filename

    except Exception as e:
        st.error(f"Error downloading full video: {e}")
        return None


# ------------- UI STARTS HERE -------------

st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3208/3208759.png", width=120)
st.sidebar.title("🎥 Video Summarizer")
st.sidebar.markdown("**Powered by AI 🤖**")
st.sidebar.divider()

cookies_file = st.sidebar.file_uploader("Upload cookies.txt (optional)", type=["txt"],
                                        help="Required only for restricted/protected YouTube videos")

cookies_path = None
if cookies_file:
    temp_cookie = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    temp_cookie.write(cookies_file.read())
    temp_cookie.flush()
    cookies_path = temp_cookie.name
    st.sidebar.success("Cookies loaded successfully")


st.markdown("<h1 style='text-align: center;'>🎥 AI-Powered Video Summarization</h1>", unsafe_allow_html=True)
st.divider()

video_url = st.text_input("Paste a video URL...", help="Supports YouTube URLs.")

if video_url:
    st.divider()
    summary_choice = st.radio(
        "Pick one:", ("📝 Text Summary", "🎧 Audio Summary", "🎬 Video Summary"),
        horizontal=True, key="my_radio"
    )
    st.divider()

    if st.button(f"🚀 Generate {summary_choice}", use_container_width=True):
        progress = st.progress(0, "Starting...")
        with st.spinner("⚡ Working hard... This may take a few minutes ⏳"):

            progress.progress(10, "Downloading video audio...")
            temp_video_path = download_video_from_url(video_url, temp_dir, cookies_path)

            if temp_video_path is None:
                st.stop()

            st.divider()

            if summary_choice.startswith("📝"):
                progress.progress(25, "1/2 - Transcribing audio...")
                transcribed_text, detected_lang = transcribe_audio(temp_video_path, temp_dir)

                if transcribed_text:
                    progress.progress(75, "3/3 - Processing summary...")
                    summary_text = summarize_text(transcribed_text, source_lang=detected_lang)

                    if summary_text:
                        progress.progress(100, "Done!")
                        st.success("🎉 Summary Generated Successfully!")
                        tab1, tab2 = st.tabs(["✨ Final Summary", "📜 Full Transcription"])
                        with tab1: st.write(summary_text)
                        with tab2: st.write(transcribed_text)

            elif summary_choice.startswith("🎧"):
                progress.progress(25, "1/3 - Transcribing audio...")
                transcribed_text, detected_lang = transcribe_audio(temp_video_path, temp_dir)

                if transcribed_text:
                    progress.progress(60, "2/3 - Processing summary...")
                    summary_text = summarize_text(transcribed_text, source_lang=detected_lang)

                    if summary_text:
                        progress.progress(80, "3/3 - Converting summary to audio...")
                        temp_audio_path = os.path.join(temp_dir, "summary.mp3")

                        if text_to_audio(summary_text, temp_audio_path):
                            progress.progress(100, "Done!")
                            st.success("Audio Summary Generated Successfully! 🎉")
                            st.audio(temp_audio_path)
                            with st.expander("Show Summary Text"):
                                st.write(summary_text)

            elif summary_choice.startswith("🎬"):
                progress.progress(10, "Downloading full video...")
                full_video_path = download_full_video(video_url, temp_dir, cookies_path)

                if full_video_path is None:
                    st.error("🚨 Could not download full video.")
                    st.stop()

                progress.progress(40, "Detecting scenes...")
                scenes = detect_scenes_fast(full_video_path)

                if not scenes:
                    st.error("⚠ No scenes detected. Try increasing threshold.")
                    st.stop()

                progress.progress(60, "Selecting best scenes...")
                key_scenes = select_key_scenes(scenes, max_scenes=5)

                progress.progress(80, "Creating summary video...")
                summary_video_path = os.path.join(temp_dir, "video_summary.mp4")
                final_path = create_video_summary_ffmpeg(full_video_path, key_scenes, summary_video_path)

                progress.progress(100, "Done 🎉")
                st.success("🎬 Video Summary Created Successfully!")
                st.video(final_path)
