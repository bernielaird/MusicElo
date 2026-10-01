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
