"""Local codebase discovery toolkit for INGOT.

Provides deterministic, Python-native tools for codebase analysis
that run before and after AI agents, ensuring plan quality is
independent of backend capabilities.

Modules:
    file_index: Fast file indexing with fuzzy search
    grep_engine: Python-native regex search across indexed files
    citation_verifier: Verify researcher citation accuracy against disk
    manifest_parser: Build manifest analysis for module structure
    test_mapper: Convention-based source-to-test file mapping
    context_builder: Orchestrate discovery tools into structured reports
"""

__all__ = [
    "CitationVerifier",
    "ContextBuilder",
    "FileIndex",
    "GrepEngine",
    "ManifestParser",
    "TestMapper",
]
