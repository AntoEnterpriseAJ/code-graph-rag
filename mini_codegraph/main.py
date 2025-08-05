from query import ask_graph, find_snippet, ingest_repo

REPO = "/.../some_path/"

ingest_repo(REPO)

rows = ask_graph("show Contourer::run")
qn = rows[0]["qualified_name"]

snippet = find_snippet(qn, project_root=REPO)
print(f"{snippet.file_path}:{snippet.line_start}-{snippet.line_end}\n")
print(snippet.source_code)
