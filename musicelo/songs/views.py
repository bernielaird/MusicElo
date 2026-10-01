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

    track_id = spotify.parse_track_id(request.POST.get("spotifyurl", ""))
    if track_id is None:
        messages.error(request, "Please enter a valid Spotify track URL.")
        return redirect("songs:add")

    song = get_or_create_song(track_id)
    if song is None:
        messages.error(request, "Couldn't load that track from Spotify. Please try again.")
        return redirect("songs:add")

    _, created = Rating.objects.get_or_create(user=request.user, song=song)
    if created:
        messages.success(request, f"Added {song.name} by {song.artist}.")
    else:
        messages.info(request, f"{song.name} is already in your list.")
    return redirect("songs:add")


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
