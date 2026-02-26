import time
import os
from tqdm import tqdm
from dotenv import load_dotenv
import json

# Your modular imports
from src.recipe_engine.ingestion import (
    google_drive_client,
    gemini_extractor,
    supabase_loader,
    utils  # Our new shared services file
)

load_dotenv()


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

if __name__ == "__main__":
    run_batch(limit=15)
    #ngest_from_url("https://www.iheartnaptime.net/meatball-recipe/#recipe")