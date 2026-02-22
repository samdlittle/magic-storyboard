import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
from gtts import gTTS
import base64
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Magic Storybook", page_icon="🎨")

# Accessing secrets for deployment
try:
    GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
except:
    st.error("Secrets not found. Please check your Streamlit Cloud settings!")
    st.stop()

# Initialize Gemini Client
client = genai.Client(api_key=GENAI_API_KEY)

# --- 2. MULTI-USER DATA ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(spreadsheet=SHEET_URL, ttl=0)

# --- 3. LOGIN & SIDEBAR ---
if 'family_id' not in st.session_state:
    st.title("👨‍👩‍👧‍👦 Magic Storybook")
    fid = st.text_input("Enter Family Name (no spaces):").lower().strip()
    if st.button("Open My Book") and fid:
        st.session_state.family_id = fid
        st.rerun()
    st.stop()

family_id = st.session_state.family_id
df = load_data()
user_chars = df[df['family_id'] == family_id]

with st.sidebar:
    st.header(f"✨ {family_id.capitalize()}'s Friends")
    new_n = st.text_input("Friend Name")
    new_d = st.text_area("What do they look like?")
    if st.button("Save Friend"):
        new_row = pd.DataFrame([[family_id, new_n, new_d]], columns=df.columns)
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        st.success("Added! Refreshing...")
        st.rerun()

# --- 4. THE STORYBOOK ---
st.title(f"📖 The Adventures of {family_id.capitalize()}")

if user_chars.empty:
    st.info("Your book is empty! Add a character in the sidebar to begin.")
else:
    char_name = st.selectbox("Who is the hero?", user_chars['char_name'])
    char_desc = user_chars[user_chars['char_name'] == char_name]['char_desc'].values[0]
    setting = st.selectbox("Where are they?", ["The Moon", "A Candy Forest", "Under the Sea", "A Dinosaur Jungle"])
    action = st.text_input("Optional: What is happening? (e.g. playing ball)")

    if st.button("🪄 Make the Page!", use_container_width=True):
        with st.spinner("Writing and Painting..."):
            # A. Generate Text (Gemini 2.5 Flash Model)
            story_prompt = f"Write a 4-sentence story for a 3-year-old about {char_name} ({char_desc}) in {setting}. Context: {action}."
            story_res = client.models.generate_content(model="gemini-2.5-flash", contents=story_prompt)
            story_text = story_res.text

            # B. Generate Image (Imagen 3.0)
            img_prompt = f"Child-friendly soft 3D animation style. {char_name} ({char_desc}) in {setting}. Bright and happy colors."
            
            try:
                # We use generate_images with the official Imagen 3 model
                # and explicitly ask for 1 image to avoid free-tier quota limits
                image_res = client.models.generate_images(
                    model="imagen-3.0-generate-001",
                    prompt=img_prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="4:3",
                        output_mime_type="image/jpeg"
                    )
                )
                
                # C. Display Results
                st.image(image_res.generated_images[0].image.image_bytes)
            except Exception as e:
                # Fallback so the app doesn't crash if the image API hiccups
                st.warning("The magic painter is taking a quick break, but here is your story!")
            
            st.subheader(story_text)

            # D. Audio Read Aloud
            tts = gTTS(text=story_text, lang='en')
            tts.save("story.mp3")
            with open("story.mp3", "rb") as f:
                data = base64.b64encode(f.read()).decode()
                st.markdown(f'<audio autoplay="true" src="data:audio/mp3;base64,{data}">', unsafe_allow_html=True)
