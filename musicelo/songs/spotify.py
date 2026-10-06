"""Helpers for looking up tracks with the Spotify Web API."""

import logging
import re
from functools import cache
from urllib.parse import urlparse

import spotipy
from spotipy.cache_handler import CacheHandler, MemoryCacheHandler
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

logger = logging.getLogger(__name__)

ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")
KINDS = ("track", "playlist")

# Read-only access to the user's library, top tracks and playlists.
SCOPES = (
    "user-library-read",
    "user-top-read",
    "playlist-read-private",
    "playlist-read-collaborative",
)
TOP_TRACK_RANGES = ("short_term", "medium_term", "long_term")


def parse_spotify_url(value):
    """Extract the kind and ID from a Spotify track or playlist URL or URI.

    Accepts links like https://open.spotify.com/track/<id>?si=...,
    localized links like https://open.spotify.com/intl-de/playlist/<id>,
    and URIs like spotify:track:<id>. Returns a (kind, id) tuple, where kind
    is "track" or "playlist", or None for anything else.
    """
    value = value.strip()
    if value.startswith("spotify:"):
        parts = value.split(":")[1:]
    else:
        parsed = urlparse(value)
        if parsed.netloc != "open.spotify.com":
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[0].startswith("intl-"):
            parts = parts[1:]

    if len(parts) < 2 or parts[0] not in KINDS or not ID_RE.match(parts[1]):
        return None
    return parts[0], parts[1]


def parse_track_id(value):
    """Extract the track ID from a Spotify track URL or URI, or None."""
    result = parse_spotify_url(value)
    if result is None or result[0] != "track":
        return None
    return result[1]


@cache
def _client():
    # Credentials come from the SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET env vars.
    # The token is kept in memory so spotipy doesn't write a .cache file to disk.
    return spotipy.Spotify(
        client_credentials_manager=SpotifyClientCredentials(
            cache_handler=MemoryCacheHandler()
        )
    )


class AccountCacheHandler(CacheHandler):
    """Stores a user's OAuth token on their SpotifyAccount instead of in a file."""

    def __init__(self, account):
        self.account = account

    def get_cached_token(self):
        return self.account.token_info or None

    def save_token_to_cache(self, token_info):
        self.account.token_info = token_info
        self.account.save(update_fields=["token_info"])


def _oauth(cache_handler=None, state=None):
    # Credentials and redirect URI come from the SPOTIPY_CLIENT_ID,
    # SPOTIPY_CLIENT_SECRET and SPOTIPY_REDIRECT_URI env vars.
    return SpotifyOAuth(
        scope=SCOPES,
        state=state,
        cache_handler=cache_handler or MemoryCacheHandler(),
        open_browser=False,
    )


def authorize_url(state):
    """The Spotify login page URL that starts the account connection flow."""
    return _oauth(state=state).get_authorize_url()


def exchange_code(code):
    """Trade an authorization code for tokens.

    Returns a (token_info, profile) tuple, where profile is the user's Spotify
    profile, or None if the exchange fails.
    """
    cache = MemoryCacheHandler()
    try:
        _oauth(cache).get_access_token(code, as_dict=False, check_cache=False)
        token_info = cache.get_cached_token()
        profile = spotipy.Spotify(auth=token_info["access_token"]).me()
    except Exception:
        logger.exception("Spotify authorization code exchange failed")
        return None
    return token_info, profile


def user_client(account):
    """A Spotify client that acts as the account's user, refreshing its token as needed."""
    return spotipy.Spotify(auth_manager=_oauth(AccountCacheHandler(account)))


def fetch_track(track_id):
    """Fetch a track's metadata as a dict of Song fields, or None if the lookup fails."""
    try:
        track = _client().track(track_id)
    except Exception:
        logger.exception("Spotify lookup failed for track %s", track_id)
        return None

    return _song_fields(track)


def fetch_playlist_tracks(playlist_id, account=None):
    """Fetch every track in a playlist as a list of Song field dicts, or None if the lookup fails.

    With a SpotifyAccount, the lookup runs as that user, so their private
    playlists work too. Podcast episodes, local files and unavailable tracks
    are skipped.
    """
    try:
        client = user_client(account) if account else _client()
        page = client.playlist_items(playlist_id, additional_types=("track",))
        # Newer API responses name the track field "item"; older ones use "track".
        return _collect_tracks(
            client, page, lambda entry: entry.get("item") or entry.get("track")
        )
    except Exception:
        logger.exception("Spotify lookup failed for playlist %s", playlist_id)
        return None


def fetch_saved_tracks(account):
    """Fetch the user's Liked Songs as a list of Song field dicts, or None if the lookup fails."""
    try:
        client = user_client(account)
        page = client.current_user_saved_tracks(limit=50)
        return _collect_tracks(client, page, lambda entry: entry.get("track"))
    except Exception:
        logger.exception("Spotify lookup failed for saved tracks of %s", account)
        return None


def fetch_top_tracks(account, time_range="medium_term"):
    """Fetch the user's top 50 tracks as a list of Song field dicts, or None if the lookup fails.

    time_range is one of TOP_TRACK_RANGES: roughly the last 4 weeks,
    6 months, or year.
    """
    try:
        client = user_client(account)
        page = client.current_user_top_tracks(limit=50, time_range=time_range)
        return _collect_tracks(client, page, lambda track: track)
    except Exception:
        logger.exception("Spotify lookup failed for top tracks of %s", account)
        return None


def fetch_user_playlists(account):
    """Fetch the playlists in the user's library, or None if the lookup fails.

    Each playlist is a dict with id, name, owner, image and track_count.
    """
    playlists = []
    try:
        client = user_client(account)
        page = client.current_user_playlists(limit=50)
        while page:
            for playlist in page["items"]:
                if not playlist:
                    continue
                images = playlist.get("images") or []
                # Newer API responses name the track summary "items"; older ones use "tracks".
                summary = playlist.get("items") or playlist.get("tracks") or {}
                playlists.append({
                    "id": playlist["id"],
                    "name": playlist["name"],
                    "owner": (playlist.get("owner") or {}).get("display_name") or "",
                    "image": images[0]["url"] if images else "",
                    "track_count": summary.get("total"),
                })
            page = client.next(page) if page.get("next") else None
    except Exception:
        logger.exception("Spotify lookup failed for playlists of %s", account)
        return None
    return playlists


def _collect_tracks(client, page, get_track):
    """Follow a paged response and return its tracks as Song field dicts.

    get_track pulls the track object out of each item in the page.
    """
    tracks = []
    while page:
        for entry in page["items"]:
            track = get_track(entry) if entry else None
            if (
                track
                and track.get("type") == "track"
                and not track.get("is_local")
                and track.get("id")
            ):
                tracks.append(_song_fields(track))
        page = client.next(page) if page.get("next") else None
    return tracks


def _song_fields(track):
    images = track["album"]["images"]
    return {
        "name": track["name"],
        "artist": track["artists"][0]["name"],
        "album": track["album"]["name"],
        "coverart": images[0]["url"] if images else "",
        "uri": track["uri"],
    }
