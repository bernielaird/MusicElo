"""Helpers for looking up tracks with the Spotify Web API."""

import logging
import re
from functools import cache
from urllib.parse import urlparse

import spotipy
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyClientCredentials

logger = logging.getLogger(__name__)

TRACK_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")


def parse_track_id(value):
    """Extract the track ID from a Spotify track URL or URI.

    Accepts links like https://open.spotify.com/track/<id>?si=...,
    localized links like https://open.spotify.com/intl-de/track/<id>,
    and URIs like spotify:track:<id>. Returns None for anything else.
    """
    value = value.strip()
    if value.startswith("spotify:track:"):
        track_id = value.removeprefix("spotify:track:")
    else:
        parsed = urlparse(value)
        if parsed.netloc != "open.spotify.com":
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[0].startswith("intl-"):
            parts = parts[1:]
        if len(parts) < 2 or parts[0] != "track":
            return None
        track_id = parts[1]

    return track_id if TRACK_ID_RE.match(track_id) else None


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

    images = track["album"]["images"]
    return {
        "name": track["name"],
        "artist": track["artists"][0]["name"],
        "album": track["album"]["name"],
        "coverart": images[0]["url"] if images else "",
        "uri": track["uri"],
    }
