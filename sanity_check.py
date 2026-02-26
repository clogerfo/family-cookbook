import os
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client
from dotenv import load_dotenv

# 1. Load Environment Variables
load_dotenv()


def check_env_vars():
    print("🔍 Checking Environment Variables...")
    required = ["SUPABASE_URL", "SUPABASE_KEY", "GEMINI_API_KEY", "RECIPE_FOLDER_ID"]
    missing = [var for var in required if not os.environ.get(var)]

    if missing:
        print(f"❌ Missing keys in .env: {', '.join(missing)}")
        return False
    print("✅ All environment variables present.")
    return True


def check_supabase():
    print("\n⚡ Testing Supabase Connection...")
    try:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        # Attempt to reach the table
        supabase.table("recipes").select("id").limit(1).execute()
        print("✅ Supabase connection successful.")
    except Exception as e:
        print(f"❌ Supabase Error: {e}")


def check_google_drive():
    print("\n📂 Testing Google Drive Access...")
    if not os.path.exists('token.json'):
        print("❌ token.json not found. Run your authentication flow first.")
        return
    try:
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/drive.readonly'])
        service = build('drive', 'v3', credentials=creds)
        # Check folder accessibility
        folder_id = os.environ["RECIPE_FOLDER_ID"]
        service.files().get(fileId=folder_id).execute()
        print("✅ Google Drive folder is accessible.")
    except Exception as e:
        print(f"❌ Google Drive Error: {e}")


def check_gemini():
    print("\n🧠 Testing Gemini API...")
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.0-flash')
        # Simple test prompt
        response = model.generate_content("Say 'Gemini is online' if you can read this.")
        print(f"✅ Gemini Response: {response.text.strip()}")
    except Exception as e:
        print(f"❌ Gemini Error: {e}")


if __name__ == "__main__":
    if check_env_vars():
        check_supabase()
        check_google_drive()
        check_gemini()
        print("\n🏁 Sanity Check Complete.")