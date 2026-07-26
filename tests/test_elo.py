import pytest
from app.services.debate_service import _calculate_elo_updates, ELO_K_FACTOR


def test_equal_ratings_win():
    pro_new, con_new = _calculate_elo_updates(1500, 1500, score_a=1.0)
    assert pro_new == 1516
    assert con_new == 1484
    assert (pro_new - 1500) == 16
    assert (con_new - 1500) == -16


def test_equal_ratings_draw():
    pro_new, con_new = _calculate_elo_updates(1500, 1500, score_a=0.5)
    assert pro_new == 1500
    assert con_new == 1500
    assert (pro_new - 1500) == 0
    assert (con_new - 1500) == 0


def test_underdog_wins():
    underdog_new, favorite_new = _calculate_elo_updates(1200, 2000, score_a=1.0)
    underdog_gain = underdog_new - 1200
    favorite_loss = favorite_new - 2000
    assert underdog_gain > 20
    assert favorite_loss < -20
    assert underdog_gain >= abs(favorite_loss)


def test_favorite_wins():
    favorite_new, underdog_new = _calculate_elo_updates(2000, 1200, score_a=1.0)
    favorite_gain = favorite_new - 2000
    underdog_loss = underdog_new - 1200
    assert favorite_gain >= 0
    assert underdog_loss <= 0
    assert abs(favorite_gain) <= abs(underdog_loss)


def test_draw_underdog_gains():
    underdog_new, favorite_new = _calculate_elo_updates(1200, 2000, score_a=0.5)
    underdog_change = underdog_new - 1200
    favorite_change = favorite_new - 2000
    assert underdog_change > 0
    assert favorite_change < 0
    assert underdog_change == abs(favorite_change)


def test_draw_favorite_loses():
    favorite_new, underdog_new = _calculate_elo_updates(2000, 1200, score_a=0.5)
    favorite_change = favorite_new - 2000
    underdog_change = underdog_new - 1200
    assert favorite_change < 0
    assert underdog_change > 0
    assert abs(favorite_change) == underdog_change


def test_ratings_never_negative():
    rating = 10
    for _ in range(5):
        rating, _ = _calculate_elo_updates(rating, 2500, score_a=0.0)
    assert rating >= 0


def test_elo_sum_preserved():
    # Total ELO in the system should shift but sum of both players is predictable
    pro_new, con_new = _calculate_elo_updates(1500, 1500, score_a=1.0)
    assert (pro_new + con_new) == 3000


def test_elo_sum_preserved_draw():
    pro_new, con_new = _calculate_elo_updates(1200, 2000, score_a=0.5)
    assert (pro_new + con_new) == 3200


def test_k_factor_multiplier():
    rating_diff = 400
    expected_stronger = 1 / (1 + 10 ** (-rating_diff / 400))
    expected_weaker = 1 / (1 + 10 ** (rating_diff / 400))
    assert round(expected_stronger, 2) == pytest.approx(0.91, abs=0.01)
    assert round(expected_weaker, 2) == pytest.approx(0.09, abs=0.01)
