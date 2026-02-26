import streamlit as st
import os
import json
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Family Heritage Cookbook",
    page_icon="🍲",
    layout="centered"
)

try:
    supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
except Exception:
    st.error("Could not connect to the Cookbook.")
    st.stop()

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* 1. Global Background */
    .stApp { background-color: #f4f6f9; }
    h1, h2, h3, h4, h5, h6, p, div, span, label { color: #2C3E50 !important; }

    /* 2. Expander (Recipe Name) - Force White on all states (Hover, Active, Focus) */
    div[data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"] details summary,
    div[data-testid="stExpander"] details summary:hover,
    div[data-testid="stExpander"] details summary:active,
    div[data-testid="stExpander"] details summary:focus {
        background-color: #FFFFFF !important;
        color: #2C3E50 !important;
        font-weight: 600;
        font-size: 1.1em;
    }

    /* 3. Dropdowns (Category & Version History) - Force White Fill */
    div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #2C3E50 !important;
        border: 1px solid #ccc !important;
    }
    /* The dropdown list items when opened */
    ul[data-baseweb="menu"] { background-color: #FFFFFF !important; }
    li[data-baseweb="menu-item"] { color: #2C3E50 !important; }

    /* 4. Buttons (The "Update" Button) */
    button[kind="secondary"] {
        background-color: #FFFFFF !important;
        color: #2C3E50 !important;
        border: 1px solid #ccc !important;
    }
    button[kind="secondary"]:hover {
        border-color: #1565C0 !important;
        color: #1565C0 !important;
    }

    /* 5. The Data Editor Fix (Invisible Text) */
    /* Streamlit renders the active editing cell inside a portal. We force dark text here. */
    [data-testid="stDataFrame"] input,
    [data-testid="stDataFrame"] textarea,
    #portal input, 
    #portal textarea {
        color: #2C3E50 !important;
        -webkit-text-fill-color: #2C3E50 !important; /* Overrides WebKit forced colors */
        background-color: #FFFFFF !important;
    }

    /* 6. Formatting */
    ul.ingredient-list { list-style-type: none; padding-left: 0; }
    li.ingredient-item { margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px dashed #eee; font-size: 0.95em; }
    .tag {
        display: inline-block; background-color: #E3F2FD; color: #1565C0 !important;
        padding: 4px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600; margin-right: 5px;
    }
    .chef-tag { background-color: #FFF3CD; color: #856404 !important; }

</style>
""", unsafe_allow_html=True)


# --- HELPER: FORMATTING FOR DISPLAY ---
def format_ingredients(ingredients_data):
    html_output = "<ul class='ingredient-list'>"
    if isinstance(ingredients_data, str):
        try:
            ingredients_data = json.loads(ingredients_data.replace("'", '"'))
        except:
            items = ingredients_data.split('\n')
            for item in items:
                if item.strip(): html_output += f"<li class='ingredient-item'>{item}</li>"
            return html_output + "</ul>"

    if isinstance(ingredients_data, list):
        for ing in ingredients_data:
            if isinstance(ing, dict):
                qty, unit, item = ing.get('qty', ''), ing.get('unit', ''), ing.get('item', 'Item')
                html_output += f"<li class='ingredient-item'><b>{qty} {unit}</b> {item}</li>".replace("<b>  </b> ", "")
            else:
                html_output += f"<li class='ingredient-item'>{ing}</li>"
    return html_output + "</ul>"


def format_instructions(instructions_data):
    if isinstance(instructions_data, str):
        try:
            if instructions_data.strip().startswith('['):
                instructions_data = json.loads(instructions_data.replace("'", '"'))
            else:
                return instructions_data.replace('\n', '<br><br>')
        except:
            return instructions_data

    if isinstance(instructions_data, list):
        html_out = ""
        for idx, step in enumerate(instructions_data, 1):
            html_out += f"<div style='margin-bottom:10px;'><b>{idx}.</b> {step}</div>"
        return html_out
    return str(instructions_data)


# --- HELPER: NORMALIZATION FOR EDITORS ---
def normalize_ingredients_for_editor(ing_data):
    """Ensures data is a list of dicts for the Pandas DataFrame."""
    normalized = []
    if isinstance(ing_data, str):
        try:
            ing_data = json.loads(ing_data.replace("'", '"'))
        except:
            ing_data = [{"item": x.strip()} for x in ing_data.split('\n') if x.strip()]

    if isinstance(ing_data, list):
        for item in ing_data:
            if isinstance(item, dict):
                normalized.append({
                    "qty": str(item.get("qty", "")),
                    "unit": str(item.get("unit", "")),
                    "item": str(item.get("item", item.get("name", "")))
                })
            else:
                normalized.append({"qty": "", "unit": "", "item": str(item)})

    if not normalized:  # Give them one empty row to start
        normalized.append({"qty": "", "unit": "", "item": ""})
    return normalized


def normalize_instructions_for_editor(inst_data):
    """Ensures data is a list of dicts with a 'step' key."""
    normalized = []
    if isinstance(inst_data, str):
        try:
            inst_data = json.loads(inst_data.replace("'", '"'))
        except:
            inst_data = [x.strip() for x in inst_data.split('\n') if x.strip()]

    if isinstance(inst_data, list):
        for step in inst_data:
            normalized.append({"step": str(step)})

    if not normalized:
        normalized.append({"step": ""})
    return normalized


# --- POP-UP DIALOG FOR VERSIONING ---
@st.dialog("Iterate Recipe", width="large")
def iterate_recipe_modal(recipe):
    st.markdown(f"**Creating v{recipe.get('version', 1) + 1} of {recipe['title']}**")

    with st.form(f"iterate_form_{recipe['id']}"):
        change_reason = st.text_input("Why are you changing this?", placeholder="e.g., Needed more salt...")

        # --- NEW: EDITABLE TIMING FIELDS ---
        c_p, c_c, c_s = st.columns(3)
        with c_p:
            new_prep = st.number_input("Prep Time (min)", min_value=0, value=int(recipe.get('prep_time_min') or 0))
        with c_c:
            new_cook = st.number_input("Cook Time (min)", min_value=0, value=int(recipe.get('cook_time_min') or 0))
        with c_s:
            new_servings = st.text_input("Servings", value=str(recipe.get('servings') or ""))

        st.write("**Ingredients**")

        # 1. Convert to DataFrame
        ing_df = pd.DataFrame(normalize_ingredients_for_editor(recipe.get('ingredients', [])))
        # 2. Display interactive table
        edited_ing_df = st.data_editor(
            ing_df,
            num_rows="dynamic",  # Allows adding/deleting rows
            use_container_width=True,
            hide_index=True,
            column_config={
                "qty": st.column_config.TextColumn("Qty", width="small"),
                "unit": st.column_config.TextColumn("Unit", width="small"),
                "item": st.column_config.TextColumn("Ingredient", width="large", required=True),
            }
        )

        st.write("**Instructions**")
        inst_df = pd.DataFrame(normalize_instructions_for_editor(recipe.get('instructions', [])))
        edited_inst_df = st.data_editor(
            inst_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "step": st.column_config.TextColumn("Recipe Step", width="large", required=True)
            }
        )

        if st.form_submit_button("💾 Save New Version", type="primary"):
            if not change_reason:
                st.error("Please provide a reason!")
            else:
                # Convert DataFrames back to cleanly formatted lists for the database
                # Drop rows where the ingredient item or instruction step is totally blank
                final_ingredients = edited_ing_df.dropna(subset=['item']).to_dict('records')
                final_instructions = edited_inst_df['step'].dropna().tolist()

                root_parent_id = recipe.get('parent_id') if recipe.get('parent_id') else recipe['id']

                new_version = {
                    "title": recipe['title'],
                    "category": recipe['category'],
                    "family_tag": recipe.get('family_tag'),
                    "uploader_name": recipe.get('uploader_name'),
                    "ingredients": final_ingredients,
                    "instructions": final_instructions,
                    "parent_id": root_parent_id,
                    "version": recipe.get('version', 1) + 1,
                    "prep_time_min": new_prep,  # NEW
                    "cook_time_min": new_cook,  # NEW
                    "servings": new_servings,  # NEW
                    "change_reason": change_reason,
                    "is_draft": False
                }

                supabase.table("recipes").insert(new_version).execute()
                st.success("Version saved!")
                st.rerun()


# --- MAIN APP LOGIC ---
st.title("🍲 Family Heritage Cookbook")

families = ["All Recipes", "Logerfo", "Keenoy"]
selected_tab = st.radio("Family Collection", families, horizontal=True, label_visibility="collapsed")

col1, col2 = st.columns([3, 1])
with col1:
    search_query = st.text_input("🔍 Search...", "")
with col2:
    category_filter = st.selectbox("Category", ["All", "Breakfast", "Lunch", "Dinner", "Snack", "Bake"])

query = supabase.table("recipes").select("*").eq("is_draft", False)
if selected_tab != "All Recipes": query = query.ilike("family_tag", f"%{selected_tab}%")
if category_filter != "All": query = query.ilike("category", category_filter.lower())

raw_recipes = query.execute().data

if search_query:
    q = search_query.lower()
    raw_recipes = [r for r in raw_recipes if q in r['title'].lower() or q in str(r['ingredients']).lower()]

lineages = {}
for r in raw_recipes:
    root_id = r.get('parent_id') or r['id']
    if root_id not in lineages: lineages[root_id] = []
    lineages[root_id].append(r)

for root_id in lineages:
    lineages[root_id].sort(key=lambda x: x.get('version', 1), reverse=True)

if not lineages:
    st.info("No recipes found.")
else:
    for root_id, history in lineages.items():
        latest = history[0]
        cat_emoji = {"breakfast": "🍳", "lunch": "🥪", "dinner": "🍝", "snack": "🥨", "bake": "🍰"}.get(
            latest['category'].lower(), "🍽️")

        with st.expander(f"{cat_emoji}  {latest['title']} (v{latest.get('version', 1)})"):
            chef_name = latest.get('uploader_name') or "Family Classic"
            st.markdown(
                f"<span class='tag'>{latest['category'].upper()}</span><span class='tag chef-tag'>👤 {chef_name}</span>",
                unsafe_allow_html=True)

            display_recipe = latest

            # We use a clean flexbox layout to line them up horizontally
            meta_html = "<div style='display: flex; gap: 20px; margin-top: 15px; margin-bottom: 5px; font-size: 0.95em; color: #555;'>"
            if display_recipe.get('prep_time_min'):
                meta_html += f"<span>⏱️ <b>Prep:</b> {display_recipe['prep_time_min']} min</span>"
            if display_recipe.get('cook_time_min'):
                meta_html += f"<span>🍳 <b>Cook:</b> {display_recipe['cook_time_min']} min</span>"
            if display_recipe.get('servings'):
                meta_html += f"<span>🍽️ <b>Yield:</b> {display_recipe['servings']}</span>"
            meta_html += "</div><hr style='margin-top: 10px; margin-bottom: 15px;'>"

            # Only render if at least one of the fields has data
            if "⏱️" in meta_html or "🍳" in meta_html or "🍽️" in meta_html:
                st.markdown(meta_html, unsafe_allow_html=True)
            else:
                st.divider()  # Fallback divider if no timing data exists

            if len(history) > 1:
                st.write("")
                options = {f"v{r.get('version', 1)}: {r.get('change_reason', 'Original')}": r for r in history}
                selected_label = st.selectbox("📜 View Version History", options.keys(), key=f"sel_{root_id}")
                display_recipe = options[selected_label]
                st.markdown(f"*Viewing: {selected_label}*")
                st.divider()

            c1, c2 = st.columns([1, 1.5])
            with c1:
                st.markdown("### 🛒 Ingredients")
                st.markdown(format_ingredients(display_recipe.get('ingredients', [])), unsafe_allow_html=True)
            with c2:
                st.markdown("### 👨‍🍳 Instructions")
                st.markdown(format_instructions(display_recipe.get('instructions', [])), unsafe_allow_html=True)

            st.divider()
            c_note, c_btn = st.columns([3, 1])
            with c_note:
                if display_recipe.get('change_reason'):
                    st.info(f"**Update Note:** {display_recipe['change_reason']}")
                elif display_recipe.get('user_notes'):
                    st.success(f"**Family Note:** {display_recipe['user_notes']}")

            with c_btn:
                if st.button("🔄 Update", key=f"btn_{display_recipe['id']}"):
                    iterate_recipe_modal(display_recipe)