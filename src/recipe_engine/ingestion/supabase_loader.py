import os
from supabase import create_client, Client

# Initialize once
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(url, key)


def save_to_supabase(extracted_data, file_name):
    print(f"💾 Vault: Saving '{file_name}'...")

    # We map the dictionary keys directly to our Table columns
    result = supabase.table("recipes").insert({
        "title": extracted_data['title'],
        "category": extracted_data['category'],
        "prep_time_min": extracted_data.get('prep_time_min'),
        "cook_time_min": extracted_data.get('cook_time_min'),
        "servings": extracted_data.get('servings'),
        "ingredients": extracted_data['ingredients'],  # JSONB
        "instructions": extracted_data['instructions'],  # JSONB
        "content_hash": extracted_data.get('content_hash'),
        "source_type": extracted_data.get('source_type'),
        "google_drive_id": extracted_data.get('google_drive_id'),
        "source_url": extracted_data.get('source_url'),
        "user_notes": extracted_data.get('user_notes', None),
        "tags": extracted_data.get('tags', []),
        "is_draft": True,
        "uploader_name": "Automatic Pipeline",
        "image_urls": extracted_data.get("image_urls"), # JSONB
        "user_comments": f"Original scan: {file_name}"
    }).execute()

    return result