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
from .models import Rating, Song


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
    tracks = spotify.fetch_playlist_tracks(playlist_id)
    if tracks is None:
        messages.error(
            request,
            "Couldn't load that playlist from Spotify. Make sure it's public and try again.",
        )
        return
    if not tracks:
        messages.info(request, "That playlist doesn't have any songs to add.")
        return

    # A playlist can list the same track more than once; keep the first copy.
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
        message = f"Added {added} song{'s' if added != 1 else ''} from the playlist."
        if skipped:
            message += f" {skipped} {'were' if skipped != 1 else 'was'} already in your list."
        messages.success(request, message)
    else:
        messages.info(request, "Every song in that playlist is already in your list.")


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
