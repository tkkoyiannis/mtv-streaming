from flask import Flask, render_template, request, jsonify
import requests
from config import (
    SECRET_KEY,
    DEBUG,
    HOST,
    PORT,
    TMDB_API_KEY,
    ENABLE_VIDSRC_TO,
    ENABLE_VIDSRC_ME,
    ENABLE_SUPEREMBED,
    ENABLE_2EMBED
)
import logging
from functools import wraps
import time
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY


def rate_limit(max_requests=60, window=60):
    """Simple rate limiting decorator"""
    requests_log = {}

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            current_time = time.time()

            if client_ip not in requests_log:
                requests_log[client_ip] = []

            # Clean old requests
            requests_log[client_ip] = [
                req_time
                for req_time in requests_log[client_ip]
                if current_time - req_time < window
            ]

            if len(requests_log[client_ip]) >= max_requests:
                return jsonify({"error": "Rate limit exceeded"}), 429

            requests_log[client_ip].append(current_time)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


class StreamAggregator:
    def __init__(self):
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.tmdb_api_key = TMDB_API_KEY
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Personal Stream Aggregator 1.0"})

    def search_tmdb(self, query, media_type="multi"):
        """Search TMDb for movies/TV shows with better error handling"""
        url = f"{self.tmdb_base_url}/search/{media_type}"
        params = {
            "api_key": self.tmdb_api_key,
            "query": query,
            "language": "en-US",
            "page": 1,
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Filter out adult content
            if "results" in data:
                data["results"] = [
                    item for item in data["results"] if not item.get("adult", False)
                ]

            return data
        except requests.RequestException as e:
            logger.error(f"TMDb search error: {e}")
            return {"results": []}

    def get_movie_details(self, movie_id):
        """Get detailed movie information"""
        url = f"{self.tmdb_base_url}/movie/{movie_id}"
        params = {
            "api_key": self.tmdb_api_key,
            "append_to_response": "external_ids,videos,credits",
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Movie details error: {e}")
            return None

    def get_tv_details(self, tv_id):
        """Get detailed TV show information"""
        url = f"{self.tmdb_base_url}/tv/{tv_id}"
        params = {
            "api_key": self.tmdb_api_key,
            "append_to_response": "external_ids,videos,credits",
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"TV details error: {e}")
            return None

    def get_season_episodes(self, tv_id, season_number):
        """Get episodes for a specific season"""
        url = f"{self.tmdb_base_url}/tv/{tv_id}/season/{season_number}"
        params = {"api_key": self.tmdb_api_key}

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("episodes", [])
        except requests.RequestException as e:
            logger.error(f"Episodes error: {e}")
            return []

    # NEW: Get suggestions by genre
    def get_suggestions_by_genre(self, genre):
        """Get random suggestions for a specific genre"""
        try:
            suggestions = []

            if genre == "trending":
                # Get trending content
                movie_response = self.session.get(
                    f"{self.tmdb_base_url}/trending/movie/day?api_key={self.tmdb_api_key}",
                    timeout=10,
                )
                tv_response = self.session.get(
                    f"{self.tmdb_base_url}/trending/tv/day?api_key={self.tmdb_api_key}",
                    timeout=10,
                )

                if movie_response.status_code == 200 and tv_response.status_code == 200:
                    movies = movie_response.json()["results"][:8]
                    tv_shows = tv_response.json()["results"][:8]

                    # Add media_type to distinguish between movies and TV shows
                    for movie in movies:
                        movie["media_type"] = "movie"
                    for tv in tv_shows:
                        tv["media_type"] = "tv"

                    suggestions = movies + tv_shows
            else:
                # Genre mapping
                genre_map = {
                    "action": {"movie": 28, "tv": 10759},
                    "comedy": {"movie": 35, "tv": 35},
                    "drama": {"movie": 18, "tv": 18},
                    "horror": {"movie": 27, "tv": 9648},
                    "sci-fi": {"movie": 878, "tv": 10765},
                }

                if genre in genre_map:
                    movie_genre_id = genre_map[genre]["movie"]
                    tv_genre_id = genre_map[genre]["tv"]

                    # Get movies and TV shows by genre
                    movie_response = self.session.get(
                        f"{self.tmdb_base_url}/discover/movie?api_key={self.tmdb_api_key}"
                        f"&with_genres={movie_genre_id}&sort_by=popularity.desc&page=1",
                        timeout=10,
                    )
                    tv_response = self.session.get(
                        f"{self.tmdb_base_url}/discover/tv?api_key={self.tmdb_api_key}&"
                        f"with_genres={tv_genre_id}&sort_by=popularity.desc&page=1",
                        timeout=10,
                    )

                    if (
                        movie_response.status_code == 200
                        and tv_response.status_code == 200
                    ):
                        movies = movie_response.json()["results"][:8]
                        tv_shows = tv_response.json()["results"][:8]

                        # Add media_type to distinguish between movies and TV shows
                        for movie in movies:
                            movie["media_type"] = "movie"
                        for tv in tv_shows:
                            tv["media_type"] = "tv"

                        suggestions = movies + tv_shows

            # Filter out adult content
            suggestions = [item for item in suggestions if not item.get("adult", False)]

            # Shuffle and limit results
            random.shuffle(suggestions)
            suggestions = suggestions[:12]

            return suggestions

        except Exception as e:
            logger.error(f"Error getting suggestions for genre {genre}: {e}")
            return []

    def get_streaming_sources(
        self, imdb_id, media_type="movie", season=None, episode=None
    ):
        """Get streaming sources from various providers"""
        sources = []

        # Clean IMDb ID
        imdb_id = imdb_id.replace("tt", "") if imdb_id.startswith("tt") else imdb_id
        imdb_id = f"tt{imdb_id}"

        # VidSrc.to
        if ENABLE_VIDSRC_TO:
            if media_type == "movie":
                vidsrc_url = f"https://vidsrc.to/embed/movie/{imdb_id}"
            else:
                vidsrc_url = f"https://vidsrc.to/embed/tv/{imdb_id}/{season}/{episode}"

            sources.append(
                {
                    "name": "VidSrc.to",
                    "url": vidsrc_url,
                    "quality": "HD",
                    "subtitles": True,
                    "type": "iframe",
                }
            )

        # VidSrc.me
        if ENABLE_VIDSRC_ME:
            if media_type == "movie":
                vidsrc_me_url = f"https://vidsrc.me/embed/movie?imdb={imdb_id}"
            else:
                vidsrc_me_url = f"https://vidsrc.me/embed/tv?imdb={imdb_id}"
                f"&season={season}&episode={episode}"

            sources.append(
                {
                    "name": "VidSrc.me",
                    "url": vidsrc_me_url,
                    "quality": "HD",
                    "subtitles": True,
                    "type": "iframe",
                }
            )

        # SuperEmbed
        if ENABLE_SUPEREMBED:
            if media_type == "movie":
                superembed_url = (
                    f"https://multiembed.mov/directstream.php?video_id={imdb_id}"
                )
            else:
                superembed_url = f"https://multiembed.mov/directstream.php?video_id={imdb_id}&s={season}&e={episode}"

            sources.append(
                {
                    "name": "SuperEmbed",
                    "url": superembed_url,
                    "quality": "HD",
                    "subtitles": False,
                    "type": "iframe",
                }
            )

        # 2embed
        if ENABLE_2EMBED:
            if media_type == "movie":
                embed2_url = f"https://www.2embed.to/embed/imdb/movie?id={imdb_id}"
            else:
                embed2_url = f"https://www.2embed.to/embed/imdb/tv?id={imdb_id}&s={season}"
                f"&e={episode}"

            sources.append(
                {
                    "name": "2Embed",
                    "url": embed2_url,
                    "quality": "HD",
                    "subtitles": True,
                    "type": "iframe",
                }
            )

        return sources


aggregator = StreamAggregator()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
@rate_limit(max_requests=30, window=60)
def search():
    query = request.args.get("q", "").strip()
    media_type = request.args.get("type", "multi")

    if not query or len(query) < 2:
        return jsonify({"results": []})

    # Validate media_type
    if media_type not in ["multi", "movie", "tv"]:
        media_type = "multi"

    results = aggregator.search_tmdb(query, media_type)
    return jsonify(results)


# NEW: Suggestions endpoint
@app.route("/api/suggestions/<genre>")
@rate_limit(max_requests=60, window=60)
def get_suggestions(genre):
    """Get random suggestions for a specific genre"""
    try:
        # Validate genre
        valid_genres = ["trending", "action", "comedy", "drama", "horror", "sci-fi"]
        if genre not in valid_genres:
            return jsonify({"success": False, "error": "Invalid genre"}), 400

        suggestions = aggregator.get_suggestions_by_genre(genre)

        return jsonify({"success": True, "results": suggestions, "genre": genre})

    except Exception as e:
        logger.error(f"Error in suggestions endpoint: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/movie/<int:movie_id>")
@rate_limit(max_requests=60, window=60)
def get_movie(movie_id):
    details = aggregator.get_movie_details(movie_id)
    if not details:
        return jsonify({"error": "Movie not found"}), 404
    return jsonify(details)


@app.route("/api/tv/<int:tv_id>")
@rate_limit(max_requests=60, window=60)
def get_tv_show(tv_id):
    details = aggregator.get_tv_details(tv_id)
    if not details:
        return jsonify({"error": "TV show not found"}), 404
    return jsonify(details)


@app.route("/api/tv/<int:tv_id>/seasons")
@rate_limit(max_requests=60, window=60)
def get_seasons(tv_id):
    details = aggregator.get_tv_details(tv_id)
    if not details:
        return jsonify({"error": "TV show not found"}), 404

    seasons = details.get("seasons", [])
    return jsonify({"seasons": seasons})


@app.route("/api/tv/<int:tv_id>/season/<int:season_number>/episodes")
@rate_limit(max_requests=60, window=60)
def get_episodes(tv_id, season_number):
    episodes = aggregator.get_season_episodes(tv_id, season_number)
    return jsonify({"episodes": episodes})


@app.route("/api/stream", methods=["POST"])
@rate_limit(max_requests=30, window=60)
def get_stream():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400

        imdb_id = data.get("imdb_id")
        media_type = data.get("media_type", "movie")
        season = data.get("season")
        episode = data.get("episode")

        if not imdb_id:
            return jsonify({"error": "IMDb ID required"}), 400

        # Validate media type
        if media_type not in ["movie", "tv"]:
            return jsonify({"error": "Invalid media type"}), 400

        # For TV shows, season and episode are required
        if media_type == "tv" and (not season or not episode):
            return jsonify({"error": "Season and episode required for TV shows"}), 400

        sources = aggregator.get_streaming_sources(imdb_id, media_type, season, episode)

        if not sources:
            return jsonify({"error": "No streaming sources found"}), 404

        return jsonify({"sources": sources})

    except Exception as e:
        logger.error(f"Stream API error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429


if __name__ == "__main__":
    if not TMDB_API_KEY or TMDB_API_KEY == "your_tmdb_api_key_here":
        print("ERROR: Please set your TMDb API key in config.py or .env file")
        print("Get your free API key from: https://www.themoviedb.org/settings/api")
        exit(1)

    print(f"Starting Personal Stream Aggregator on {HOST}:{PORT}")
    print(f"Debug mode: {DEBUG}")
    app.run(debug=DEBUG, host=HOST, port=PORT)
