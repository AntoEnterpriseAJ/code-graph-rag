import asyncio
from pathlib import Path
from typing import Any

from db.graph_service import MemgraphIngestor
from ingestion.graph_updater import GraphUpdater
from ingestion.parser_loader import load_parsers
from nl2cypher.llm import CypherGenerator
from retrieval.code_retrieval import CodeRetriever


def ingest_repo(
    repo_path: str, *, memgraph_host: str = "localhost", memgraph_port: int = 7687
) -> None:
    """Parse <repo_path> and load its code graph into Memgraph."""
    parsers, queries = load_parsers()
    with MemgraphIngestor(memgraph_host, memgraph_port) as db:
        db.clean_database()

        updater = GraphUpdater(
            ingestor=db,
            repo_path=Path(repo_path),
            parsers=parsers,
            queries=queries,
        )
        updater.run()
    print("✔ Graph ingestion complete")


async def _ask_async(question: str, db: MemgraphIngestor) -> Any:
    cypher_gen = CypherGenerator()
    cypher_query = await cypher_gen.generate(question)
    return db.fetch_all(cypher_query)


def ask_graph(
    question: str, *, memgraph_host: str = "localhost", memgraph_port: int = 7687
) -> Any:
    """Natural-language question → Cypher → list[dict]."""
    with MemgraphIngestor(memgraph_host, memgraph_port) as db:
        return asyncio.run(_ask_async(question, db))


# --- code snippet helper -------------------------------------------------- #

_code_retriever = None


def find_snippet(
    qualified_name: str,
    *,
    project_root: str = ".",
    memgraph_host: str = "localhost",
    memgraph_port: int = 7687,
) -> Any:
    """Return retrieval.schemas.CodeSnippet for <qualified_name>."""
    with MemgraphIngestor(memgraph_host, memgraph_port) as db:
        retriever = CodeRetriever(project_root=project_root, ingestor=db)
        return asyncio.run(retriever.find_code_snippet(qualified_name))
