from pathlib import Path

from ingestion.graph_updater import MemgraphIngestor
from loguru import logger
from retrieval.schemas import CodeSnippet


class CodeRetriever:
    """Service to retrieve code snippets using the graph and filesystem."""

    def __init__(self, project_root: str, ingestor: MemgraphIngestor):
        self.project_root = Path(project_root).resolve()
        self.ingestor = ingestor
        logger.info(f"CodeRetriever initialized with root: {self.project_root}")

    async def find_code_snippet(self, qualified_name: str) -> CodeSnippet:
        """Finds a code snippet by querying the graph for its location."""
        logger.info(f"[CodeRetriever] Searching for: {qualified_name}")

        # One hop is enough: Module ─DEFINES/DEFINES_METHOD→ (n)
        query = """
            MATCH (n {qualified_name:$qn})
            OPTIONAL MATCH (n)<-[:DEFINES|DEFINES_METHOD]-(m:Module)
            WITH n,
                 coalesce(n.impl_path , m.path) AS path
            RETURN n.name        AS name,
                   n.start_line  AS start,
                   n.end_line    AS end,
                   path,
                   n.docstring   AS docstring
            LIMIT 1
        """
        params = {"qn": qualified_name}
        try:
            # Use the ingestor's public interface
            results = self.ingestor.fetch_all(query, params)

            if not results:
                return CodeSnippet(
                    qualified_name=qualified_name,
                    source_code="",
                    file_path="",
                    line_start=0,
                    line_end=0,
                    found=False,
                    error_message="Entity not found in graph.",
                )

            res = results[0]
            file_path_str = res.get("impl_path") or res.get("path")
            start_line = res.get("start")
            end_line = res.get("end")

            if not all([file_path_str, start_line, end_line]):
                return CodeSnippet(
                    qualified_name=qualified_name,
                    source_code="",
                    file_path=file_path_str or "",
                    line_start=0,
                    line_end=0,
                    found=False,
                    error_message="Graph entry is missing location data.",
                )

            full_path = self.project_root / file_path_str
            with full_path.open("r", encoding="utf-8") as f:
                all_lines = f.readlines()

            snippet_lines = all_lines[start_line - 1 : end_line]
            source_code = "".join(snippet_lines)

            return CodeSnippet(
                qualified_name=qualified_name,
                source_code=source_code,
                file_path=file_path_str,
                line_start=start_line,
                line_end=end_line,
                docstring=res.get("docstring"),
            )
        except Exception as e:
            logger.error(f"[CodeRetriever] Error: {e}", exc_info=True)
            return CodeSnippet(
                qualified_name=qualified_name,
                source_code="",
                file_path="",
                line_start=0,
                line_end=0,
                found=False,
                error_message=str(e),
            )
