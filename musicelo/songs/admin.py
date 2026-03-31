from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Song, Rating

admin.site.register(Song)
admin.site.register(Rating)