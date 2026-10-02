from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .elo import INITIAL_RATING, K_FACTOR, expected_score, update_ratings
from .models import Rating, Song
from .spotify import parse_spotify_url, parse_track_id

TRACK_ID = "4uLU6hMCjMI75M1A2tKUQC"


def make_song(n=1):
    return Song.objects.create(
        name=f"Song {n}",
        artist=f"Artist {n}",
        album=f"Album {n}",
        coverart=f"https://i.scdn.co/image/{n}",
        uri=f"spotify:track:{n:022d}",
    )


class EloTests(SimpleTestCase):
    def test_equal_ratings_have_even_odds(self):
        self.assertAlmostEqual(expected_score(1500, 1500), 0.5)

    def test_expected_scores_sum_to_one(self):
        self.assertAlmostEqual(expected_score(1700, 1400) + expected_score(1400, 1700), 1)

    def test_higher_rating_is_favored(self):
        self.assertGreater(expected_score(1700, 1500), 0.5)
        self.assertLess(expected_score(1500, 1700), 0.5)

    def test_400_point_gap_gives_ten_to_one_odds(self):
        self.assertAlmostEqual(expected_score(1900, 1500), 10 / 11)

    def test_equal_ratings_move_by_half_k(self):
        winner, loser = update_ratings(1500, 1500)
        self.assertAlmostEqual(winner, 1500 + K_FACTOR / 2)
        self.assertAlmostEqual(loser, 1500 - K_FACTOR / 2)

    def test_update_is_zero_sum(self):
        winner, loser = update_ratings(1620, 1480)
        self.assertAlmostEqual(winner + loser, 1620 + 1480)

    def test_upset_moves_ratings_more_than_expected_win(self):
        favorite_gain = update_ratings(1800, 1400)[0] - 1800
        underdog_gain = update_ratings(1400, 1800)[0] - 1400
        self.assertGreater(underdog_gain, favorite_gain)
        self.assertGreater(favorite_gain, 0)


class ParseTrackIdTests(SimpleTestCase):
    def test_valid_inputs(self):
        cases = [
            f"https://open.spotify.com/track/{TRACK_ID}",
            f"https://open.spotify.com/track/{TRACK_ID}?si=abc123",
            f"https://open.spotify.com/intl-de/track/{TRACK_ID}",
            f"  https://open.spotify.com/track/{TRACK_ID}/  ",
            f"spotify:track:{TRACK_ID}",
        ]
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(parse_track_id(value), TRACK_ID)

    def test_invalid_inputs(self):
        cases = [
            "",
            "not a url",
            f"https://open.spotify.com/album/{TRACK_ID}",
            f"https://open.spotify.com/playlist/{TRACK_ID}",
            "https://open.spotify.com/track/",
            "https://open.spotify.com/track/tooshort",
            f"https://evil.example.com/track/{TRACK_ID}",
            f"spotify:album:{TRACK_ID}",
        ]
        for value in cases:
            with self.subTest(value=value):
                self.assertIsNone(parse_track_id(value))


class ModelTests(TestCase):
    def test_new_rating_starts_at_initial_rating(self):
        user = User.objects.create_user("alice", password="pw")
        rating = Rating.objects.create(user=user, song=make_song())
        self.assertEqual(rating.value, INITIAL_RATING)

    def test_user_cannot_rate_same_song_twice(self):
        user = User.objects.create_user("alice", password="pw")
        song = make_song()
        Rating.objects.create(user=user, song=song)
        with self.assertRaises(IntegrityError):
            Rating.objects.create(user=user, song=song)

    def test_track_id_strips_uri_prefix(self):
        song = Song(uri=f"spotify:track:{TRACK_ID}")
        self.assertEqual(song.track_id, TRACK_ID)


