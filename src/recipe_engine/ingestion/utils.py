import hashlib
from src.recipe_engine.ingestion import supabase_loader

def generate_content_hash(data):
    """
    Creates a SHA-256 fingerprint.
    Accepts bytes (for PDFs/Images) or strings (for URLs).
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def is_duplicate(content_hash):
    """
    Checks Supabase to see if this fingerprint already exists.
    Returns True if duplicate, False if unique.
    """
    existing = supabase_loader.supabase.table("recipes") \
        .select("id") \
        .eq("content_hash", content_hash) \
        .execute()
    return len(existing.data) > 0


