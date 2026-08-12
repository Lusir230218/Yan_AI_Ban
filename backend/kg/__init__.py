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
# 阶段五·2D 飞轮
from kg.flywheel_ema import (
    EMAConfig, batch_update, learning_rate, time_decay, update,
)
from kg.flywheel_signals import (
    fetch_gap_questions, fetch_total_user_count,
    signals_cross_source, signals_explicit_feedback,
    signals_implicit_feedback,
)
from kg.dispute import (
    detect_cycles, detect_low_confidence,
    export_to_review_queue, mark_disputed,
)
from kg.admin_concepts import (
    archive_concept, merge_concepts, restore_concept,
)
from kg.flywheel import weekly_flywheel_update
from kg.metrics import (
    concepts_confidence_avg, disputes_exported_total,
    flywheel_runs_total, signals_total,
)
from kg.scheduler import start_scheduler, stop_scheduler

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
    # 阶段五·2D 飞轮
    "EMAConfig", "update", "batch_update", "learning_rate", "time_decay",
    "signals_explicit_feedback", "signals_implicit_feedback",
    "signals_cross_source", "fetch_total_user_count", "fetch_gap_questions",
    "detect_cycles", "detect_low_confidence",
    "mark_disputed", "export_to_review_queue",
    "merge_concepts", "archive_concept", "restore_concept",
    "weekly_flywheel_update",
    "flywheel_runs_total", "signals_total",
    "disputes_exported_total", "concepts_confidence_avg",
    "start_scheduler", "stop_scheduler",
]