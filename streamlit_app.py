import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import urllib.parse
import json
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

# Helper to generate safe image URLs
def get_image_url(prompt):
    # Keep the prompt very short to prevent URL breaking
    short_prompt = prompt[:150] 
    safe_prompt = urllib.parse.quote(short_prompt)
    return f"https://image.pollinations.ai/prompt/{safe_prompt}?nologo=true"

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

# --- 3. SESSION STATE FOR THE BOOK ---
if "story_pages" not in st.session_state:
    st.session_state.story_pages = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 0
if "selected_char" not in st.session_state:
    st.session_state.selected_char = None
if "char_desc" not in st.session_state:
    st.session_state.char_desc = None
if "selected_setting" not in st.session_state:
    st.session_state.selected_setting = None

# --- 4. THE VISUAL MENU ---
if not st.session_state.story_pages:
    st.title("📖 Let's Make a Book!")
    
    if user_chars.empty:
        st.info("Add a character in the sidebar menu to begin!")
        st.stop()

    # STEP 1: PICK A CHARACTER
    if not st.session_state.selected_char:
        st.markdown("### 1️⃣ Tap your hero!")
        char_cols = st.columns(min(len(user_chars), 3)) 
        
        for i, row in user_chars.iterrows():
            with char_cols[i % 3]:
                # Visual Icon
                icon_url = get_image_url(f"Cute 3D icon of {row['char_desc']}")
                st.image(icon_url, use_container_width=True)
                
                if st.button(f"Pick {row['char_name']}", key=f"char_{i}", use_container_width=True):
                    st.session_state.selected_char = row['char_name']
                    st.session_state.char_desc = row['char_desc']
                    st.rerun()

    # STEP 2: PICK A SETTING
    elif not st.session_state.selected_setting:
        st.success(f"Hero: **{st.session_state.selected_char}**")
        if st.button("⬅️ Change Hero"):
            st.session_state.selected_char = None
            st.rerun()
            
        st.markdown("### 2️⃣ Tap a place to go!")
        settings = ["The Moon", "A Candy Forest", "Under the Sea", "A Dinosaur Jungle"]
        set_cols = st.columns(2) 
        
        for i, s in enumerate(settings):
            with set_cols[i % 2]:
                # Visual Icon
                set_url = get_image_url(f"Cute toddler landscape of {s}")
                st.image(set_url, use_container_width=True)
                
                if st.button(f"Go to {s}", key=f"set_{i}", use_container_width=True):
                    st.session_state.selected_setting = s
                    st.rerun()

    # STEP 3: GENERATE THE BOOK
    else:
        st.success(f"Hero: **{st.session_state.selected_char}**")
        st.success(f"Place: **{st.session_state.selected_setting}**")
        if st.button("⬅️ Start Over"):
            st.session_state.selected_char = None
            st.session_state.selected_setting = None
            st.rerun()
            
        st.markdown("---")
        if st.button("🪄 Write my 8-Page Book!", use_container_width=True, type="primary"):
            with st.spinner("Writing the story... this takes about 10 seconds!"):
                char_n = st.session_state.selected_char
                char_d = st.session_state.char_desc
                place = st.session_state.selected_setting

                prompt = f"""
                Write an 8-page children's book for a 3-year-old. 
                Character: {char_n} ({char_d}). Setting: {place}.
                Output a JSON array of 8 objects.
                Format exactly like this: [{{"text": "Short simple sentence here.", "image_prompt": "Visual description of the scene"}}, ...]
                Keep the image_prompt VERY short (under 10 words). Example: "Pixar style, {char_n} in {place}."
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
                    st.rerun()
                except Exception as e:
                    st.error("The magic book had a spelling mistake! Please click generate again.")

# --- 5. THE READING INTERFACE (THE PAGES) ---
else:
    page_data = st.session_state.story_pages[st.session_state.current_page]
    total_pages = len(st.session_state.story_pages)
    
    st.markdown(f"### Page {st.session_state.current_page + 1} of {total_pages}")
    
    # Render the Image directly
    img_url = get_image_url(page_data['image_prompt'])
    st.image(img_url, use_container_width=True)
    
    # Render the Text
    st.markdown(f"## {page_data['text']}")
    
    st.markdown("---")
    
    # Navigation Buttons
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
