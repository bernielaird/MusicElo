"""Elo rating math for head-to-head song comparisons."""

INITIAL_RATING = 1500
K_FACTOR = 30


def expected_score(rating, opponent_rating):
    """Probability (0-1) that a song with `rating` beats one with `opponent_rating`."""
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def update_ratings(winner_rating, loser_rating, k=K_FACTOR):
    """Return the (winner, loser) ratings after the winner wins a matchup.

    The update is zero-sum: the winner gains exactly what the loser loses.
    """
    change = k * (1 - expected_score(winner_rating, loser_rating))
    return winner_rating + change, loser_rating - change
