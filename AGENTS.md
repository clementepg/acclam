# ACCLAM Launch Quest repository

This is a privacy-filtered copy of the existing local Launch Quest. Preserve
`work/launch-quest/PROJECT_REGISTER.json`, baseline IDs, task histories, proofs,
source paths and historical checkpoints. The original private Website workspace
remains intact. This transfer does not authorize task completion or create
automatic synchronization between copies.

Read README.md and work/launch-quest/README.txt before editing. Do not run the
one-time seed/localization/audit migration scripts to regenerate the register.
Do not infer Wix implementation, import, human approval or release from a
specification, CSV, test plan or repository commit.

Private client documents and source extracts are deliberately excluded. Their
exact relative paths and hashes are retained in EXTERNAL_SOURCES.json and the
register. Use ACCLAM_SOURCE_ROOT only in the local environment when authorized;
never commit its absolute path, source bodies, credentials, logs or runtime IDs.
Missing private evidence must remain distinguishable from verified evidence.

Runtime: Node.js18+ and Python3.10+, standard libraries. No npm install is needed.
Run `python work/launch-quest/scripts/verify_repository.py` and the applicable
runtime tests before a commit. Strict evidence validation also requires the
private sources: `python work/launch-quest/scripts/quest.py validate`.

Keep the register as the single state artifact. Generated progress/source maps
and transfer manifests are projections/audits, never competing task registers.
Make any future authority change or synchronization explicit before independently
editing multiple copies. No Wix/Drive writes or website deployment are implied.
