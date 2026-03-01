# =============================================================================
# config.py — Central configuration for the Madison Interest Map project
# =============================================================================
# All tunable constants live here so you can tweak them without touching code.

# -----------------------------------------------------------------------------
# Geographic boundary — Madison, WI
# -----------------------------------------------------------------------------
# Any entity (place/event) whose coordinates fall outside this box is ignored.
# These values roughly describe the city limits of Madison, Wisconsin.
MADISON_BOUNDS = {
    "min_lat":  43.02,   # southernmost latitude
    "max_lat":  43.15,   # northernmost latitude
    "min_lon": -89.55,   # westernmost longitude
    "max_lon": -89.30,   # easternmost longitude
}

# -----------------------------------------------------------------------------
# Final score weights — must sum to 1.0
# -----------------------------------------------------------------------------
# Each component contributes this fraction to the final 0..1 score.
#   correlation : how well the entity matches the user's keywords (TF-IDF cosine)
#   popularity  : normalised (rating + review count)
#   weather     : how "nice" the weather is at the entity's location right now
#   urgency     : for events — how close the event is to ending
WEIGHTS = {
    "correlation": 0.45,
    "popularity":  0.25,
    "weather":     0.15,
    "urgency":     0.15,
}

# -----------------------------------------------------------------------------
# Popularity score constants
# -----------------------------------------------------------------------------
# We cap review counts at this value before taking log so a mega-popular place
# doesn't completely dominate the ranking.
REVIEW_COUNT_CAP = 500

# -----------------------------------------------------------------------------
# Urgency constant
# -----------------------------------------------------------------------------
# An event that is URGENCY_HORIZON_HOURS or more away from ending gets urgency=0.
# An event ending *right now* gets urgency=1.
URGENCY_HORIZON_HOURS = 3

# -----------------------------------------------------------------------------
# Weather "comfortable" ranges — used to build weather_score
# -----------------------------------------------------------------------------
# Temperatures inside [TEMP_IDEAL_LOW, TEMP_IDEAL_HIGH] score 1.0;
# outside this range the score decays towards 0.
TEMP_IDEAL_LOW_F  = 60   # °F
TEMP_IDEAL_HIGH_F = 78   # °F
TEMP_DECAY_F      = 20   # degrees of deviation → score falls to ~0

# API settings
API_HOST = "0.0.0.0"
API_PORT = 8000
