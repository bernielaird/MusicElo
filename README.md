# MusicElo

Rank your music by choosing between two songs at a time.

MusicElo is a Django web app that builds a personal ranking of your songs from head-to-head matchups. It uses the [Elo rating system](https://en.wikipedia.org/wiki/Elo_rating_system), the same method used to rank chess players. Paste a Spotify track link to add a song, then keep picking the one you like more. Your list sorts itself as you vote.

<!-- Add a screenshot or GIF of the versus page here, e.g.:
![Versus screen](docs/versus.png)
-->

## Features

- **Head-to-head voting:** you're shown two of your songs side by side with cover art and pick the one you prefer.
- **Elo-based ranking:** every song starts at 1500, and each vote adjusts both songs' ratings based on how surprising the result was.
- **Spotify integration:** paste a Spotify track URL and the app gets the title, artist, album, and cover art through the Spotify Web API.
- **User accounts:** each user has their own song list and their own ratings.

## How the ranking works

When song A (rating `Ra`) is compared with song B (rating `Rb`), each song's expected score is

```
Ea = 1 / (1 + 10^((Rb - Ra) / 400))
Eb = 1 - Ea
```

After the vote, the winner gets `S = 1` and the loser `S = 0`, and both ratings update:

```
Ra' = Ra + K * (Sa - Ea)
Rb' = Rb + K * (Sb - Eb)
```

with `K = 30`. If a high-rated song beats a low-rated one, the ratings barely change. If the low-rated song wins, both ratings move a lot. After enough votes, the ratings settle into an order that reflects your preferences.

## Tech stack

- **Backend:** Python 3.12, Django 6.1
- **Frontend:** Django templates, HTML, CSS
- **Database:** SQLite
- **External API:** Spotify Web API, accessed with [Spotipy](https://spotipy.readthedocs.io/)

## Getting started

### Prerequisites

- Python 3.12+
- A Spotify developer app (create one free at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)) to get a client ID and secret

### Setup

```bash
git clone https://github.com/<your-username>/MusicElo.git
cd MusicElo

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
SPOTIPY_CLIENT_ID=your-spotify-client-id
SPOTIPY_CLIENT_SECRET=your-spotify-client-secret
```

Then run the migrations and start the server:

```bash
cd musicelo
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/, sign up, and add at least two songs to start voting.

## Running tests

```bash
cd musicelo
python manage.py test
```

The suite covers the Elo math, Spotify URL parsing, authentication, adding songs (with the Spotify API mocked), and voting, including checks that users can only see and vote on their own ratings.

## Usage

1. **Add songs:** on the **Add** page, paste a Spotify track link (e.g. `https://open.spotify.com/track/...`).
2. **Vote:** on the **Versus** page, click the song you prefer. A new matchup loads right away.
3. **See your ranking:** the **List** page shows all your songs sorted by rating.

## Project structure

```
musicelo/
├── manage.py
├── musicelo/          # Project settings and root URL config
└── songs/             # Main app
    ├── models.py      # Song and Rating models
    ├── elo.py         # Elo rating math
    ├── spotify.py     # Spotify URL parsing and track lookup
    ├── views.py       # Song import, versus matchups, and voting
    ├── tests.py
    ├── urls.py
    ├── templates/songs/
    └── static/songs/
```

## License

Released under the [MIT License](MIT-LICENSE.txt).
