import streamlit as st
import os
from faster_whisper import WhisperModel
import torch 
from transformers import pipeline 
import sys 
from elevenlabs import save
from groq import Groq
from elevenlabs.client import ElevenLabs
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image
import numpy as np
from dotenv import load_dotenv

os.environ["STREAMLIT_WATCHDOG"] = "false"

load_dotenv()
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
except (FileNotFoundError, KeyError):
    groq_api_key = os.getenv("GROQ_API_KEY")

# Stop the app if the key is still missing
if not groq_api_key:
    st.error("🚨 Groq API Key not found! Please check your secrets.toml or .env file.")
    st.stop()

# Initialize the client with the found key
client = Groq(api_key=groq_api_key)

# --- THIS FUNCTION IS MODIFIED ---
def transcribe_audio(audio_path, temp_dir):
    """
    Transcribes a given audio file using faster-whisper.
    """
    model = None 
    try:

        download_path = os.path.join(os.getcwd(), "models_cache")
        os.makedirs(download_path, exist_ok=True)
        model = WhisperModel("medium", device="cuda", compute_type="float16",download_root=download_path)
        
        print(f"✅ Transcribing file: {audio_path}")
        sys.stdout.flush()

        segments, info = model.transcribe(
            audio_path,
            word_timestamps=False
        )
        
        result_text = " ".join([segment.text for segment in segments])

        print(f"✅ Transcription complete. Detected language: {info.language}")
        sys.stdout.flush()
        
        transcript = f" \nTHE TRANSCRIPT IS: \n\n{result_text.strip()}"
        
    except Exception as e:
        print(f"⚠️ Error during transcription: {e}")
        sys.stdout.flush()
        return None, None
    finally:
        # --- FIX: REMOVED torch.cuda.empty_cache() ---
        if model:
            print("✅ transcribe_audio: Cleaning up Whisper model...") # <-- THIS IS THE NEW PRINT
            sys.stdout.flush()
            del model
            print("✅ transcribe_audio: Whisper model cleanup complete.")
            sys.stdout.flush()
            
    return transcript, info.language


# --- THIS IS THE UPDATED FUNCTION ---

def translate_text(text, source_lang):
    """
    Translates text from a source language to English using m2m100_418M
    FORCING CPU to avoid VRAM conflicts with Whisper.
    """
    
    clean_text = text.replace("THE TRANSCRIPT IS:", "").strip()
    
    print(f"✅ translate_text: Starting translation from '{source_lang}' to 'en'...")
    st.info(f"1b/3 - Translating text from '{source_lang}' to 'en'...")
    
    # --- THIS IS THE FIX ---
    # We are forcing 'cpu' to avoid VRAM conflicts.
    device = "cpu"
    print(f"✅ translate_text: Forcing device '{device}' to ensure stability.")
    st.warning("Translation is running on CPU to prevent crashes. This step may be slow...")
    # --- END OF FIX ---

    sys.stdout.flush()
    
    translator_pipeline = None
    model_name = "facebook/m2m100_418M"

    try:
        print(f"✅ translate_text: Attempting to load model '{model_name}' onto device '{device}'...")
        sys.stdout.flush()
        
        translator_pipeline = pipeline(
            "translation",
            model=model_name,
            device=device  # This will now correctly be "cpu"
        )
        
        print(f"✅ translate_text: Model loaded successfully onto '{device}'.")
        sys.stdout.flush()

    except Exception as e:
        print(f"⚠️ translate_text: CRITICAL ERROR loading model: {e}")
        sys.stdout.flush()
        st.error(f"Failed to load translation model: {e}")
        return None

    # --- IF MODEL LOADED, PROCEED ---
    try:
        max_chunk_size = 400 
        words = clean_text.split()
        chunks = [" ".join(words[i:i+max_chunk_size]) for i in range(0, len(words), max_chunk_size)]
        
        translated_chunks = []
        print(f"✅ translate_text: Starting translation of {len(chunks)} chunks...")
        sys.stdout.flush()
        
        for i, chunk in enumerate(chunks, 1):
            print(f"Translating chunk {i}/{len(chunks)}...")
            sys.stdout.flush()
            
            result = translator_pipeline(chunk, src_lang=source_lang, tgt_lang="en")
            
            translated_chunks.append(result[0]['translation_text'])
        
        translated_text = " ".join(translated_chunks)
        print("✅ Translation complete.")
        sys.stdout.flush()
        return translated_text

    except Exception as e:
        print(f"⚠️ translate_text: Error *during* translation: {e}")
        sys.stdout.flush()
        st.error(f"Error during translation process: {e}")
        return None
    finally:
        # --- Cleanup ---
        if translator_pipeline:
            print("✅ translate_text: Cleaning up translation model...")
            sys.stdout.flush()
            del translator_pipeline
            print("✅ translate_text: Cleanup complete.")
            sys.stdout.flush()


