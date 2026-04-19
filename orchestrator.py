import time
import os
from tqdm import tqdm
from dotenv import load_dotenv
import json
from google import genai
from google.genai import types
from supabase import create_client, Client
import cloudscraper
from bs4 import BeautifulSoup

# --- SUPABASE CONNECTION ---
supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# --- NEW: Cloud-Safe Dotenv Loader ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # We are in the cloud, ignore dotenv!

# Your modular imports
from src.recipe_engine.ingestion import (
    google_drive_client,
    gemini_extractor,
    supabase_loader,
    utils  # Our new shared services file
)

#load_dotenv()

import json


def ingest_from_drive(file_id, file_name, force_retry=False):
    """Orchestrates the movement of a single Drive file to Supabase."""
    try:
        # 1. Librarian gets the data
        pdf_bytes = google_drive_client.download_file_bytes(file_id)

        # 2. Utils checks the fingerprint (Deduplication)
        content_hash = utils.generate_content_hash(pdf_bytes)

        if utils.is_duplicate(content_hash) and not force_retry:
            return "skipped"

        # 3. Brain extracts the data
        data = gemini_extractor.extract_recipe_from_pdf(pdf_bytes, file_name)

        if data:
            # Enrich with metadata before saving
            data.update({
                "content_hash": content_hash,
                "google_drive_id": file_id,
                "source_type": "drive",
                "is_draft": True
            })

            # 4. Vault saves the data
            supabase_loader.save_to_supabase(data, file_name)
            return "success"

        return "error"

    except Exception as e:
        print(f"\n❌ Pipeline Error on {file_name}: {e}")
        return "error"


def run_batch(limit=None):
    folder_id = os.environ.get("RECIPE_FOLDER_ID")
    all_files = google_drive_client.get_all_pdfs(folder_id)
    files_to_process = all_files[:limit] if limit else all_files

    stats = {"success": 0, "skipped": 0, "error": 0}

    # Progress bar for visual feedback
    for f in tqdm(files_to_process, desc="Syncing Drive to Supabase", unit="recipe"):
        result = ingest_from_drive(f['id'], f['name'])
        stats[result] += 1

        # Only sleep if we actually hit the API to stay under rate limits
        if result != "skipped":
            time.sleep(12)

    print(f"\n🏁 Batch Complete | Success: {stats['success']} | Skipped: {stats['skipped']} | Errors: {stats['error']}")


def ingest_from_url(url: str):
    # 1. Deduplicate by URL string
    url_hash = utils.generate_content_hash(url)
    if utils.is_duplicate(url_hash):
        print("⏩ URL already exists in archive.")
        return

    # 2. Extract
    data = gemini_extractor.extract_recipe_from_url(url)

    if data:
        data.update({
            "content_hash": url_hash,
            "source_url": url,
            "source_type": "url",
            "is_draft": True
        })
        # 3. Save
        supabase_loader.save_to_supabase(data, "Web Import")


