from django.contrib.auth.models import User
from django.db import models

from .elo import INITIAL_RATING


class Song(models.Model):
    name = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    album = models.CharField(max_length=255)
    coverart = models.URLField(blank=True)
    uri = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.name} - {self.artist}"

    @property
    def track_id(self):
        """The bare Spotify track ID, e.g. for embed and open.spotify.com links."""
        return self.uri.rsplit(":", 1)[-1]


class Rating(models.Model):
    value = models.FloatField(default=INITIAL_RATING)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "song"], name="unique_rating_per_user_song"
            )
        ]

    def __str__(self):
        return f"{self.song} - {self.user}: {self.value:.0f}"
