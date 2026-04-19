import os
import json
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai  # Note the new import
from google.genai import types
from dotenv import load_dotenv # <--- Add this


# --- SCHEMA DEFINITION (The Contract) ---
class Ingredient(BaseModel):
    item: str
    qty: Optional[float]
    unit: Optional[str]
    prep_note: Optional[str]


class RecipeExtraction(BaseModel):
    title: str
    category: str
    prep_time_min: Optional[int]
    cook_time_min: Optional[int]
    servings: Optional[int]
    ingredients: List[Ingredient]
    instructions: List[str]
    tags: List[str]

    # --- NEW FIELD ---
    user_notes: Optional[str] = Field(
        default=None,
        description="Extract any handwritten notes, family stories, or margin annotations. Format as a bulleted list using '- '."
    )

# Load the .env file immediately upon import
load_dotenv()

PROMPT = f"""
Act as a professional chef and data engineer. Extract the recipe from this document.
Return ONLY a raw JSON object matching this schema:
{RecipeExtraction.schema_json()}

### CRITICAL CONSTRAINTS:
1. HERITAGE PRESERVATION: Actively scan the top, bottom, and margins for handwritten notes, tweaks, or family stories. Extract these and format them as a bulleted list in the `user_notes` field.
2. CATEGORY MAPPING: Map the recipe strictly to: breakfast, lunch, dinner, snack, bake, or experiment. If the recipe is unique or comes from a restaurant menu it is experimental.
3. FRACTION HANDLING: If you see "1 1/2", return 1.5. If you see "1/4", return 0.25.
4. ERROR HANDLING: If a field is missing (like prep_time), return null.

Return the JSON block only. No conversation.
"""

# ... (Keep your Pydantic classes Ingredient and RecipeExtraction) ...

def extract_recipe_from_pdf(file_bytes, file_name):
    # Initialize the new Client
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print(f"🧠 Brain: Analyzing '{file_name}' using 2.0 SDK...")

    # The new SDK handles the PDF and prompt in a more structured way
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            PROMPT,
            types.Part.from_bytes(data=file_bytes, mime_type="application/pdf")
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RecipeExtraction,  # DIRECT SCHEMA SUPPORT!
        ),
    )

    try:
        # The 'response.parsed' is a RecipeExtraction object.
        # We use .model_dump() to turn it into a standard dictionary.
        if response.parsed:
            return response.parsed.model_dump()

        # Fallback if the model didn't parse it automatically
        return json.loads(response.text)
    except Exception as e:
        print(f"❌ Extraction Error: {e}")
        return None


def extract_recipe_from_url(url: str):
    """Uses Gemini to parse a recipe directly from a web URL."""
    print(f"🌐 Brain: Scraping recipe from {url}...")

    # --- THE ANTI-HALLUCINATION PROMPT ---
    WEB_PROMPT = f"""
    You are a strict data extraction AI. I am providing you with a URL.
    Read the webpage at this URL and extract the recipe.

    CRITICAL RULES:
    1. EXTRACT VERBATIM: You must copy the ingredients and instruction steps EXACTLY word-for-word as they appear on the page. 
    2. DO NOT SUMMARIZE: Do not rewrite, rephrase, simplify, or edit the chef's instructions.
    3. DO NOT INVENT: If a measurement is missing, leave it out. Do not use outside knowledge.
    4. If you cannot clearly read the exact ingredients and steps because of a firewall, you MUST return null/empty.

    Original Instructions: {PROMPT}
    """

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[WEB_PROMPT, url],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RecipeExtraction,
        ),
    )

    if response.parsed:
        return response.parsed.model_dump()
    return None



def extract_recipe_from_multiple_images(image_bytes_list: list, mime_type: str = "image/jpeg"):
    """
    Extracts a single recipe from a list of image bytes (e.g., front and back of a card).
    """
    print(f"🧠 Brain: Analyzing {len(image_bytes_list)} image(s)...")

    # 1. Start the payload with your text instructions
    contents_payload = [PROMPT]
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    # 2. Append every image the user uploaded
    for img_bytes in image_bytes_list:
        contents_payload.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=contents_payload,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RecipeExtraction,
        ),
    )

    if response.parsed:
        return response.parsed.model_dump()
    return None