def ingest_from_url_waterfall(url: str):
    """
    Attempts to extract a recipe using a waterfall strategy to bypass firewalls.
    """
    # 1. Deduplicate
    url_hash = utils.generate_content_hash(url)
    if utils.is_duplicate(url_hash):
        print("⏩ URL already exists in archive.")
        return "duplicate"

    page_text = None

    # 2. ATTEMPT 1: The Stealth Scraper & JSON-LD Hunter
    try:
        print(f"🌐 Attempt 1: Stealth scraping {url}...")
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True})
        response = scraper.get(url, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # --- THE MAGIC TRICK: Hunt for the hidden SEO Recipe Data ---
            recipe_json_ld = None
            for script in soup.find_all('script', type='application/ld+json'):
                if 'Recipe' in script.text:
                    recipe_json_ld = script.text
                    break

            if recipe_json_ld:
                print("🎯 Jackpot! Found hidden schema.org recipe data.")
                page_text = recipe_json_ld  # We ONLY pass this perfect data to Gemini
            else:
                print("⚠️ No schema found. Falling back to raw text extraction.")
                # If no hidden schema, grab the visible text (keep it tight, ~20k chars)
                page_text = soup.get_text(separator='\n', strip=True)[:100000]

    except Exception as e:
        print(f"⚠️ Attempt 1 Failed (Firewall blocked the scraper): {e}")

    # 3. Route to the correct Gemini Extractor
    data = None
    if page_text:
        # If we successfully bypassed the firewall, feed the text to Gemini
        # (Make sure you updated your extract_recipe_from_text function as we discussed!)
        data = gemini_extractor.extract_recipe_from_text(page_text)
    else:
        # ATTEMPT 2: The Fallback
        # If the scraper failed, we just pass the URL directly to Gemini and pray it isn't blocked.
        print("🤖 Attempt 2: Sending raw URL directly to Gemini...")
        data = gemini_extractor.extract_recipe_from_url(url)

    # 🐛 DEBUG 2: Save the final JSON object Gemini generated (from either attempt)
    with open("debug_2_gemini_data.json", "w", encoding="utf-8") as f:
        if data:
            json.dump(data, f, indent=4)  # Pretty-prints the dictionary
        else:
            f.write("Gemini returned None (Failed to extract anything)")

    # 4. Save to Database
    if data:
        data.update({
            "content_hash": url_hash,
            "source_url": url,
            "source_type": "url",
            "is_draft": True
        })
        supabase_loader.save_to_supabase(data, "Web Import")
        return "success"
    else:
        return "error"


def ingest_from_multiple_images(image_bytes_list: list, filename: str = "Multi-page Snapshot"):
    """
    Ingests raw images directly from the Streamlit UI and saves them to Supabase Storage.
    """
    try:
        print(f"📸 Commander: Processing {len(image_bytes_list)} mobile upload(s)...")

        # 1. Deduplicate
        combined_bytes = b"".join(image_bytes_list)
        content_hash = utils.generate_content_hash(combined_bytes)

        if utils.is_duplicate(content_hash):
            return "duplicate"

        import os
        from supabase import create_client

        # Create an independent connection to avoid circular imports
        supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        saved_image_urls = []
        for idx, img_bytes in enumerate(image_bytes_list):
            file_name = f"{content_hash}_{idx}.jpg"
            try:
                # Upload to the bucket we just created
                supabase.storage.from_("recipe_images").upload(
                    file_name,
                    img_bytes,
                    {"content-type": "image/jpeg"}
                )
                # Get the public URL
                public_url = supabase.storage.from_("recipe_images").get_public_url(file_name)
                saved_image_urls.append(public_url)
            except Exception as e:
                print(f"⚠️ Warning: Could not save image {idx} to storage: {e}")

        # 3. The Brain: Extract from Images
        data = gemini_extractor.extract_recipe_from_multiple_images(image_bytes_list)

        if data:
            data.update({
                "content_hash": content_hash,
                "source_type": "camera",
                "is_draft": True,
                "uploader_name": "Mobile Upload",
                "image_urls": saved_image_urls  # <--- NEW: Attaching the URLs
            })

            # 4. The Vault: Save
            supabase_loader.save_to_supabase(data, filename)
            return "success"

    except Exception as e:
        print(f"❌ Error handling images: {e}")
        return "error"


def ingest_from_web_text(page_text: str, url: str):
    """Passes scraped web text to Gemini and saves to Supabase."""
    try:
        # Initialize the new Gemini client
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

        prompt = f"""
        You are an expert culinary AI. Extract the recipe from the following web page text.
        Ignore all ads, reviews, and personal blog stories. 

        Return ONLY a raw JSON object with these exact keys:
        - "title" (string)
        - "category" (string: experiment, breakfast, lunch, dinner, snack, or bake)
        - "prep_time_min" (integer or null)
        - "cook_time_min" (integer or null)
        - "servings" (integer or null)
        - "ingredients" (list of dictionaries, each with 'qty', 'unit', and 'item')
        - "instructions" (list of strings for the steps)
        - "uploader_name" (string: try to find the author's name, or null)

        Web Page Text:
        {page_text}
        """

        # Call Gemini
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        # Parse the JSON response
        recipe_data = json.loads(response.text)

        # Attach our metadata for the Review Queue
        recipe_data['source_type'] = 'url'
        recipe_data['source_url'] = url
        recipe_data['is_draft'] = True

        # Push to database
        supabase.table("recipes").insert(recipe_data).execute()
        return "success"

    except Exception as e:
        print(f"Extraction Error: {e}")
        return "error"


def generate_from_menu(image_bytes: bytes, target_dish: str = ""):
    """Reads a restaurant menu and reverse-engineers a make-at-home recipe."""
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

        # We tell the AI what dish to look for, or to pick the best one if left blank
        dish_focus = f"the dish named '{target_dish}'" if target_dish else "the most prominent or unique main course"

        prompt = f"""
        You are an expert executive chef. The attached image is a restaurant menu. 
        Locate {dish_focus} on this menu. 

        Based on the menu's description of that dish, reverse-engineer a detailed, high-quality recipe 
        so the user can recreate it at home. Invent exact measurements and step-by-step instructions 
        that match the flavor profile described on the menu.

        Return ONLY a raw JSON object with these exact keys:
        - "title" (string: The name of the dish + " (Restaurant Copycat)")
        - "category" (string: experiment, dinner, lunch, breakfast, snack, or bake)
        - "prep_time_min" (integer)
        - "cook_time_min" (integer)
        - "servings" (integer: default to 2 or 4)
        - "ingredients" (list of dictionaries, each with 'qty', 'unit', and 'item')
        - "instructions" (list of strings for the steps)
        - "uploader_name" (string: "AI Chef")
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        recipe_data = json.loads(response.text)

        # Attach metadata to flag this as an AI-generated copycat
        recipe_data['source_type'] = 'camera'
        recipe_data['family_tag'] = 'Generated'
        recipe_data['user_notes'] = f"AI-Generated copycat recipe based on a restaurant menu."
        recipe_data['is_draft'] = True

        supabase.table("recipes").insert(recipe_data).execute()
        return "success"

    except Exception as e:
        print(f"Generation Error: {e}")
        return "error"

if __name__ == "__main__":
    run_batch(limit=15)
    #ngest_from_url("https://www.iheartnaptime.net/meatball-recipe/#recipe")