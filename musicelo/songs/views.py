import secrets

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import spotify
from .elo import update_ratings
from .models import Rating, Song, SpotifyAccount

TOP_TRACK_LABELS = {
    "short_term": "your top tracks from the last 4 weeks",
    "medium_term": "your top tracks from the last 6 months",
    "long_term": "your top tracks from the last year",
}


def index(request):
    return render(request, "songs/index.html")


def signup(request):
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("songs:add")
    return render(request, "songs/signup.html", {"form": form})


@login_required
def song_list(request):
    ratings = (
        Rating.objects.filter(user=request.user)
        .select_related("song")
        .order_by("-value")
    )
    return render(request, "songs/songlist.html", {"ratings": ratings})


@login_required
def add_song(request):
    if request.method != "POST":
        return render(request, "songs/add.html")

    parsed = spotify.parse_spotify_url(request.POST.get("spotifyurl", ""))
    if parsed is None:
        messages.error(request, "Please enter a valid Spotify track or playlist URL.")
        return redirect("songs:add")

    kind, spotify_id = parsed
    if kind == "playlist":
        add_playlist(request, spotify_id)
        return redirect("songs:add")

    song = get_or_create_song(spotify_id)
    if song is None:
        messages.error(request, "Couldn't load that track from Spotify. Please try again.")
        return redirect("songs:add")

    _, created = Rating.objects.get_or_create(user=request.user, song=song)
    if created:
        messages.success(request, f"Added {song.name} by {song.artist}.")
    else:
        messages.info(request, f"{song.name} is already in your list.")
    return redirect("songs:add")


def add_playlist(request, playlist_id):
    """Add every track in a Spotify playlist to the user's list."""
    account = SpotifyAccount.objects.filter(user=request.user).first()
    tracks = spotify.fetch_playlist_tracks(playlist_id, account)
    if tracks is None:
        if account:
            error = "Couldn't load that playlist from Spotify. Please try again."
        else:
            error = (
                "Couldn't load that playlist from Spotify. Make sure it's public "
                "and try again, or connect your Spotify account to add private playlists."
            )
        messages.error(request, error)
        return
    add_tracks(request, tracks, "the playlist")


def add_tracks(request, tracks, source):
    """Add a list of Song field dicts to the user's list and report the result.

    source describes where the tracks came from, e.g. "the playlist".
    """
    if not tracks:
        messages.info(request, f"There aren't any songs to add from {source}.")
        return

    # A source can list the same track more than once; keep the first copy.
    tracks_by_uri = {track["uri"]: track for track in reversed(tracks)}
    uris = list(tracks_by_uri)

    with transaction.atomic():
        Song.objects.bulk_create(
            [Song(**track) for track in tracks_by_uri.values()], ignore_conflicts=True
        )
        songs = Song.objects.filter(uri__in=uris)
        already_rated = set(
            Rating.objects.filter(user=request.user, song__in=songs).values_list(
                "song_id", flat=True
            )
        )
        new_ratings = [
            Rating(user=request.user, song=song)
            for song in songs
            if song.id not in already_rated
        ]
        Rating.objects.bulk_create(new_ratings, ignore_conflicts=True)

    added, skipped = len(new_ratings), len(already_rated)
    if added:
        message = f"Added {added} song{'s' if added != 1 else ''} from {source}."
        if skipped:
            message += f" {skipped} {'were' if skipped != 1 else 'was'} already in your list."
        messages.success(request, message)
    else:
        messages.info(request, f"Every song from {source} is already in your list.")


def get_or_create_song(track_id):
    """Return the Song for a Spotify track ID, fetching it from Spotify if it's new."""
    song = Song.objects.filter(uri=f"spotify:track:{track_id}").first()
    if song:
        return song

    track = spotify.fetch_track(track_id)
    if track is None:
        return None
    song, _ = Song.objects.get_or_create(uri=track["uri"], defaults=track)
    return song


