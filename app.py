import streamlit as st
import os
import tempfile
import atexit
import shutil
import yt_dlp
import pandas as pd

# Import functions from your custom modules
from summary import (
    transcribe_audio,
    summarize_text,
    text_to_audio,
    detect_scenes,
    select_key_scenes,
    create_video_summary
)

# --- Streamlit App Config ---
st.set_page_config(
    page_title="AI Video Summarizer",
    layout="wide",
    page_icon="🎬"
)

# --- SETUP TEMP DIRECTORY ---
@st.cache_resource
def get_temp_dir():
    temp_dir = tempfile.mkdtemp()
    atexit.register(cleanup_dir, temp_dir=temp_dir)
    return temp_dir

def cleanup_dir(temp_dir):
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

temp_dir = get_temp_dir()

# --- DOWNLOADER FUNCTION (FIXED FOR YOUTUBE) ---
def download_video_from_url(url, save_dir):
    try:
        st.info(f"Accessing link with yt-dlp...")
        file_path_template = os.path.join(save_dir, '%(title)s.%(ext)s')

        # 👇 THIS IS THE FIX: Cookies + User Agent
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': file_path_template,
            'quiet': True,
            'noplaylist': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            },
            'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        st.success(f"Download complete: {info.get('title')}")
        return filename
        
    except Exception as e:
        st.error(f"Error downloading with yt-dlp: {e}")
        return None

def download_full_video(url, save_dir):
    try:
        st.info("Downloading full video for visual summary...")
        file_template = os.path.join(save_dir, "%(title)s.%(ext)s")

        # 👇 THIS IS THE FIX: Cookies + User Agent
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': file_template,
            'quiet': True,
            'noplaylist': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            },
            'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',    
            
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        st.success("Full video downloaded.")
        return filename

    except Exception as e:
        st.error(f"Error downloading full video: {e}")
        return None

# --- UI LAYOUT ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3208/3208759.png", width=120)
    st.title("🎥 Video Summarizer")
    st.markdown("**Powered by AI 🤖**")
    st.divider()
    st.markdown("### 📌 Features")
    st.markdown("- 📝 Text Summaries\n- 🎧 Audio Summaries\n- 🎬 Condensed Video")

st.markdown("<h1 style='text-align: center;'>🎥 AI-Powered Video Summarization</h1>", unsafe_allow_html=True)

# --- MAIN APP LOGIC ---
video_url = st.text_input("Paste a video URL...", help="Currently supports YouTube URLs.")

if video_url:
    st.divider()
    st.subheader("⚙️ Choose Summary Type")
    summary_choice = st.radio("Pick one:", ("📝 Text Summary", "🎧 Audio Summary", "🎬 Video Summary"), horizontal=True)
    st.divider()

    if st.button(f"🚀 Generate {summary_choice}", use_container_width=True):
        progress = st.progress(0, "Starting...")
        
        # 1. Download Audio (Common Step)
        if not summary_choice.startswith("🎬"):
             progress.progress(10, "Downloading video audio...")
             temp_video_path = download_video_from_url(video_url, temp_dir)
             if temp_video_path is None: st.stop()

        # 2. Process Logic
        if summary_choice.startswith("📝"):
            progress.progress(25, "Transcribing...")
            transcribed_text, detected_lang = transcribe_audio(temp_video_path, temp_dir)
            if transcribed_text:
                progress.progress(75, "Summarizing...")
                summary_text = summarize_text(transcribed_text, source_lang=detected_lang)
                if summary_text:
                    progress.progress(100, "Done!")
                    st.success("Success!")
                    tab1, tab2 = st.tabs(["Final Summary", "Full Transcription"])
                    tab1.write(summary_text)
                    tab2.write(transcribed_text)

        elif summary_choice.startswith("🎧"):
            progress.progress(25, "Transcribing...")
            transcribed_text, detected_lang = transcribe_audio(temp_video_path, temp_dir)
            if transcribed_text:
                progress.progress(60, "Summarizing...")
                summary_text = summarize_text(transcribed_text, source_lang=detected_lang)
                if summary_text:
                    progress.progress(80, "Generating Audio...")
                    temp_audio_path = os.path.join(temp_dir, "summary.mp3")
                    if text_to_audio(summary_text, temp_audio_path):
                        progress.progress(100, "Done!")
                        st.audio(temp_audio_path)
                        with st.expander("Read Summary"): st.write(summary_text)

        elif summary_choice.startswith("🎬"):
            progress.progress(10, "Downloading full video...")
            full_video_path = download_full_video(video_url, temp_dir)
            if full_video_path:
                progress.progress(40, "Detecting scenes...")
                scenes = detect_scenes(full_video_path)
                if scenes:
                    key_scenes = select_key_scenes(scenes)
                    progress.progress(70, "Creating summary...")
                    summary_video_path = os.path.join(temp_dir, "video_summary.mp4")
                    final_path = create_video_summary(full_video_path, key_scenes, summary_video_path)
                    progress.progress(100, "Done!")
                    st.video(final_path)

# --- COMMENTS SECTION ---
st.divider()
st.write("## 💬 User Feedback")
COMMENTS_FILE = "comments.csv"
if not os.path.exists(COMMENTS_FILE):
    pd.DataFrame(columns=["Name", "Comment"]).to_csv(COMMENTS_FILE, index=False)

with st.form("comment_form"):
    name = st.text_input("Your Name")
    comment = st.text_area("Your Comment")
    if st.form_submit_button("Submit"):
        if name and comment:
            new_row = pd.DataFrame({"Name": [name], "Comment": [comment]})
            pd.read_csv(COMMENTS_FILE).append(new_row).to_csv(COMMENTS_FILE, index=False) # Simplified append
            st.success("Submitted!")
            st.rerun()

comments_df = pd.read_csv(COMMENTS_FILE)
for i, row in comments_df.iterrows():
    st.info(f"**{row['Name']}**: {row['Comment']}")

