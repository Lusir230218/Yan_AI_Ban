"""kg 模块 — 阶段五知识图谱子系统的公共 API。

下游代码应只从这个文件 import，不要直接 import 内部模块。
- ontology / neo4j_client / schema 全部 re-export
- 抽出 kg_session / init_kg_schema / list_constraints_and_indexes
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
]