@login_required
def versus(request):
    pair = list(
        Rating.objects.filter(user=request.user)
        .select_related("song")
        .order_by("?")[:2]
    )
    if len(pair) < 2:
        messages.info(request, "Add at least two songs to start comparing.")
        return redirect("songs:add")

    first, second = pair
    return render(request, "songs/versus.html", {"first": first, "second": second})


@login_required
@require_POST
def vote(request, winner_id, loser_id):
    if winner_id == loser_id:
        return HttpResponseBadRequest("A song can't play against itself.")

    with transaction.atomic():
        user_ratings = Rating.objects.select_for_update().filter(user=request.user)
        winner = get_object_or_404(user_ratings, id=winner_id)
        loser = get_object_or_404(user_ratings, id=loser_id)

        winner.value, loser.value = update_ratings(winner.value, loser.value)
        winner.save(update_fields=["value"])
        loser.save(update_fields=["value"])

    return redirect("songs:versus")


@login_required
def spotify_account(request):
    """Show the user's Spotify connection and what they can import from it."""
    account = SpotifyAccount.objects.filter(user=request.user).first()
    playlists = None
    if account:
        playlists = spotify.fetch_user_playlists(account)
        if playlists is None:
            messages.error(
                request,
                "Couldn't load your playlists from Spotify. "
                "Try disconnecting and connecting your account again.",
            )
    return render(
        request,
        "songs/spotify.html",
        {"account": account, "playlists": playlists, "top_ranges": TOP_TRACK_LABELS},
    )


@login_required
@require_POST
def spotify_connect(request):
    """Send the user to Spotify to approve access to their account."""
    state = secrets.token_urlsafe(32)
    request.session["spotify_oauth_state"] = state
    return redirect(spotify.authorize_url(state))


@login_required
def spotify_callback(request):
    """Finish connecting after Spotify redirects back with an authorization code."""
    expected_state = request.session.pop("spotify_oauth_state", None)
    if not expected_state or request.GET.get("state") != expected_state:
        messages.error(request, "That Spotify sign-in link has expired. Please try again.")
        return redirect("songs:spotify")

    if "error" in request.GET or "code" not in request.GET:
        messages.info(request, "Spotify account not connected.")
        return redirect("songs:spotify")

    result = spotify.exchange_code(request.GET["code"])
    if result is None:
        messages.error(request, "Couldn't connect to Spotify. Please try again.")
        return redirect("songs:spotify")

    token_info, profile = result
    account, _ = SpotifyAccount.objects.update_or_create(
        user=request.user,
        defaults={
            "spotify_id": profile["id"],
            "display_name": profile.get("display_name") or "",
            "token_info": token_info,
        },
    )
    messages.success(
        request, f"Connected Spotify account {account.display_name or account.spotify_id}."
    )
    return redirect("songs:spotify")


@login_required
@require_POST
def spotify_disconnect(request):
    SpotifyAccount.objects.filter(user=request.user).delete()
    messages.success(request, "Disconnected your Spotify account.")
    return redirect("songs:spotify")


@login_required
@require_POST
def spotify_import(request):
    """Import Liked Songs, top tracks or a playlist from the connected account."""
    account = SpotifyAccount.objects.filter(user=request.user).first()
    if account is None:
        messages.error(request, "Connect your Spotify account first.")
        return redirect("songs:spotify")

    source = request.POST.get("source")
    if source == "liked":
        tracks, label = spotify.fetch_saved_tracks(account), "your Liked Songs"
    elif source == "top" and request.POST.get("time_range") in TOP_TRACK_LABELS:
        time_range = request.POST["time_range"]
        tracks, label = spotify.fetch_top_tracks(account, time_range), TOP_TRACK_LABELS[time_range]
    elif source == "playlist" and spotify.ID_RE.match(request.POST.get("playlist_id", "")):
        tracks = spotify.fetch_playlist_tracks(request.POST["playlist_id"], account)
        label = "the playlist"
    else:
        return HttpResponseBadRequest("Unknown import source.")

    if tracks is None:
        messages.error(request, f"Couldn't load {label} from Spotify. Please try again.")
    else:
        add_tracks(request, tracks, label)
    return redirect("songs:spotify")
