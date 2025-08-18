from query import ask_graph, find_snippet, ingest_repo

REPO = "/home/anto/dev/repos/AlgoPool.CT.CoronaryCommon"

ingest_repo(REPO)

rows = ask_graph("Show me SegmentationCommon::extractContours")
snippets = []
if not rows:
    print("No matches.")
else:
    seen = set()
    for row in rows:
        qn = row.get("qualified_name")
        if not qn or qn in seen:
            continue
        seen.add(qn)
        snippet = find_snippet(qn, project_root=REPO)
        snippets.append(snippet)

for snippet in snippets:
    print(f"{snippet.file_path}:{snippet.line_start}-{snippet.line_end}\n")
    print(snippet.source_code)
