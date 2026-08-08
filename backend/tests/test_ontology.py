"""测试 kg/ontology.py — 阶段五本体定义的校验函数"""
import pytest

from kg.ontology import (
    CONCEPT_TYPES,
    RELATION_SPECS,
    ConceptType,
    RelationType,
    type_from_id,
    validate_concept_properties,
    validate_extraction_payload,
    validate_relation,
    validate_relation_properties,
)


def test_concept_types_count():
    assert len(CONCEPT_TYPES) == 7


def test_concept_types_have_all_required_types():
    expected = {ConceptType.KP, ConceptType.THEOREM, ConceptType.METHOD,
                ConceptType.DEFINITION, ConceptType.FORMULA, ConceptType.MISTAKE,
                ConceptType.EXAMPLE}
    assert set(CONCEPT_TYPES.keys()) == expected


def test_relation_types_count():
    assert len(RELATION_SPECS) == 8


def test_relation_types_have_all_required():
    expected = {RelationType.PREREQUISITE_OF, RelationType.DEFINES,
                RelationType.EXAMPLE_OF, RelationType.USED_IN,
                RelationType.COMMON_MISTAKE_OF, RelationType.GENERALIZES,
                RelationType.SPECIALIZES, RelationType.CONTRASTS_WITH}
    assert set(RELATION_SPECS.keys()) == expected


def test_type_from_id():
    assert type_from_id("kp:MA-INT-001") == ConceptType.KP
    assert type_from_id("method:u-substitution") == ConceptType.METHOD
    assert type_from_id("mistake:forgot-back-sub") == ConceptType.MISTAKE
    assert type_from_id("unknown:foo") is None
    assert type_from_id("no-prefix") is None


def test_concept_required_fields_missing():
    errors = validate_concept_properties(ConceptType.KP, {"name": "test"})
    assert any("id" in e for e in errors)


def test_concept_id_max_length():
    long_id = "k" * 201
    errors = validate_concept_properties(
        ConceptType.KP, {"id": long_id, "name": "x"}
    )
    assert any("length" in e for e in errors)


def test_concept_difficulty_out_of_range():
    errors = validate_concept_properties(
        ConceptType.METHOD, {"id": "method:x", "name": "x", "difficulty": 1.5}
    )
    assert any("max" in e for e in errors)


def test_concept_confidence_out_of_range():
    errors = validate_concept_properties(
        ConceptType.THEOREM, {"id": "theorem:x", "name": "x", "confidence": -0.1}
    )
    assert any("min" in e for e in errors)


def test_concept_unknown_type():
    errors = validate_concept_properties(ConceptType.KP, {"id": "foo", "name": "x"})
    assert errors == []


def test_relation_valid():
    spec = validate_relation(
        ConceptType.METHOD, RelationType.PREREQUISITE_OF, ConceptType.KP
    )
    assert spec == []


def test_relation_wrong_src_type():
    errors = validate_relation(
        ConceptType.MISTAKE, RelationType.PREREQUISITE_OF, ConceptType.KP
    )
    assert any("src" in e for e in errors)


def test_relation_wrong_dst_type():
    errors = validate_relation(
        ConceptType.KP, RelationType.PREREQUISITE_OF, ConceptType.MISTAKE
    )
    assert any("dst" in e for e in errors)


def test_relation_defines_only_from_definition():
    errors = validate_relation(
        ConceptType.KP, RelationType.DEFINES, ConceptType.METHOD
    )
    assert any("src" in e for e in errors)


def test_relation_contrasts_with_is_symmetric():
    assert RELATION_SPECS[RelationType.CONTRASTS_WITH].is_symmetric is True


def test_relation_prerequisite_is_not_symmetric():
    assert RELATION_SPECS[RelationType.PREREQUISITE_OF].is_symmetric is False


def test_relation_confidence_required():
    errors = validate_relation_properties(RelationType.PREREQUISITE_OF, {})
    assert any("confidence" in e for e in errors)


def test_payload_happy_path():
    result = {
        "concepts": [
            {"id": "kp:MA-INT-001", "name": "不定积分", "type": "KP", "level": 2},
            {"id": "method:u-sub", "name": "换元积分法", "type": "Method", "level": 2},
        ],
        "relations": [
            {"from": "method:u-sub", "rel": "PREREQUISITE_OF",
             "to": "kp:MA-INT-001", "confidence": 0.92},
        ],
    }
    errors = validate_extraction_payload(result)
    assert errors == [], f"unexpected errors: {errors}"


