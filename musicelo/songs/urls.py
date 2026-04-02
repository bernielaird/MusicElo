from django.urls import path

from . import views

from django.contrib.auth import views as auth_views

app_name = "songs"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("songlist/", views.songlist, name="songlist"),
    path("ratinglist/", views.ratinglist, name="ratinglist"),
    path("add/", views.add, name="add"),
    path("versus/", views.versus, name="versus"),
    path("versus/<int:first>/<int:second>/", views.versus_edit, name="versus_edit"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
]