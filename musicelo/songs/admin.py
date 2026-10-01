from django.contrib import admin

from .models import Rating, Song


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ["name", "artist", "album"]
    search_fields = ["name", "artist", "album"]


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["song", "user", "value"]
    list_filter = ["user"]
