"""Services: the use cases the UI and the command line call.

Owns: the calculator's operations (choose a context, enter or find an item, score, compare,
inspect profiles, manage characters and gear sets, report data health). The UI calls
services only - never a provider, a repository or a formula directly.

May import: every ``wow_gear`` layer.
"""
