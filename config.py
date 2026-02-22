# Scoring weights — must sum to 1.0
SCORING_WEIGHTS = {
    "grant_freshness":  0.20,
    "award_size_score": 0.15,
    "ai_signal":        0.30,
    "data_signal":      0.20,
    "is_new_award":     0.15,
}

SIGNAL_LABELS = {
    "grant_freshness":  "Grant Freshness  (weight: 20%)",
    "award_size_score": "Award Size       (weight: 15%)",
    "ai_signal":        "AI Signal        (weight: 30%)",
    "data_signal":      "Data Signal      (weight: 20%)",
    "is_new_award":     "New Award        (weight: 15%)",
}

FRESHNESS_DECAY_DAYS   = 90    # leads older than this score 0.0
AWARD_SIZE_LOG_MIN     = 10.8  # log($50k) ≈ 10.8 → score 0.0
AWARD_SIZE_LOG_MAX     = 15.4  # log($5M) ≈ 15.4 → score 1.0
ABSTRACT_MIN_WORDS     = 80    # abstracts shorter than this flagged as low-data
GRANT_RETRIEVAL_POOL   = 50    # candidates passed to LLM reranker
