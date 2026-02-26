# 🍲 The Logerfo & Keenoy Family Cookbook

A digital heritage archive for preserving family recipes. This system digitizes handwritten notes, imports web recipes, and presents them in a searchable, mobile-friendly app.

![Status](https://img.shields.io/badge/Status-Production-green)
![Stack](https://img.shields.io/badge/Stack-Python_Streamlit_Supabase_Gemini-blue)

## 🏗️ System Architecture

The project consists of three distinct tools:

1.  **The Orchestrator (`orchestrator.py`)**: 
    * *Role:* The "Back of House" data ingestion engine.
    * *Function:* Scans Google Drive for new PDFs and accepts URLs. Uses Gemini 2.0 to extract structured data (ingredients, steps) and handles de-duplication via SHA-256 hashing.
    
2.  **The Editor (`dashboard.py`)**: 
    * *Role:* The "Staging Area."
    * *Function:* A Streamlit interface to review AI extractions, fix typos, assign family tags (Logerfo/Keenoy), and credit the original chef before publishing.

3.  **The App (`app.py`)**: 
    * *Role:* The "Family Experience."
    * *Function:* A read-only, mobile-optimized web app for cooking. Features semantic search, family filters, and a high-contrast reading mode.

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.10+
* A Supabase project (Database)
* Google Cloud Service Account (Drive API)
* Google Gemini API Key

### 2. Installation
```bash
# Clone repository
git clone [https://github.com/yourusername/family-cookbook.git](https://github.com/yourusername/family-cookbook.git)

# Install dependencies
pip install -r requirements.txt