def summarize_text(text, source_lang="en"):
    """
    Summarizes text. If source_lang is not 'en', it translates first.
    """

    print(f"✅ summarize_text: Received text. Language is '{source_lang}'.")
    sys.stdout.flush()
    text_to_summarize = ""

    # ------- LANGUAGE HANDLING -------
    if source_lang != "en" and source_lang is not None:
        try:
            print("✅ summarize_text: Language is not 'en'. Calling translate_text...")
            sys.stdout.flush()
            translated_text = translate_text(text, source_lang)
            if translated_text is None:
                return None
            text_to_summarize = translated_text
            st.info("2/3 - Summarizing translated text...")
        except Exception as e:
            st.error(f"Translation failed: {e}")
            return None
    else:
        print("✅ summarize_text: Language is 'en'. Skipping translation...")
        sys.stdout.flush()
        text_to_summarize = text.replace("THE TRANSCRIPT IS:", "").strip()
        st.info("2/3 - Summarizing English text...")

    print("✅ summarize_text: Calling Groq LLaMA model for summarization...")
    sys.stdout.flush()

    # ------- SPLIT INTO CHUNKS -------
    max_chunk_size = 1500
    words = text_to_summarize.split()
    chunks = [" ".join(words[i:i + max_chunk_size]) for i in range(0, len(words), max_chunk_size)]

    summaries = []

    # ------- GROQ SUMMARIZATION REQUEST -------
    for idx, chunk in enumerate(chunks, 1):
        summary_prompt = f"""
        You are a professional summarizer. Your job is to summarize the given transcript.
        Rules:
        - Create a clean bullet point summary.
        - Remove filler words & repetitions.
        - Maintain the original meaning
        - Final summary must be in English.
        - 200 to 250 words max.

        Text to summarize:
        {chunk}

        Now produce the summary:
        """

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": summary_prompt}]
            )

            summaries.append(response.choices[0].message.content.strip())
            print(f"✅ summarize_text: Processed chunk {idx}/{len(chunks)}")
            sys.stdout.flush()

        except Exception as e:
            print(f"⚠️ Error during Groq summarization: {e}")
            st.error(f"Error during Groq summarization: {e}")
            return None

    # ------- COMBINE MULTIPLE CHUNKS -------
    if len(summaries) > 1:
        combined = " ".join(summaries)

        final_prompt = f"""
        Combine these partial summaries into a cohesive summary.
        - Remove duplicates & repetition
        - Produce clean formatted bullet points
        - Limit final answer to 8-10 lines and remove bullets

        Partial summaries:
        {combined}

        Final Combined Summary:
        """

        final_response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": final_prompt}]
        )

        return final_response.choices[0].message.content.strip()

    return summaries[0]




def text_to_audio(text, audio_path):
    """
    Converts text to speech using ElevenLabs (High Quality) and saves it as an MP3 file.
    """
    print("✅ text_to_audio: Converting final summary to speech with ElevenLabs...")
    sys.stdout.flush()
    st.info("3/3 - Generating realistic AI voice... 🔉")

    try:
        api_key = "sk_e86cfb4b60786fefc126afd8567c0e5bb227e3f7e60568fd" 

        # if api_key == "YOUR_API_KEY_GOES_HERE":
        #     st.error("Please insert your ElevenLabs API Key in the code!")
        #     return False

        # Cleaning: We remove asterisks (*) but KEEP periods (.) so the AI pauses correctly.
        clean_summary = text.replace("*", "").replace(".", "").strip().replace("\n\n", "\n")

        client = ElevenLabs(api_key=api_key)

        audio = client.text_to_speech.convert(
            text=clean_summary,
            voice_id="21m00Tcm4TlvDq8ikWAM", 
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
            
        )

        # Save the audio file
        save(audio, audio_path)
        print("✅ text_to_audio: MP3 file saved.")
        sys.stdout.flush()
        return True
    except Exception as e:
        print(f"⚠️ Error during Text-to-Speech conversion: {e}")
        sys.stdout.flush()
        st.error(f"Error during Text-to-Speech conversion: {e}")
        return False
    


# ================= VIDEO SUMMARIZATION =====================
from scenedetect import SceneManager, open_video
from scenedetect.detectors import ContentDetector
from moviepy.editor import VideoFileClip, concatenate_videoclips

def detect_scenes(video_path):
    """
    Detects scene boundaries using latest PySceneDetect API.
    Returns list of (start_seconds, end_seconds)
    """
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=27.0))

    scene_manager.detect_scenes(video)
    scenes = scene_manager.get_scene_list()

    if len(scenes) == 0:
        return [(0, 60)]  # fallback: first 60 seconds

    return [(start.get_seconds(), end.get_seconds()) for start, end in scenes]


def select_key_scenes(scenes, max_scenes=5):
    return sorted(scenes, key=lambda x: x[1] - x[0], reverse=True)[:max_scenes]


def create_video_summary(video_path, scenes, output_path="summary_video.mp4"):
    video = VideoFileClip(video_path)

    clips = []
    for start, end in scenes:
        clips.append(video.subclip(start, min(end, start + 10)))

    final_clip = concatenate_videoclips(clips)
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    return output_path



