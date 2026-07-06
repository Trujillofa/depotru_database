"""
Vanna AI Integration for SmartBusiness Database
================================================
Chat with your database using natural language!

Instead of writing SQL or running complex scripts, just ask questions like:
- "What are my top 10 selling products?"
- "Show me revenue by category this month"
- "Which customers have the highest order values?"
- "What's my profit margin by product?"

This uses Vanna AI to convert your questions into SQL queries automatically.

Setup Options:
1. Cloud (Easy): Use OpenAI/Anthropic/Grok API with Vanna or ChromaDB
2. Local (Private): Use Ollama + ChromaDB (runs entirely on your machine)

Requirements:
- pip install vanna
- pip install pyodbc (for SQL Server)
- Optional: pip install chromadb ollama (for local setup)

Usage:
    python vanna_chat.py

Then open http://localhost:8084 in your browser and start asking questions!
"""

import os

from src.vanna_integration import ProviderSettings, VannaService, create_vanna_provider

# ============================================================================
# CONFIGURATION - CHOOSE YOUR SETUP
# ============================================================================

# Option 1: Use OpenAI (Recommended for best results)
USE_OPENAI = True
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key")

# Option 2: Use local Ollama (Free, runs on your machine)
USE_OLLAMA = False
OLLAMA_MODEL = "mistral"  # or "llama2", "codellama"

# Option 3: Use Anthropic Claude
USE_ANTHROPIC = False
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-api-key")

# Option 4: Use Grok (xAI)
USE_GROK = False
GROK_API_KEY = os.getenv("GROK_API_KEY", "your-grok-api-key")

# Database connection (your SmartBusiness SQL Server)
DB_SERVER = os.getenv("DB_SERVER", "your-server")
DB_NAME = os.getenv("DB_NAME", "SmartBusiness")
DB_USER = os.getenv("DB_USER", "your-username")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your-password")

# ============================================================================
# SETUP VANNA
# ============================================================================


def create_vanna_instance():
    settings = ProviderSettings(
        use_openai=USE_OPENAI,
        use_ollama=USE_OLLAMA,
        use_anthropic=USE_ANTHROPIC,
        use_grok=USE_GROK,
        openai_api_key=OPENAI_API_KEY,
        ollama_model=OLLAMA_MODEL,
        anthropic_api_key=ANTHROPIC_API_KEY,
        grok_api_key=GROK_API_KEY,
    )
    return create_vanna_provider(settings)


def connect_to_database(vn):
    return VannaService(vn).connect_to_mssql(
        db_server=DB_SERVER,
        db_name=DB_NAME,
        db_user=DB_USER,
        db_password=DB_PASSWORD,
    )


def train_vanna_on_schema(vn):
    return VannaService(vn).train_on_schema()


def run_chat_interface(vn):
    """Launch the web-based chat interface"""

    from vanna.flask import VannaFlaskApp  # pyright: ignore[reportMissingImports]

    print("\n" + "=" * 60)
    print("🚀 STARTING VANNA CHAT INTERFACE")
    print("=" * 60)
    print()
    print("Open your browser and go to: http://localhost:8084")
    print()
    print("Try asking questions like:")
    print("  • What are my top 10 selling products?")
    print("  • Show me revenue by category")
    print("  • Which customers have the highest order values?")
    print("  • What's my profit margin by product category?")
    print("  • Show me monthly revenue trends")
    print("  • Which products have low profit margins?")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)

    # Create and run Flask app
    app = VannaFlaskApp(vn, allow_llm_to_see_data=True)
    app.run(port=8084)


def main():
    """Main entry point"""
    print("=" * 60)
    print("VANNA AI - Chat with Your SmartBusiness Database")
    print("=" * 60)
    print()

    # Check for required environment variables
    if USE_OPENAI and OPENAI_API_KEY == "your-openai-api-key":
        print("⚠️  WARNING: Set your OPENAI_API_KEY environment variable")
        print("   export OPENAI_API_KEY='sk-...'")
        print()

    if USE_GROK and GROK_API_KEY == "your-grok-api-key":
        print("⚠️  WARNING: Set your GROK_API_KEY environment variable")
        print("   export GROK_API_KEY='xai-...'")
        print()

    # Create Vanna instance
    print("[1/4] Creating Vanna instance...")
    vn = create_vanna_instance()
    print("✓ Vanna instance created!")

    # Connect to database
    print("\n[2/4] Connecting to database...")
    vn = connect_to_database(vn)

    # Train on schema
    print("\n[3/4] Training on database schema...")
    vn = train_vanna_on_schema(vn)

    # Run chat interface
    print("\n[4/4] Starting chat interface...")
    run_chat_interface(vn)


if __name__ == "__main__":
    main()
