# Fixtures

Test inputs committed with the code. Tests read only from here (and, read-only, the bundled
dataset), never from `data/cache`, `data/user` or `data/raw`.

| Folder | What |
| --- | --- |
| `profiles/` | Fixture build profiles with round weights for hand calculation (not real builds) |
| `golden/` | Hand-calculated scores: a context, an item, the expected component-by-component result (`tests/regression/test_golden_scores.py`) |
| `reviews/<profile id>/` | Hand-reviewed comparisons of real items that each shipped profile must rank correctly - at least five per profile (`tests/regression/test_profile_reviews.py`) |
| `bundled/` | A 15-item dataset copied from the bundled one, for workspace tests |
| `providers/` | Constructed provider responses (Blizzard) for the adapter tests |

A review holds the context, copies of the items as the bundled dataset had them, the
expected outcome, winner, score difference, per-component differences, cap events and
unusable reasons, the hand calculation, and why a player would agree. A review is written by
hand; when a profile, the ruleset or a reviewed item changes, its test fails until someone
reviews it again - expected numbers are never edited just to pass.
