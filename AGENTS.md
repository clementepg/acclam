# ACCLAM Launch Quest repository

This is the active ACCLAM Launch Quest working repository, selected by the user.
The authority transition is recorded in work/launch-quest/WORKING_AUTHORITY.json.
Preserve
`work/launch-quest/PROJECT_REGISTER.json`, baseline IDs, task histories, proofs,
source paths and historical checkpoints. The original private Website workspace
remains an untouched historical snapshot. Do not write progress back into it or
create automatic synchronization between copies. Task completion still requires
evidence supporting its actual phase and scope.

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
editing multiple copies. The user authorized online Launch Quest publication;
build its allowlisted static projection with scripts/build_online.py. Never
publish the raw register, source map, private source paths, proofs or documents
as Site assets. Wix/Drive implementation writes remain outside this request.
