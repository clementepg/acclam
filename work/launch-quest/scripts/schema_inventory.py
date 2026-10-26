"""Build read-only schema crosswalk; never changes frozen sources or task state."""
from pathlib import Path
import csv
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work/launch-quest/sources/schema_inventory.json"
PAGES = ROOT / "work/launch-quest/sources/locked_pages.json"
FACTS = ROOT / "handoff/locked_baseline_facts.json"
DICTIONARY = ROOT / "Website architecture/schema_v3_0/ACCLAM_V3_CSV_Templates/ACCLAM_V3_Field_Dictionary.csv"
TEMPLATES = DICTIONARY.parent / "collections"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(text):
    return re.sub(r"[^\w]", "", text, flags=re.UNICODE).lower()


def relative(path):
    return path.relative_to(ROOT).as_posix()


pages = json.loads(PAGES.read_text(encoding="utf-8"))
facts = json.loads(FACTS.read_text(encoding="utf-8-sig"))
source = ROOT / pages["sourceRelativePath"]
assert sha(source) == pages["sourceSha256"] == facts["authority"]["sha256"]
assert pages["physicalPageCount"] == 252
assert len(facts["collections"]) == 77
with DICTIONARY.open(encoding="utf-8-sig", newline="") as stream:
    reader = csv.DictReader(stream)
    dictionary_columns = reader.fieldnames
    dictionary = list(reader)
assert len(dictionary) == 1083 and len(dictionary_columns) == 22
by_name = {}
for row_number, row in enumerate(dictionary, 2):
    row["_csvRow"] = row_number
    by_name.setdefault(row["Collection"], []).append(row)
templates = {}
for path in TEMPLATES.glob("*.csv"):
    match = re.fullmatch(r"(\d\d)_(.+)\.csv", path.name)
    assert match, path
    assert match[2] not in templates, path
    templates[match[2]] = path
assert set(by_name) == set(templates) == {c["name"] for c in facts["collections"]}

# Remove only repeated printed page furniture. Keep document content and source
# page offsets so every collection section can be cited by physical PDF page.
text = ""
page_offsets = []
for page in pages["pages"]:
    if not 24 <= page["page"] <= 189:
        continue
    clean = re.sub(r"\ATOMO [IVX]+\nACCLAM[^\n]*\nPagina \d+\n", "", page["text"])
    page_offsets.append((len(text), page["page"]))
    text += clean + "\n"


def physical_page(offset):
    return max((p for start, p in page_offsets if start <= offset), default=24)


starts = []
for collection in facts["collections"]:
    title = f'{collection["number"]} {collection["name"]}'
    candidates = []
    for match in re.finditer(r"(?m)^" + re.escape(title) + r"\n", text):
        following = text[match.end():match.end()+450]
        if "\nFolder\n" in following and "\nPrivacy\n" in following:
            candidates.append(match.start())
    assert len(candidates) == 1, (title, candidates)
    starts.append((candidates[0], collection))
starts.sort()
assert [c["number"] for _, c in starts] == [f"{n:02d}" for n in range(1,78)]

