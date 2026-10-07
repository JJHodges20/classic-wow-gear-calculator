# 0007 - The player's own build profiles

Date: 2026-10-07. Status: accepted.

## Context

The roadmap's theorycrafter wants "to inspect and override stat weights rather than being
forced to trust hidden defaults", and the Build Profiles page is to "inspect or customize
stat weights, caps, assumptions, and notes". The shipped profiles are sourced research
artifacts; changing them in place would break the link between a weight and its source, and
every result must stay reproducible from its profile version.

## Decision

1. **A customised profile is a copy.** Saving changed weights from a shipped profile creates
   `custom_<name>` in `data/user/profiles/<class>/`, never touching `configs/profiles/`.
2. **Every save is a version.** The first save is 1.0.0; each later save of the same custom
   profile increments the patch number, and each version is copied to
   `data/user/profiles/history/<id>/<version>.yaml`, so a result naming a version can be
   reproduced.
3. **What the player set is labelled.** A changed or added weight takes the `assumption`
   basis with a note naming the original value; unchanged weights keep their sources. Custom
   profiles are `experimental`, and their notes record the profile they were copied from.
4. **The same checks apply.** A custom profile goes through the model's validation and the
   ruleset cross-checks; an invalid one is refused with the reason. A broken custom file is
   reported on the Data Health and Profiles pages and skipped, never fatal.
5. **They appear like any other profile** in the context bar, the comparison and the
   reports, with "(yours)" in the Profiles page list.

## Consequences

- The shipped profiles stay the reviewed, sourced baseline; review fixtures run only against
  them.
- Deleting a custom profile removes it from the lists but keeps its history.
