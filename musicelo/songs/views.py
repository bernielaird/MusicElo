from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Rating, Song
import os
import math
from django.views import generic
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials



class IndexView(generic.ListView):
    template_name = "songs/index.html"
    context_object_name = "Song_List"
    
    def get_queryset(self):
        """Return the last five published questions."""
        return Song.objects.order_by("name")

def songlist(request):
    Song_List = Song.objects.order_by("name")
    context = {"Song_List": Song_List}
    return render(request, "songs/songlist.html", context)

def ratinglist(request):
    Rating_List = Rating.objects.filter(user = request.user.id).order_by("-value")
    context = {"Rating_List": Rating_List}
    return render(request, "songs/ratinglist.html", context)

def add(request,):
    if request.method == 'POST':
        spotifyurl = request.POST.get('spotifyurl')
        spotifyid = spotifyurl.split("/")[4].split("?")[0]
    song = addsong(spotifyid)
    if song != "Nothing Added":
        addrating(request, song)
    return redirect("/songs/ratinglist")


def addsong(lz_uri):
    spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())
    track = spotify.track(lz_uri)
    for song in Song.objects.order_by("name"):
        if song.name == track['name']:
            return "Nothing Added"

    Song.objects.create(
        name = track['name'],
        album = track['album']['name'],
        artist = track['artists'][0]['name'],
        coverart = track['album']['images'][0]['url'],
        uri = track['uri'],
    )
    return track['name']

def addrating(request, song):
    Rating.objects.create(
        user_id = request.user.id,
        song_id = Song.objects.filter(name = song).first().id,
        value = 1500,
    )

def versus(request):
    #TODO: JUST PASS RATING OBJECT TO IT AND PART THROUGH IT IN HTML
    ratings = list(Rating.objects.filter(user = request.user.id).order_by("value"))
    random_ratings = random.sample(ratings, 2)
    context = {"firstsong": random_ratings[0].song.name, "secondsong": random_ratings[1].song.name,
               "firstartist": random_ratings[0].song.artist, "secondartist": random_ratings[1].song.artist,
               "firstscore": int(random_ratings[0].value), "secondscore": int(random_ratings[1].value),
               "firsturi": random_ratings[0].song.uri.split(':')[2], "seconduri": random_ratings[1].song.uri.split(':')[2],
               "firstid": random_ratings[0].id, "secondid": random_ratings[1].id,
               "firstimage": random_ratings[0].song.coverart,"secondimage": random_ratings[1].song.coverart}
    return render(request, "songs/versus.html", context)

def versus_edit(request, first,second):
    
    def Probability(rating1, rating2):
        return 1.0 * 1.0 / (1 + 1.0 * math.pow(10, 1.0 * (rating1 - rating2) / 400))
    
    def EloRating(first, second):
        Ra, Rb = Rating.objects.filter(id = first).first().value, Rating.objects.filter(id = second).first().value
        K = 30
        Pb = Probability(Ra, Rb)
        Pa = Probability(Rb, Ra)
    
        Ra = Ra + K * (1 - Pa)
        Rb = Rb + K * (0 - Pb)
    
        Rating.objects.filter(id = first).update(value = Ra)
        Rating.objects.filter(id = second).update(value = Rb)

    EloRating(first,second)

    context = {"firstsong": Rating.objects.filter(id = first).first().song, "secondsong": Rating.objects.filter(id = second).first().song,
               "firstvalue": Rating.objects.filter(id = first).first().value, "secondvalue": Rating.objects.filter(id = second).first().value}
    return redirect("/songs/versus")