import os 
import streamlit

def temp_directory():
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    return temp_dir

def save_uploaded_file(uploaded_file,temp_dir):
    if uploaded_file:
        file_path = os.path.join(temp_dir,uploaded_file.name)
        with open (file_path,'wb') as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None