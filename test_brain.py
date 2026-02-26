import os
import json
from dotenv import load_dotenv
from src.recipe_engine.ingestion import google_drive_client, gemini_extractor

# 1. Load your API keys
load_dotenv()


def test_single_extraction():
    print("🚀 Starting Dry Run Test...")

    # 2. Get a list of PDFs from the Librarian
    service = google_drive_client.get_drive_service()
    folder_id = os.environ["RECIPE_FOLDER_ID"]
    query = f"'{folder_id}' in parents and mimeType = 'application/pdf'"

    results = service.files().list(q=query, pageSize=1, fields="files(id, name)").execute()
    files = results.get('files', [])

    if not files:
        print("📭 No PDFs found in your recipe folder. Check your FOLDER_ID.")
        return

    test_file = files[0]
    print(f"📄 Found File: {test_file['name']} (ID: {test_file['id']})")

    # 3. Librarian downloads the bytes
    print("📥 Downloading bytes...")
    pdf_bytes = google_drive_client.download_file_bytes(test_file['id'])

    # 4. Brain processes the bytes (The real test!)
    try:
        print("🧠 Sending to Gemini for extraction (this may take a few seconds)...")
        extracted_json = gemini_extractor.extract_recipe_from_pdf(pdf_bytes, test_file['name'])

        print("\n✨ SUCCESS! Extracted JSON Result:")
        print(json.dumps(extracted_json, indent=2))

        # 5. Engineering Check: Validation
        print("\n🧪 Logic Check:")
        if "ingredients" in extracted_json and len(extracted_json["ingredients"]) > 0:
            print(f"✅ Ingredients found: {len(extracted_json['ingredients'])}")
        else:
            print("⚠️ Warning: No ingredients extracted.")

    except Exception as e:
        print(f"❌ Brain Failure: {e}")


if __name__ == "__main__":
    test_single_extraction()