collections = []
field_signature_issues = []
reference_issues = []
template_issues = []
for i, (start, collection) in enumerate(starts):
    end = starts[i+1][0] if i+1 < len(starts) else len(text)
    segment = text[start:end]
    # TOMO II/III dictionary sections are separated by indexes/reference
    # matrices and front matter. Stop at this collection's final builder check,
    # not at the next collection's much later start in the following volume.
    builder_check = segment.rfind("Builder check:")
    assert builder_check >= 0, collection["name"]
    builder_end = segment.find("\n", builder_check)
    if builder_end < 0:
        builder_end = len(segment)
    segment = segment[:builder_end]
    end = start + len(segment)
    section_norm = norm(segment)
    metadata = segment.split("Reference map", 1)[0]
    count_match = re.search(r"\nFields\n(\d+)\nPrimary display\n([^\n]+)", metadata)
    assert count_match, collection["name"]
    assert int(count_match[1]) == collection["field_count"]
    assert count_match[2] == collection["primary_display"]
    assert norm(collection["folder"]) in norm(metadata)
    rows = by_name[collection["name"]]
    assert len(rows) == collection["field_count"]
    keys = [r["Wix Field Key"] for r in rows]
    assert len(keys) == len(set(keys))
    path = templates[collection["name"]]
    with path.open(encoding="utf-8-sig", newline="") as stream:
        template_rows = list(csv.reader(stream))
    headers = template_rows[0]
    assert headers == keys, collection["name"]
    assert not any(any(value.strip() for value in row) for row in template_rows[1:])
    field_rows = []
    upstream = segment.split("UPSTREAM field", 1)[1].split("DOWNSTREAM", 1)[0] if "UPSTREAM field" in segment else ""
    for row in rows:
        required = "YES" if row["Required?"].lower() == "yes" else "No"
        signature = norm(row["Wix Field Key"] + row["Display Label"] + row["Field Type"] + required)
        signature_match = signature in section_norm
        if not signature_match:
            field_signature_issues.append({"collection":collection["name"],"field":row["Wix Field Key"],"csvRow":row["_csvRow"]})
        field_rows.append({
            "key": row["Wix Field Key"], "displayLabel": row["Display Label"],
            "type": row["Field Type"], "required": row["Required?"].lower() == "yes",
            "businessKey": row["Business Key?"].lower() == "yes", "referenceTarget":row["Reference Target"] or None,
            "dictionaryCsvRow":row["_csvRow"], "lockedPdfKeyLabelTypeRequiredTextMatched":signature_match,
        })
    name_to_id = {c["name"]: c["number"] for c in facts["collections"]}
    references = []
    for row in rows:
        if not row["Reference Target"]:
            continue
        target_name = row["Reference Target"]
        target_id = name_to_id[target_name]
        signature = norm(row["Wix Field Key"] + target_id + " " + target_name + "many-to-one")
        reference_match = signature in norm(upstream)
        if not reference_match:
            reference_issues.append({"collection":collection["name"],"field":row["Wix Field Key"],"target":target_name})
        references.append({
            "field":row["Wix Field Key"], "targetId":target_id,"targetCollection":target_name,
            "required":row["Required?"].lower() == "yes", "cardinality":row["Cardinality"],
            "dictionaryCsvRow":row["_csvRow"],"lockedPdfUpstreamTextMatched":reference_match,
            "selfReference":target_name == collection["name"],
        })
    start_page = physical_page(start)
    end_page = physical_page(max(start,end-2))
    collections.append({
        "id":collection["number"],"name":collection["name"],"folder":collection["folder"],
        "folderId":collection["folder"][:2],"purpose":collection["purpose"],
        "privacyClassification":collection["privacy_classification"],
        "specifiedImportPhase":collection["specified_import_phase"],"recordCodePrefix":collection["id_prefix"],
        "primaryDisplay":collection["primary_display"],"wixPermissionMode":collection["wix_permission_mode"],
        "physicalPageRangeInclusive":[start_page,end_page],"globalIndexPhysicalPage":8 if int(collection["number"])<=38 else 9,
        "folderMapPhysicalPage":7,"sourceRelativePath":pages["sourceRelativePath"],
        "sourceSha256":pages["sourceSha256"],"sourcePdfFragment":"#page="+str(start_page),
        "lockedFieldCount":collection["field_count"],"dictionaryFieldCount":len(rows),
        "dictionaryCsvRowsInclusive":[rows[0]["_csvRow"],rows[-1]["_csvRow"]],
        "dictionaryRelativePath":relative(DICTIONARY),"dictionarySha256":sha(DICTIONARY),
        "templateRelativePath":relative(path),"templateSha256":sha(path),
        "templateFilenamePrefix":path.name[:2],"templateFilenamePrefixIsGlobalId":False,
        "templateHeaderCount":len(headers),"templateHeadersEqualDictionaryKeysInOrder":headers==keys,
        "templateHasDataRows":False,"businessKeys":[r["Wix Field Key"] for r in rows if r["Business Key?"].lower()=="yes"],
        "fields":field_rows,"references":references,
        "referenceTargetIds":sorted({r["targetId"] for r in references}),
        "dependencySemantics":"Reference target collection identities must exist and record IDs must be resolved; these are schema/data references, not an acyclic task build order.",
        "designMappingStatus":"source_mapped","wixImplementationStatus":"not_independently_verified",
        "completionEvidence":False,
    })

assert sum(c["lockedFieldCount"] for c in collections)==1083
assert sum(len(c["references"]) for c in collections)==456
prefixes = {}
for c in collections:
    prefixes.setdefault(c["templateFilenamePrefix"],[]).append(c["name"])

# Reference graph cycles are expected in the frozen design. Report actual
# strongly connected components to prevent using these links as task DAGs.
graph = {c["id"]:c["referenceTargetIds"] for c in collections}
seen, stack, indexes, low, on_stack, components = set(), [], {}, {}, set(), []


def visit(node):
    indexes[node] = low[node] = len(indexes)
    stack.append(node)
    on_stack.add(node)
    for target in graph[node]:
        if target not in indexes:
            visit(target)
            low[node] = min(low[node],low[target])
        elif target in on_stack:
            low[node] = min(low[node],indexes[target])
    if low[node] == indexes[node]:
        component = []
        while True:
            target=stack.pop()
            on_stack.remove(target)
            component.append(target)
            if target==node:
                break
        if len(component)>1 or node in graph[node]:
            components.append(sorted(component))


for node in graph:
    if node not in indexes:
        visit(node)

required_graph = {c["id"]: {r["targetId"] for r in c["references"] if r["required"]} for c in collections}
required_remaining = {node:set(targets) for node, targets in required_graph.items()}
while required_remaining:
    ready = {node for node, targets in required_remaining.items() if not targets}
    if not ready:
        break
    required_remaining = {node:targets-ready for node,targets in required_remaining.items() if node not in ready}
self_references = [{"collectionId":c["id"],"collection":c["name"],"field":r["field"],"required":r["required"]} for c in collections for r in c["references"] if r["selfReference"]]
cycle_details = []
for component in components:
    cycle_details.append({"collectionIds":component,"edges":[{"sourceId":c["id"],"field":r["field"],"targetId":r["targetId"],"required":r["required"]} for c in collections for r in c["references"] if c["id"] in component and r["targetId"] in component]})

