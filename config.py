import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# TMDb API Configuration
# Get your free API key from https://www.themoviedb.org/settings/api
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "your_tmdb_api_key_here")

# Flask Configuration
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "your_flask_secret_key")

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))

# Streaming Sources Configuration
ENABLE_VIDSRC_TO = os.getenv("ENABLE_VIDSRC_TO", "True").lower() == "true"
ENABLE_VIDSRC_ME = os.getenv("ENABLE_VIDSRC_ME", "True").lower() == "true"
ENABLE_SUPEREMBED = os.getenv("ENABLE_SUPEREMBED", "True").lower() == "true"
ENABLE_2EMBED = os.getenv("ENABLE_2EMBED", "True").lower() == "true"

# Cache Configuration (for future implementation)
CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", 3600))  # 1 hour
