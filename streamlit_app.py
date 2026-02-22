import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import asyncio
import edge_tts
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Magic Storybook", page_icon="📖", layout="centered")

try:
    GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
except Exception as e:
    st.error("Missing Secrets! Make sure GEMINI_API_KEY and your gsheets link are set.")
    st.stop()

client = genai.Client(api_key=GENAI_API_KEY)
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(spreadsheet=SHEET_URL, ttl=0)

# --- NATIVE GOOGLE IMAGE GENERATION ---
@st.cache_data(show_spinner=False)
def get_gemini_image(prompt, aspect="4:3"):
    """Uses your AI Studio key to generate guaranteed images."""
    try:
        res = client.models.generate_images(
            model="imagen-3.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1, 
                aspect_ratio=aspect,
                output_mime_type="image/jpeg"
            )
        )
        return res.generated_images[0].image.image_bytes
    except Exception as e:
        return None

def generate_good_audio(text, page_num):
    """Uses Microsoft Edge's Neural TTS for a highly realistic voice."""
    filename = f"story_page_{page_num}.mp3"
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    communicate = edge_tts.Communicate(text, "en-US-AriaNeural", rate="-10%")
    loop.run_until_complete(communicate.save(filename))
    loop.close()
    return filename

# --- 2. LOGIN & SIDEBAR ---
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
    st.header("✨ Add New Friends")
    new_n = st.text_input("Friend Name")
    new_d = st.text_area("What do they look like? (e.g. A tiny red dragon)")
    if st.button("Save Friend") and new_n and new_d:
        new_row = pd.DataFrame([[family_id, new_n, new_d]], columns=df.columns)
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        st.success("Added! Refreshing...")
        st.rerun()

# --- 3. SESSION STATE ---
if "story_pages" not in st.session_state:
    st.session_state.story_pages = []
    st.session_state.current_page = 0
    st.session_state.selected_char = None
    st.session_state.char_desc = None
    st.session_state.selected_setting = None
    st.session_state.selected_theme = None
    st.session_state.selected_style = None

# --- 4. THE VISUAL MENU ---
if not st.session_state.story_pages:
    st.title("📖 Let's Make a Book!")
    
    if user_chars.empty:
        st.info("Add a character in the sidebar menu to begin!")
        st.stop()

    # STEP 1: CHARACTER (WITH CLICKABLE PICTURES)
    if not st.session_state.selected_char:
        st.markdown("### 1️⃣ Tap your hero!")
        char_cols = st.columns(min(len(user_chars), 3)) 
        for i, row in user_chars.iterrows():
            with char_cols[i % 3]:
                with st.spinner("Drawing icon..."):
                    icon_bytes = get_gemini_image(f"Cute 3D icon of {row['char_desc']}, white background", "1:1")
                if icon_bytes:
                    st.image(icon_bytes, use_container_width=True)
                if st.button(f"Pick {row['char_name']}", key=f"char_{i}", use_container_width=True):
                    st.session_state.selected_char = row['char_name']
                    st.session_state.char_desc = row['char_desc']
                    st.rerun()

    # STEP 2: SETTING (WITH CLICKABLE PICTURES)
    elif not st.session_state.selected_setting:
        st.success(f"Hero: **{st.session_state.selected_char}**")
        st.markdown("### 2️⃣ Tap a place to go!")
        settings = ["The Moon", "A Candy Forest", "Under the Sea", "A Dinosaur Jungle"]
        set_cols = st.columns(2) 
        for i, s in enumerate(settings):
            with set_cols[i % 2]:
                with st.spinner("Drawing place..."):
                    set_bytes = get_gemini_image(f"Cute toddler landscape of {s}", "4:3")
                if set_bytes:
                    st.image(set_bytes, use_container_width=True)
                if st.button(f"Go to {s}", key=f"set_{i}", use_container_width=True):
                    st.session_state.selected_setting = s
                    st.rerun()

    # STEP 3: THEME & STYLE
    else:
        st.success(f"Hero: **{st.session_state.selected_char}**")
        st.success(f"Place: **{st.session_state.selected_setting}**")
        
        st.markdown("### 3️⃣ What is the story about?")
        themes = ["Sharing with friends", "Gentle hands (no hitting)", "Being brave", "Trying new foods", "Understanding big emotions"]
        theme_choice = st.selectbox("Choose a moral/theme:", themes, label_visibility="collapsed")
        
        st.markdown("### 4️⃣ Choose the Art Style!")
        styles = ["Soft 3D Pixar Animation", "Gentle Watercolor Illustration", "Bright Colorful Paper Cutout"]
        style_choice = st.selectbox("How should the pictures look?", styles, label_visibility="collapsed")
        
        st.markdown("---")
        colA, colB = st.columns(2)
        with colA:
            if st.button("⬅️ Start Over", use_container_width=True):
                st.session_state.selected_char = None
                st.session_state.selected_setting = None
                st.rerun()
        with colB:
            if st.button("🪄 Write my 10-Page Book!", use_container_width=True, type="primary"):
                with st.spinner("Writing the 10-page story..."):
                    prompt = f"""
                    Write a 10-page children's book for a 3-year-old. 
                    Character: {st.session_state.selected_char} ({st.session_state.char_desc}). 
                    Setting: {st.session_state.selected_setting}.
                    Theme/Moral: {theme_choice}.
                    
                    Output strictly a JSON array of 10 objects. Do not use markdown blocks.
                    Format: [{{"text": "Simple sentence.", "image_prompt": "Visual description"}}, ...]
                    
                    The story must have a beginning, middle, and end, teaching {theme_choice} gently.
                    The image_prompt must ALWAYS start with: "{style_choice} style, {st.session_state.selected_char} in {st.session_state.selected_setting}." Keep prompts under 15 words.
                    """
                    
                    res = client.models.generate_content(
                        model="gemini-2.5-flash", 
                        contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    
                    try:
                        pages = json.loads(res.text)
                        st.session_state.story_pages = pages
                        st.session_state.current_page = 0
                        st.session_state.selected_style = style_choice
                        st.rerun()
                    except Exception as e:
                        st.error("The magic book had a spelling mistake! Please try again.")

# --- 5. THE READING INTERFACE ---
else:
    page_data = st.session_state.story_pages[st.session_state.current_page]
    total_pages = len(st.session_state.story_pages)
    
    st.markdown(f"### Page {st.session_state.current_page + 1} of {total_pages}")
    
    # Generate the high-quality Imagen picture for this specific page
    with st.spinner("Painting the page... 🎨"):
        img_bytes = get_gemini_image(page_data['image_prompt'], "4:3")
        if img_bytes:
            st.image(img_bytes, use_container_width=True)
        else:
            st.error("Image failed to load.")
    
    # Text
    st.markdown(f"## {page_data['text']}")
    
    # High-Quality Audio Player
    with st.spinner("Loading narrator..."):
        audio_file = generate_good_audio(page_data['text'], st.session_state.current_page)
        st.audio(audio_file, format="audio/mpeg")
    
    st.markdown("---")
    
    # Navigation
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.session_state.current_page > 0:
            if st.button("⬅️ Previous Page", use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()
    with col2:
        if st.button("🔄 New Story", use_container_width=True):
            st.session_state.story_pages = []
            st.session_state.selected_char = None
            st.session_state.selected_setting = None
            st.rerun()
    with col3:
        if st.session_state.current_page < total_pages - 1:
            if st.button("Next Page ➡️", use_container_width=True, type="primary"):
                st.session_state.current_page += 1
                st.rerun()
        else:
            st.success("The End! 🎉")
