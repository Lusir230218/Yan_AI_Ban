"""kg 模块 — 阶段五知识图谱子系统的公共 API。

下游代码应只从这个文件 import，不要直接 import 内部模块。
- ontology / neo4j_client / schema 全部 re-export
- 抽出 kg_session / / extract / docx_parser / llm_client / prompts 等
"""
from kg.ontology import (
    ConceptType, Subject, RelationType,
    ID_PREFIX_TO_TYPE, type_from_id,
    CONCEPT_TYPES, RELATION_SPECS,
    SUBJECT_VALUES,
    validate_concept_properties, validate_relation,
    validate_relation_properties, validate_extraction_payload,
    make_contrast_pair,
)
from kg.neo4j_client import (
    get_kg_driver, close_kg_driver, kg_session,
    kg_lifespan, current_database,
)
from kg.schema import (
    init_kg_schema, drop_kg_schema,
    list_constraints_and_indexes,
)
from kg.docx_parser import (
    Chunk, parse_docx, to_chunk_files, read_chunk_files,
    MIN_CHUNK, MAX_CHUNK,
)
from kg.llm_client import chat_json, LLMError
from kg.prompts import TEXTBOOK_EXTRACT_PROMPT, RETRY_PROMPT_TAIL
from kg.embedding_pipeline import (
    enqueue_embedding_job, run_worker as embedding_worker,
)
from kg.merge_dups import merge_duplicates
from kg.syllabus_loader import load_syllabus
from kg.extract import cli as extract_cli, run as extract_run

__all__ = [
    # ontology
    "ConceptType", "Subject", "RelationType",
    "ID_PREFIX_TO_TYPE", "type_from_id",
    "CONCEPT_TYPES", "RELATION_SPECS", "SUBJECT_VALUES",
    "validate_concept_properties", "validate_relation",
    "validate_relation_properties", "validate_extraction_payload",
    "make_contrast_pair",
    # neo4j client
    "get_kg_driver", "close_kg_driver", "kg_session",
    "kg_lifespan", "current_database",
    # schema
    "init_kg_schema", "drop_kg_schema",
    "list_constraints_and_indexes",
    # docx parser
    "Chunk", "parse_docx", "to_chunk_files", "read_chunk_files",
    "MIN_CHUNK", "MAX_CHUNK",
    # llm / prompts
    "chat_json", "LLMError",
    "TEXTBOOK_EXTRACT_PROMPT", "RETRY_PROMPT_TAIL",
    # embedding pipeline
    "enqueue_embedding_job", "embedding_worker",
    # extract orchestration
    "merge_duplicates", "load_syllabus",
    "extract_cli", "extract_run",
]