output = {
    "schemaVersion":1,"artifact":"ACCLAM locked V3.0 collection source crosswalk",
    "reviewedOn":"2026-10-26","evidenceType":"local_source_mapping_only",
    "sourceAuthority":"User-confirmed last locked PDF. Source comparison does not prove Wix collections, imports, permissions, review or release.",
    "sourceRelativePath":pages["sourceRelativePath"],"sourceSha256":pages["sourceSha256"],"physicalPageCount":252,
    "citationConvention":"One-based physical PDF pages; physicalPageRangeInclusive lists endpoints, not only two individual pages.",
    "metadataSupport":{"relativePath":relative(FACTS),"sha256":sha(FACTS),"role":"Source-cited handoff metadata; collection headings/counts/display/folders independently checked against extracted locked PDF."},
    "dictionary":{"relativePath":relative(DICTIONARY),"sha256":sha(DICTIONARY),"dataRows":len(dictionary),"columns":dictionary_columns,"hasHelpTextColumn":False},
    "folders":facts["cms_folders"],"collections":collections,
    "reconciliation":{
        "collectionCount":len(collections),"lockedFieldCount":1083,"dictionaryFieldCount":1083,"templateCount":len(templates),
        "allTemplateHeadersMatchDictionaryOrder":True,"allLockedCollectionCountsMatchDictionary":True,
        "templateFilenamePrefixGroups":prefixes,"referenceFieldCount":456,
        "fieldKeyLabelTypeRequiredTextMatchCount":1083-len(field_signature_issues),"fieldTextMatchIssues":field_signature_issues,
        "referenceTargetTextMatchCount":456-len(reference_issues),"referenceTextMatchIssues":reference_issues,
        "referenceGraphCyclicComponents":components,
        "referenceGraphCycleDetails":cycle_details,"selfReferences":self_references,
        "requiredReferenceGraphIsAcyclic":not required_remaining,
        "requiredReferenceGraphCaveat":"A required-field DAG is still not an executed record import recipe. EntityRegistry source-item reconciliation, optional links, approvals, uniqueness and staging evidence remain necessary.",
        "qualifiedConclusion":"Global numbering, folders, counts, template headers, and reported PDF field/reference text matches provide a source crosswalk. Remaining manual/type-specific validation, indexes, Help Text, exact permission behavior and staging data acceptance must be verified before real imports.",
    },
    "caveats":[
        {"id":"SCHEMA-01","text":"Template filename prefixes repeat01-09 and are not global collection IDs. Map by exact collection technical name to the locked global01-77 index.","physicalPages":[6,7,8,9],"support":"handoff/START_HERE.txt"},
        {"id":"SCHEMA-02","text":"Companion workbook indexing was not regenerated after revised DTP publication according to shared history. This crosswalk does not certify workbook equality and never changes original workbook/schema/template sources.","support":"handoff/shared_chat_findings.txt"},
        {"id":"SCHEMA-03","text":"Dictionary CSV has no Help Text column. The locked PDF supplies Help Text and explicit permission configuration; count/header equality alone does not establish complete semantic equivalence.","physicalPages":[19,20,24,26,252]},
        {"id":"SCHEMA-04","text":"Reference graph contains cycles and self references. Do not turn every reference into a task prerequisite. Create empty schemas first, then resolve registry/taxonomy/self/batch links with a documented bootstrap or multipass staging plan preserving frozen requiredness.","physicalPages":[24,26,39,185,186,188,235,251]},
        {"id":"SCHEMA-05","text":"Folder organization and privacy classification do not configure Wix permissions. Validate explicit Collection permissions, member-page access and backend authorization separately; Certificates public verification must use a narrow projection.","physicalPages":[7,20,145,237,252]},
        {"id":"SCHEMA-06","text":"Header-only CSVs contain no imported or approved records. Sources, templates and this generated inventory are design/preparation evidence only. Wix state remains uninspected.","support":"handoff/CURRENT_STATE.json"},
        {"id":"SCHEMA-07","text":"Text signature checks normalize layout whitespace and punctuation. They do not replace visual field-by-field builder review or prove live functionality.","physicalPages":[252]},
    ],
    "nextActions":[
        "Review schema crosswalk issues and reconcile frozen PDF with companion workbook field semantics, Help Text, indexes and explicit permissions.",
        "Define verified bootstrap/multipass staging order rather than sorting only by import-phase numbers or treating references as a task DAG.",
        "Map preliminary speaker/event/session candidates to actual People/DirectoryProfiles/Events/Sessions/SpeakerAssignments fields with provenance and missing-required-value blockers.",
        "Keep Wix construction, import receipts, functional/security tests, ACCLAM review and authorized release as distinct evidence requirements.",
    ],
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"output":str(OUT),"collections":len(collections),"fieldCount":1083,"fieldTextMatchIssues":field_signature_issues,"referenceTextMatchIssues":reference_issues,"cyclicComponents":components},ensure_ascii=False))
