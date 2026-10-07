# Constructed Blizzard API responses

These responses are built by hand to the shape Blizzard documents for the Game Data API item
and item-search endpoints (and to published example responses; see
docs/research/DATA_SOURCES.md). They are not captured from the live API: no credentials were
available when they were written. Lionheart Helm and Brutality Blade carry the same values
as the bundled dataset, so the tests can check that both sources normalize to the same item.
"Test Girdle of Lookups" is invented for the tests and exists in no game data.