class AuthTests(TestCase):
    def test_protected_pages_redirect_to_login(self):
        for name in ["songs:add", "songs:songlist", "songs:versus"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(
                    response, f"{reverse('songs:login')}?next={reverse(name)}"
                )

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("songs:signup"),
            {"username": "newuser", "password1": "a-Strong-pass-123", "password2": "a-Strong-pass-123"},
        )
        self.assertRedirects(response, reverse("songs:add"))
        self.assertTrue(User.objects.filter(username="newuser").exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get().pk)

    def test_signup_with_mismatched_passwords_shows_errors(self):
        response = self.client.post(
            reverse("songs:signup"),
            {"username": "newuser", "password1": "a-Strong-pass-123", "password2": "different"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())
        self.assertContains(response, "errorlist")

    def test_login_follows_next_parameter(self):
        User.objects.create_user("alice", password="pw")
        response = self.client.post(
            f"{reverse('songs:login')}?next={reverse('songs:versus')}",
            {"username": "alice", "password": "pw"},
        )
        self.assertRedirects(response, reverse("songs:versus"), fetch_redirect_response=False)

    def test_bad_login_shows_error(self):
        User.objects.create_user("alice", password="pw")
        response = self.client.post(reverse("songs:login"), {"username": "alice", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errorlist")


class AddSongTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)
        self.url = reverse("songs:add")
        self.track = {
            "name": "Never Gonna Give You Up",
            "artist": "Rick Astley",
            "album": "Whenever You Need Somebody",
            "coverart": "https://i.scdn.co/image/abc",
            "uri": f"spotify:track:{TRACK_ID}",
        }

    def post_track(self, value=f"https://open.spotify.com/track/{TRACK_ID}"):
        return self.client.post(self.url, {"spotifyurl": value}, follow=True)

    @patch("songs.spotify.fetch_track")
    def test_adds_song_and_rating(self, fetch_track):
        fetch_track.return_value = self.track
        response = self.post_track()

        fetch_track.assert_called_once_with(TRACK_ID)
        song = Song.objects.get()
        self.assertEqual(song.name, "Never Gonna Give You Up")
        self.assertTrue(Rating.objects.filter(user=self.user, song=song).exists())
        self.assertContains(response, "Added Never Gonna Give You Up")

    @patch("songs.spotify.fetch_track")
    def test_existing_song_is_not_refetched(self, fetch_track):
        Song.objects.create(**self.track)
        self.post_track()
        fetch_track.assert_not_called()
        self.assertEqual(Rating.objects.filter(user=self.user).count(), 1)

    @patch("songs.spotify.fetch_track")
    def test_adding_twice_does_not_duplicate_rating(self, fetch_track):
        fetch_track.return_value = self.track
        self.post_track()
        response = self.post_track()
        self.assertEqual(Rating.objects.filter(user=self.user).count(), 1)
        self.assertContains(response, "already in your list")

    @patch("songs.spotify.fetch_track")
    def test_invalid_url_shows_error_without_calling_spotify(self, fetch_track):
        response = self.post_track("https://example.com/not-spotify")
        fetch_track.assert_not_called()
        self.assertFalse(Song.objects.exists())
        self.assertContains(response, "valid Spotify track or playlist URL")

    @patch("songs.spotify.fetch_track", return_value=None)
    def test_spotify_failure_shows_error(self, fetch_track):
        response = self.post_track()
        self.assertFalse(Song.objects.exists())
        self.assertContains(response, "Couldn&#x27;t load that track")


class ParseSpotifyUrlTests(SimpleTestCase):
    def test_tracks_and_playlists(self):
        cases = {
            f"https://open.spotify.com/track/{TRACK_ID}?si=abc": ("track", TRACK_ID),
            f"https://open.spotify.com/playlist/{TRACK_ID}?si=abc": ("playlist", TRACK_ID),
            f"https://open.spotify.com/intl-de/playlist/{TRACK_ID}": ("playlist", TRACK_ID),
            f"spotify:playlist:{TRACK_ID}": ("playlist", TRACK_ID),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_spotify_url(value), expected)

    def test_other_kinds_are_rejected(self):
        for value in [
            f"https://open.spotify.com/album/{TRACK_ID}",
            f"spotify:artist:{TRACK_ID}",
            "https://open.spotify.com/playlist/tooshort",
        ]:
            with self.subTest(value=value):
                self.assertIsNone(parse_spotify_url(value))


class AddPlaylistTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)
        self.url = reverse("songs:add")
        self.tracks = [
            {
                "name": f"Song {n}",
                "artist": "Artist",
                "album": "Album",
                "coverart": "",
                "uri": f"spotify:track:{n:022d}",
            }
            for n in range(3)
        ]

    def post_playlist(self):
        return self.client.post(
            self.url,
            {"spotifyurl": f"https://open.spotify.com/playlist/{TRACK_ID}"},
            follow=True,
        )

    @patch("songs.spotify.fetch_playlist_tracks")
    def test_adds_every_song(self, fetch_playlist_tracks):
        fetch_playlist_tracks.return_value = self.tracks
        response = self.post_playlist()

        fetch_playlist_tracks.assert_called_once_with(TRACK_ID)
        self.assertEqual(Song.objects.count(), 3)
        self.assertEqual(Rating.objects.filter(user=self.user).count(), 3)
        self.assertContains(response, "Added 3 songs from the playlist.")

    @patch("songs.spotify.fetch_playlist_tracks")
    def test_skips_songs_already_in_list_and_duplicates(self, fetch_playlist_tracks):
        song = Song.objects.create(**self.tracks[0])
        Rating.objects.create(user=self.user, song=song, value=1234)
        fetch_playlist_tracks.return_value = self.tracks + [self.tracks[1]]
        response = self.post_playlist()

        self.assertEqual(Song.objects.count(), 3)
        self.assertEqual(Rating.objects.filter(user=self.user).count(), 3)
        self.assertEqual(Rating.objects.get(song=song).value, 1234)
        self.assertContains(response, "Added 2 songs from the playlist. 1 was already in your list.")

    @patch("songs.spotify.fetch_playlist_tracks", return_value=None)
    def test_spotify_failure_shows_error(self, fetch_playlist_tracks):
        response = self.post_playlist()
        self.assertFalse(Song.objects.exists())
        self.assertContains(response, "Couldn&#x27;t load that playlist")


class VersusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)

    def test_needs_two_songs(self):
        Rating.objects.create(user=self.user, song=make_song(1))
        response = self.client.get(reverse("songs:versus"), follow=True)
        self.assertRedirects(response, reverse("songs:add"))
        self.assertContains(response, "at least two songs")

    def test_shows_two_of_the_users_songs(self):
        Rating.objects.create(user=self.user, song=make_song(1))
        Rating.objects.create(user=self.user, song=make_song(2))
        response = self.client.get(reverse("songs:versus"))
        self.assertContains(response, "Song 1")
        self.assertContains(response, "Song 2")

    def test_never_shows_other_users_songs(self):
        other = User.objects.create_user("bob", password="pw")
        Rating.objects.create(user=self.user, song=make_song(1))
        Rating.objects.create(user=self.user, song=make_song(2))
        Rating.objects.create(user=other, song=make_song(3))
        for _ in range(10):
            self.assertNotContains(self.client.get(reverse("songs:versus")), "Song 3")


class VoteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)
        self.a = Rating.objects.create(user=self.user, song=make_song(1))
        self.b = Rating.objects.create(user=self.user, song=make_song(2))

    def vote_url(self, winner, loser):
        return reverse("songs:vote", args=[winner.id, loser.id])

    def test_vote_updates_ratings(self):
        response = self.client.post(self.vote_url(self.a, self.b))
        self.assertRedirects(response, reverse("songs:versus"), fetch_redirect_response=False)
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertAlmostEqual(self.a.value, INITIAL_RATING + K_FACTOR / 2)
        self.assertAlmostEqual(self.b.value, INITIAL_RATING - K_FACTOR / 2)

    def test_get_request_does_not_vote(self):
        response = self.client.get(self.vote_url(self.a, self.b))
        self.assertEqual(response.status_code, 405)
        self.a.refresh_from_db()
        self.assertEqual(self.a.value, INITIAL_RATING)

    def test_cannot_vote_on_another_users_ratings(self):
        other = User.objects.create_user("bob", password="pw")
        theirs = Rating.objects.create(user=other, song=make_song(3))
        response = self.client.post(self.vote_url(self.a, theirs))
        self.assertEqual(response.status_code, 404)
        self.a.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(self.a.value, INITIAL_RATING)
        self.assertEqual(theirs.value, INITIAL_RATING)

    def test_song_cannot_play_itself(self):
        response = self.client.post(self.vote_url(self.a, self.a))
        self.assertEqual(response.status_code, 400)


class SongListTests(TestCase):
    def test_lists_only_own_songs_highest_first(self):
        user = User.objects.create_user("alice", password="pw")
        other = User.objects.create_user("bob", password="pw")
        Rating.objects.create(user=user, song=make_song(1), value=1400)
        Rating.objects.create(user=user, song=make_song(2), value=1600)
        Rating.objects.create(user=other, song=make_song(3))

        self.client.force_login(user)
        response = self.client.get(reverse("songs:songlist"))

        names = [r.song.name for r in response.context["ratings"]]
        self.assertEqual(names, ["Song 2", "Song 1"])