def test_payload_unknown_relation_type():
    result = {
        "concepts": [{"id": "kp:x", "name": "x", "type": "KP"}],
        "relations": [{"from": "kp:x", "rel": "WEAK", "to": "kp:x", "confidence": 0.5}],
    }
    errors = validate_extraction_payload(result)
    assert any("unknown rel" in e for e in errors)


def test_payload_unknown_endpoint():
    result = {
        "concepts": [{"id": "kp:x", "name": "x", "type": "KP"}],
        "relations": [{"from": "kp:missing", "rel": "PREREQUISITE_OF",
                       "to": "kp:x", "confidence": 0.5}],
    }
    errors = validate_extraction_payload(result)
    assert any("unknown from" in e for e in errors)


def test_payload_self_loop_rejected():
    result = {
        "concepts": [{"id": "kp:x", "name": "x", "type": "KP"}],
        "relations": [{"from": "kp:x", "rel": "PREREQUISITE_OF",
                       "to": "kp:x", "confidence": 0.5}],
    }
    errors = validate_extraction_payload(result)
    assert any("self-loop" in e for e in errors)


def test_payload_id_prefix_mismatch():
    result = {
        "concepts": [{"id": "method:u-sub", "name": "换元", "type": "KP"}],
        "relations": [],
    }
    errors = validate_extraction_payload(result)
    assert any("prefix implies" in e for e in errors)


def test_payload_with_existing_concepts():
    result = {
        "concepts": [
            {"id": "method:u-sub", "name": "换元", "type": "Method"},
        ],
        "relations": [
            {"from": "method:u-sub", "rel": "PREREQUISITE_OF",
             "to": "kp:MA-INT-001", "confidence": 0.9},
        ],
    }
    errors = validate_extraction_payload(
        result, existing_concept_ids={"kp:MA-INT-001"}
    )
    assert errors == [], f"unexpected errors: {errors}"


def test_payload_confidence_below_min():
    result = {
        "concepts": [
            {"id": "kp:a", "name": "A", "type": "KP"},
            {"id": "kp:b", "name": "B", "type": "KP"},
        ],
        "relations": [
            {"from": "kp:a", "rel": "PREREQUISITE_OF", "to": "kp:b", "confidence": 1.5},
        ],
    }
    errors = validate_extraction_payload(result)
    assert any("max" in e for e in errors)


def test_payload_used_in_with_wrong_dst():
    result = {
        "concepts": [
            {"id": "method:u-sub", "name": "换元", "type": "Method"},
            {"id": "method:by-parts", "name": "分部", "type": "Method"},
        ],
        "relations": [
            {"from": "method:u-sub", "rel": "USED_IN",
             "to": "method:by-parts", "confidence": 0.5},
        ],
    }
    errors = validate_extraction_payload(result)
    assert any("dst" in e for e in errors)


# ===== 阶段五·2A 新增 =====

class TestSubjectEnum:
    def test_subject_values(self):
        from kg.ontology import Subject
        assert Subject.MATH_CALC.value == "math-calc"
        assert Subject.MATH_LINALG.value == "math-linalg"
        assert Subject.MATH_PROB.value == "math-prob"
        assert Subject.UNKNOWN.value == "unknown"

    def test_subject_field_in_common_props(self):
        from kg.ontology import _COMMON_CONCEPT_PROPS
        names = {p.name for p in _COMMON_CONCEPT_PROPS}
        assert "subject" in names
        assert "confidence" in names

    def test_subject_values_frozenset(self):
        from kg.ontology import SUBJECT_VALUES
        assert "math-calc" in SUBJECT_VALUES
        assert "unknown" in SUBJECT_VALUES
        assert "magic" not in SUBJECT_VALUES


class TestInitialConfidence:
    def test_concept_default_is_0_5(self):
        from kg.ontology import _COMMON_CONCEPT_PROPS
        conf = next(p for p in _COMMON_CONCEPT_PROPS if p.name == "confidence")
        assert conf.default == 0.5

    def test_relation_default_is_0_5(self):
        from kg.ontology import _COMMON_RELATION_PROPS
        conf = next(p for p in _COMMON_RELATION_PROPS if p.name == "confidence")
        assert conf.default == 0.5


class TestMakeContrastPair:
    def test_returns_both_directions(self):
        from kg.ontology import make_contrast_pair
        pair = make_contrast_pair("concept:a", "concept:b")
        assert pair == [("concept:a", "concept:b"), ("concept:b", "concept:a")]

    def test_idempotent_in_reversed_input(self):
        from kg.ontology import make_contrast_pair
        p1 = make_contrast_pair("a", "b")
        p2 = make_contrast_pair("b", "a")
        # 两个方向都产生 (a,b) + (b,a)
        assert set(p1) == set(p2)
