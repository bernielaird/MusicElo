"""Helpers for looking up tracks with the Spotify Web API."""

import logging
import re
from functools import cache
from urllib.parse import urlparse

import spotipy
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyClientCredentials

logger = logging.getLogger(__name__)

ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")
KINDS = ("track", "playlist")


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


def fetch_track(track_id):
    """Fetch a track's metadata as a dict of Song fields, or None if the lookup fails."""
    try:
        track = _client().track(track_id)
    except Exception:
        logger.exception("Spotify lookup failed for track %s", track_id)
        return None

    return _song_fields(track)


def fetch_playlist_tracks(playlist_id):
    """Fetch every track in a playlist as a list of Song field dicts, or None if the lookup fails.

    Podcast episodes, local files and unavailable tracks are skipped.
    """
    tracks = []
    try:
        client = _client()
        page = client.playlist_items(playlist_id, additional_types=("track",))
        while page:
            for entry in page["items"]:
                # Newer API responses name this field "item"; older ones use "track".
                track = entry.get("item") or entry.get("track")
                if (
                    track
                    and track.get("type") == "track"
                    and not track.get("is_local")
                    and track.get("id")
                ):
                    tracks.append(_song_fields(track))
            page = client.next(page) if page.get("next") else None
    except Exception:
        logger.exception("Spotify lookup failed for playlist %s", playlist_id)
        return None
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
