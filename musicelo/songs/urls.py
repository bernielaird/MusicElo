from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "songs"

urlpatterns = [
    path("", views.index, name="index"),
    path("songlist/", views.song_list, name="songlist"),
    path("add/", views.add_song, name="add"),
    path("versus/", views.versus, name="versus"),
    path("versus/<int:winner_id>/<int:loser_id>/", views.vote, name="vote"),
    path("spotify/", views.spotify_account, name="spotify"),
    path("spotify/connect/", views.spotify_connect, name="spotify_connect"),
    path("spotify/disconnect/", views.spotify_disconnect, name="spotify_disconnect"),
    path("spotify/import/", views.spotify_import, name="spotify_import"),
    # Must match SPOTIPY_REDIRECT_URI and a redirect URI registered on the Spotify app.
    path("callback/", views.spotify_callback, name="spotify_callback"),
    path("signup/", views.signup, name="signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="songs/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
