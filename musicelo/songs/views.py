from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Rating, Song
import math
from django.views import generic
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from urllib.parse import urlparse


class IndexView(generic.ListView):
    template_name = "songs/index.html"
    context_object_name = "Song_List"

    def get_queryset(self):
        return Song.objects.order_by("name")


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/login/")
    else:
        form = UserCreationForm()

    return render(request, "songs/signup.html", {"form": form})


def songlist(request):
    Song_List = Song.objects.order_by("name")
    context = {"Song_List": Song_List}
    return render(request, "songs/songlist.html", context)


@login_required
def ratinglist(request):
    Rating_List = Rating.objects.filter(user=request.user).order_by("-value")
    context = {"Rating_List": Rating_List}
    return render(request, "songs/ratinglist.html", context)


@login_required
def add(request):
    if request.method != "POST":
        return redirect("/ratinglist")

    spotifyurl = request.POST.get("spotifyurl", "").strip()

    try:
        parsed = urlparse(spotifyurl)
        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) < 2 or path_parts[0] != "track":
            return HttpResponse("Please enter a valid Spotify track URL.")

        spotifyid = path_parts[1]
    except Exception:
        return HttpResponse("Invalid Spotify URL.")

    song = addsong(spotifyid)
    if not song:
        return HttpResponse("Could not add song.")

    addrating(request, song)
    return redirect("/ratinglist")


def addsong(lz_uri):
    spotify = spotipy.Spotify(
        client_credentials_manager=SpotifyClientCredentials()
    )

    try:
        track = spotify.track(lz_uri)
    except Exception:
        return None

    existing_song = Song.objects.filter(uri=track["uri"]).first()
    if existing_song:
        return existing_song

    return Song.objects.create(
        name=track["name"],
        album=track["album"]["name"],
        artist=track["artists"][0]["name"],
        coverart=track["album"]["images"][0]["url"],
        uri=track["uri"],
    )


def addrating(request, song):
    existing_rating = Rating.objects.filter(
        user=request.user,
        song=song
    ).first()

    if existing_rating:
        return existing_rating

    return Rating.objects.create(
        user=request.user,
        song=song,
        value=1500,
    )


@login_required
def versus(request):
    ratings = list(Rating.objects.filter(user=request.user).order_by("value"))

    if len(ratings) < 2:
        return HttpResponse("You need at least 2 rated songs to use versus.")

    random_ratings = random.sample(ratings, 2)

    context = {
        "firstsong": random_ratings[0].song.name,
        "secondsong": random_ratings[1].song.name,
        "firstartist": random_ratings[0].song.artist,
        "secondartist": random_ratings[1].song.artist,
        "firstscore": int(random_ratings[0].value),
        "secondscore": int(random_ratings[1].value),
        "firsturi": random_ratings[0].song.uri.split(":")[2],
        "seconduri": random_ratings[1].song.uri.split(":")[2],
        "firstid": random_ratings[0].id,
        "secondid": random_ratings[1].id,
        "firstimage": random_ratings[0].song.coverart,
        "secondimage": random_ratings[1].song.coverart,
    }
    return render(request, "songs/versus.html", context)


@login_required
def versus_edit(request, first, second):
    def Probability(rating1, rating2):
        return 1.0 / (1 + math.pow(10, (rating1 - rating2) / 400))

    def EloRating(first_id, second_id):
        first_rating = Rating.objects.filter(id=first_id, user=request.user).first()
        second_rating = Rating.objects.filter(id=second_id, user=request.user).first()

        if not first_rating or not second_rating:
            return

        Ra = first_rating.value
        Rb = second_rating.value
        K = 30

        Pb = Probability(Ra, Rb)
        Pa = Probability(Rb, Ra)

        Ra = Ra + K * (1 - Pa)
        Rb = Rb + K * (0 - Pb)

        first_rating.value = Ra
        second_rating.value = Rb
        first_rating.save()
        second_rating.save()

    EloRating(first, second)
    return redirect("/versus")