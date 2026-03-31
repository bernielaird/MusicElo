from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Song(models.Model):
    name = models.CharField(max_length=100)
    artist = models.CharField(max_length=100)
    album = models.CharField(max_length=100)
    coverart = models.CharField(max_length=100)
    uri = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    
class Rating(models.Model):
    value = models.FloatField(default=1500)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.song} - {self.user}: {self.value}'