# ACCLAM Launch Quest

Local, read-only Launch Quest for the locked ACCLAM v3.0 scope: **610 objectives,
20 milestones, 77 collections**, with dependencies, evidence links and dated
history. The transferred register records three verified source/preparation
objectives. It makes no claim that Wix has been implemented, imported or released.

## Run the saved dashboard

Required: **Node.js18+** and **Python3.10+**, using standard libraries. No npm
packages, build step, credentials or Codex installation are required. The launcher
checks the available runtime. The existing Codex runtime is an optional fallback.

```text
node work/launch-quest/launch.mjs
```

On Windows, double-click `work/launch-quest/Abrir Launch Quest.cmd`.
The viewer listens on loopback only. Set `ACCLAM_QUEST_PORT` if the default4317
is occupied. `node work/launch-quest/launch.mjs --no-browser` starts without
opening a browser; `--close` stops only the identified launcher-owned process.

## What was preserved

`work/launch-quest/PROJECT_REGISTER.json` is the authoritative **data artifact**;
its exact original bytes, all task histories, IDs, source/evidence paths, proofs
and existing checkpoints are preserved. `COPY_MANIFEST.json` pins the files
copied unchanged and identifies runtime/documentation adaptations.

This repository is a transfer snapshot. The original local Website workspace is
unchanged. The transfer creates no automatic synchronization or second live
status store. Before later progress edits, explicitly choose the working master
and synchronize the other copy with a reviewed checkpoint. Browser interactions
never complete objectives.

## Private dependencies

This is a public code repository. Client PDFs/workbooks, CMS record exports,
Drive inventories/text, handoff documents and full schema/PDF extracts are
excluded. `EXTERNAL_SOURCES.json` records101 missing private files by exact
workspace-relative path and hash, preserving every evidence link without
publishing its contents. A source link without its private dependency returns
HTTP424 with an explanation.

The saved dashboard remains usable without those files. **Copy verification is
not fresh private-evidence verification**: a successful `verify-copy` checks
structure and available evidence, and reports unavailable dependencies explicitly.
It cannot turn missing private proof into a successful full validation or build.

To perform strict verification on a trusted local machine, set
`ACCLAM_SOURCE_ROOT` to the private Website workspace **only in your local
environment**, then run:

```text
python work/launch-quest/scripts/quest.py validate
python work/launch-quest/scripts/verify_repository.py
```

Only manifest-listed files may be read from that root, with path containment and
hash checks. This setting is not an instruction to copy or upload them. Do not
place credentials or private files in the repository. `.gitignore` is a secondary
guard; the transfer uses an explicit file allowlist and content review.

## Verification and maintenance

```text
python work/launch-quest/scripts/quest.py verify-copy
python work/launch-quest/scripts/verify_repository.py
python work/launch-quest/scripts/test_quest.py
```

See `work/launch-quest/README.txt` for the continuing-work sequence. Full updates
(`launch.mjs --update-only`) require all original evidence and validated sources;
they preserve the distinction between design, local preparation, Wix construction,
import, testing, ACCLAM human review and release.

The optional historical research scripts `extract_locked.py` and
`schema_inventory.py` require private source files. PDF extraction additionally
requires `pypdf`; it is not a dashboard runtime dependency. Seed/audit/localization
scripts are retained as provenance and must not be replayed over the register.

No hosting, deployment, Wix/Drive write, notifications or recurring automation
was added by this repository transfer.
