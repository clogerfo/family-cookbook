import streamlit as st
import os
import re
from supabase import create_client, Client
from streamlit_pdf_viewer import pdf_viewer
from src.recipe_engine.ingestion import google_drive_client
from orchestrator import ingest_from_multiple_images
import streamlit as st

# --- NEW: Cloud-Safe Dotenv Loader ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # We are in the cloud, ignore dotenv!


st.set_page_config(layout="wide", page_title="Recipe Staging Gateway")
supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
FOLDER_ID = os.environ.get("RECIPE_FOLDER_ID")

# --- CUSTOM CSS (Fixing the "Dark on Dark" Issue) ---
st.markdown("""
<style>
    /* Global Text Fix */
    .stApp, h1, h2, h3, p, div, span, label { 
        color: #2C3E50 !important; 
    }

    /* Input Fields Background */
    input, textarea, select {
        background-color: #FFFFFF !important;
        color: #2C3E50 !important;
        border: 1px solid #CED4DA;
    }

    /* Dropdown Menu Fix */
    div[data-baseweb="select"] > div {
        background-color: white !important;
        color: #2C3E50 !important;
    }
    div[data-baseweb="popover"] {
        background-color: white !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("👨‍🍳 Recipe Staging Gateway")

# --- CREATE TABS ---
tab1, tab2 = st.tabs(["📝 Review Queue", "📸 Snap & Cook"])

# ==========================================
# TAB 2: THE CAMERA / UPLOAD INPUT
# ==========================================
with tab2:
    st.header("📸 Snap & Cook")
    st.write("Upload or snap photos of a recipe. You can add multiple photos for the front and back of a card.")

    # The iOS Magic Button
    uploaded_photos = st.file_uploader(
        "Capture Recipe Pages",
        type=['jpg', 'jpeg', 'png'],
        accept_multiple_files=True,
        key = "mobile_recipe_uploader"  # <--- JUST ADD THIS LINE
    )

    if uploaded_photos:
        # Show how many were captured
        st.info(f"{len(uploaded_photos)} photo(s) ready for processing.")

        # We use a button so it doesn't run prematurely while you are taking the 2nd photo
        if st.button("🚀 Process Images", type="primary"):

            # Convert Streamlit uploaded files to raw bytes
            bytes_list = [photo.getvalue() for photo in uploaded_photos]

            with st.spinner("🧠 Gemini is reading your handwriting..."):

                result = ingest_from_multiple_images(bytes_list)

                if result == "success":
                    st.success("✅ Recipe digitized! Go to the Review Queue tab to publish it.")
                    st.balloons()
                elif result == "duplicate":
                    st.warning("⚠️ These photos match a recipe we already processed.")
                else:
                    st.error("❌ Something went wrong processing the images.")

with tab1:
    # --- DATA FETCHING ---
    response = supabase.table("recipes").select("*").eq("is_draft", True).execute()
    drafts = response.data

    if not drafts:
        st.balloons()
        st.success("All caught up! No drafts left to review.")
    else:
        # --- SIDEBAR: QUEUE ---
        with st.sidebar:
            st.header("Drafts Queue")
            options = {f"{d['title']} ({d.get('source_type', 'unknown')})": d for d in drafts}
            selected_label = st.selectbox("Select recipe to review:", options.keys())
            recipe = options[selected_label]

        col1, col2 = st.columns([1.2, 1])

        # --- LEFT COLUMN: SOURCE ---
        with col1:
            source_type = recipe.get('source_type', 'drive')

            if source_type == 'url':
                st.subheader("🌐 Web Source")
                url = recipe.get('source_url')
                if url:
                    st.info(f"Imported from: {url}")
                    st.markdown(f"[👉 Click to open original recipe]({url})")
                    st.divider()
                    st.caption("Review extracted text on the right.")
                else:
                    st.warning("No URL found for this import.")

            elif source_type == 'drive':
                st.subheader("📄 Original Scan")
                match = re.search(r"scan: (.*)", recipe.get('user_comments', ''))
                file_name = match.group(1) if match else None

                if file_name and FOLDER_ID:
                    try:
                        file_id = recipe.get('google_drive_id')
                        if not file_id:
                            file_id = google_drive_client.get_file_id_by_name(file_name, FOLDER_ID)

                        if file_id:
                            with st.spinner("Fetching PDF from Drive..."):
                                pdf_bytes = google_drive_client.download_file_bytes(file_id)
                                pdf_viewer(input=pdf_bytes, width=700)
                        else:
                            st.error(f"Could not find file '{file_name}' in Drive.")
                    except Exception as e:
                        st.error(f"Error loading PDF: {e}")
            elif source_type == 'camera':
                st.subheader("📸 Mobile Snapshot")

                # Retrieve the URLs we saved
                image_urls = recipe.get('image_urls', [])

                if image_urls:
                    st.info(f"Viewing {len(image_urls)} captured page(s).")
                    # Loop through and display every image (front, back, etc.)
                    for url in image_urls:
                        st.image(url, use_container_width=True)
                        st.divider()
                else:
                    st.warning("No images were saved for this upload. Please verify extraction manually.")
            else:
                st.info(f"Unknown source type: {source_type}")

        # --- RIGHT COLUMN: THE EDITOR ---
        with col2:
            st.subheader("📝 Metadata & Extraction")

            with st.form("edit_form"):
                # 1. Family Heritage Section
                c_fam, c_chef = st.columns(2)
                with c_fam:
                    # Default to Logerfo if null
                    current_fam = recipe.get('family_tag') or "Logerfo"
                    family_tag = st.selectbox("Family Lineage", ["Logerfo", "Keenoy", "Other"],
                                              index=["Logerfo", "Keenoy", "Other"].index(current_fam) if current_fam in [
                                                  "Logerfo", "Keenoy", "Other"] else 0)

                with c_chef:
                    # Default to current value or empty
                    chef_name = st.text_input("Original Chef (Author)", value=recipe.get('uploader_name') or "")

                st.divider()

                # 2. Standard Metadata
                new_title = st.text_input("Title", value=recipe.get('title', 'Untitled'))
                new_category = st.selectbox(
                    "Category",
                    ["breakfast", "lunch", "dinner", "snack", "bake"],
                    index=["breakfast", "lunch", "dinner", "snack", "bake"].index(recipe.get('category', 'dinner'))
                )

                # --- NEW: TIMING & SERVINGS FIELDS ---
                c_prep, c_cook, c_serve = st.columns(3)
                with c_prep:
                    # Use int() and or 0 to handle NULL database values safely
                    prep_time = st.number_input("Prep (min)", min_value=0, value=int(recipe.get('prep_time_min') or 0))
                with c_cook:
                    cook_time = st.number_input("Cook (min)", min_value=0, value=int(recipe.get('cook_time_min') or 0))
                with c_serve:
                    # Servings is often a string like "4-6", so text_input is safer than number_input
                    servings = st.text_input("Servings", value=str(recipe.get('servings') or ""))

                st.write("**Ingredients (JSON)**")

                # 3. Content
                st.write("**Ingredients (JSON)**")
                new_ingredients = st.text_area(
                    "Edit Ingredients",
                    value=str(recipe.get('ingredients', [])),
                    height=250
                )

                st.write("**Instructions**")
                instructions_val = recipe.get('instructions', [])
                if isinstance(instructions_val, list):
                    instructions_val = "\n".join(instructions_val)

                new_instructions = st.text_area(
                    "Edit Steps",
                    value=instructions_val,
                    height=250
                )

                user_notes = st.text_area(
                    "Family Heritage Notes",
                    value=recipe.get('user_notes', ''),
                    placeholder="e.g. Grandma always used a cast iron for this..."
                )

                # --- ACTIONS ---
                c_submit, c_discard = st.columns([1, 1])

                with c_submit:
                    if st.form_submit_button("✅ Publish to Archive", type="primary"):

                        # 1. Safely handle integer conversions
                        safe_prep = prep_time if prep_time > 0 else None
                        safe_cook = cook_time if cook_time > 0 else None

                        safe_servings = None
                        if servings and str(servings).strip().isdigit():
                            safe_servings = int(str(servings).strip())

                        # 2. Build the payload
                        updates = {
                            "title": new_title,
                            "category": new_category,
                            "family_tag": family_tag,
                            "uploader_name": chef_name,
                            "prep_time_min": safe_prep,  # Uses the cleaned variable
                            "cook_time_min": safe_cook,  # Uses the cleaned variable
                            "servings": safe_servings,  # Uses the cleaned variable
                            "user_notes": user_notes,
                            "is_draft": False
                        }

                        # 3. Send to Supabase
                        supabase.table("recipes").update(updates).eq("id", recipe['id']).execute()
                        st.success(f"Published {new_title} to the {family_tag} collection!")
                        st.rerun()

                with c_discard:
                    if st.form_submit_button("🗑️ Discard Draft"):
                        supabase.table("recipes").delete().eq("id", recipe['id']).execute()
                        st.warning("Draft deleted.")
                        st.rerun()

