"""阶段五知识图谱的本体定义 — 开发者改图谱时的单一真值源

提供：
- ConceptType: 7 种节点类型枚举
- RelationType: 8 类关系枚举
- PropertySpec: 属性约束（类型/范围/必填/默认）
- RelationSpec: 关系端点约束（domain/range）+ 是否双向
- 校验函数: validate_concept / validate_relation / validate_extraction_payload

调用方：
- kg/extract.py (LLM 抽取结果校验，2B)
- kg/schema.py (Neo4j 约束生成，2A)
- kg/graph_rag.py (查询时类型检查，可选)
- tests/test_ontology.py (单测)
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ── 节点类型 ──


class ConceptType(str, Enum):
    KP = "KP"
    THEOREM = "Theorem"
    METHOD = "Method"
    DEFINITION = "Definition"
    FORMULA = "Formula"
    MISTAKE = "Mistake"
    EXAMPLE = "Example"


class Subject(str, Enum):
    """学科（含考研数学的 3 个子学科）。跨学科关系允许但起点 confidence 较低。"""
    MATH_CALC   = "math-calc"
    MATH_LINALG = "math-linalg"
    MATH_PROB   = "math-prob"
    ENGLISH     = "english"
    POLITICS    = "politics"
    UNKNOWN     = "unknown"


# ── 关系类型 ──


class RelationType(str, Enum):
    PREREQUISITE_OF = "PREREQUISITE_OF"
    DEFINES = "DEFINES"
    EXAMPLE_OF = "EXAMPLE_OF"
    USED_IN = "USED_IN"
    COMMON_MISTAKE_OF = "COMMON_MISTAKE_OF"
    GENERALIZES = "GENERALIZES"
    SPECIALIZES = "SPECIALIZES"
    CONTRASTS_WITH = "CONTRASTS_WITH"


# ── 属性约束 ──


@dataclass(frozen=True)
class PropertySpec:
    """单属性的类型/范围/必填/默认约束。"""
    name: str
    type: str
    required: bool = False
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_length: Optional[int] = None
    description: str = ""


# ── 关系规格 ──


@dataclass(frozen=True)
class RelationSpec:
    """单类关系的 domain/range + 属性 + 是否对称。"""
    name: RelationType
    src_types: frozenset[ConceptType]
    dst_types: frozenset[ConceptType]
    properties: tuple[PropertySpec, ...] = ()
    is_symmetric: bool = False
    description: str = ""


# ── 节点类型规格 ──


@dataclass(frozen=True)
class ConceptTypeSpec:
    """单种 Concept 类型的描述 + 属性约束。"""
    name: ConceptType
    description: str
    properties: tuple[PropertySpec, ...] = ()


# ── 通用属性（节点和关系都可能有）──


_COMMON_CONCEPT_PROPS: tuple[PropertySpec, ...] = (
    PropertySpec("id", "str", required=True, max_length=200,
                 description='格式: "{type}:{slug}"，如 "kp:MA-INT-001"'),
    PropertySpec("name", "str", required=True, max_length=100),
    PropertySpec("aliases", "list[str]", required=False, description="别名列表"),
    PropertySpec("definition", "str", required=False, max_length=500),
    PropertySpec("difficulty", "float", required=False, default=0.5, min_value=0.0, max_value=1.0),
    PropertySpec("level", "int", required=False, default=2, min_value=1, max_value=5),
    PropertySpec("embedding", "list[float]", required=False, description="1536 维向量"),
    PropertySpec("embedding_model", "str", required=False, max_length=64),
    PropertySpec("embedded_at", "datetime", required=False),
    PropertySpec("confidence", "float", required=False, default=0.5, min_value=0.0, max_value=1.0),
    PropertySpec("source", "str", required=False, max_length=64,
                 description='如 "textbook:tongji-gaoshux7" / "syllabus:考研大纲"'),
    PropertySpec("source_ref", "str", required=False, max_length=200),
    PropertySpec("subject", "str", required=False, default="unknown", max_length=32,
                 description="Subject enum value: math-calc/math-linalg/math-prob/english/politics/unknown"),
    PropertySpec("status", "str", required=False, default="active", max_length=20,
                 description="active | disputed | archived | pending_review"),
    PropertySpec("created_at", "datetime", required=False),
    PropertySpec("updated_at", "datetime", required=False),
)

_COMMON_RELATION_PROPS: tuple[PropertySpec, ...] = (
    PropertySpec("confidence", "float", required=True, default=0.5, min_value=0.0, max_value=1.0),
    PropertySpec("disputed", "bool", required=False, default=False),
    PropertySpec("source", "str", required=False, max_length=64),
    PropertySpec("created_at", "datetime", required=False),
    PropertySpec("updated_at", "datetime", required=False),
)


# ── 节点类型注册表 ──


CONCEPT_TYPES: dict[ConceptType, ConceptTypeSpec] = {
    ConceptType.KP: ConceptTypeSpec(
        name=ConceptType.KP,
        description="考点（来自官方大纲，PG knowledge_points 同步）",
        properties=_COMMON_CONCEPT_PROPS + (
            PropertySpec("code", "str", required=False, max_length=64,
                         description="业务码，如 'MATH_INT_001'"),
            PropertySpec("pg_kp_id", "int", required=False,
                         description="对齐 PG knowledge_points.id 的锚点"),
        ),
    ),
    ConceptType.THEOREM: ConceptTypeSpec(
        name=ConceptType.THEOREM,
        description="定理（从中值定理到柯西积分定理等）",
        properties=_COMMON_CONCEPT_PROPS,
    ),
    ConceptType.METHOD: ConceptTypeSpec(
        name=ConceptType.METHOD,
        description="方法（如换元积分法、分部积分法、夹逼法）",
        properties=_COMMON_CONCEPT_PROPS,
    ),
    ConceptType.DEFINITION: ConceptTypeSpec(
        name=ConceptType.DEFINITION,
        description="定义（极限的定义、导数的几何意义等）",
        properties=_COMMON_CONCEPT_PROPS,
    ),
    ConceptType.FORMULA: ConceptTypeSpec(
        name=ConceptType.FORMULA,
        description="公式（牛顿-莱布尼茨公式、欧拉公式等）",
        properties=_COMMON_CONCEPT_PROPS,
    ),
    ConceptType.MISTAKE: ConceptTypeSpec(
        name=ConceptType.MISTAKE,
        description="典型错因（换元忘回代、无穷小替换漏判等）",
        properties=_COMMON_CONCEPT_PROPS,
    ),
    ConceptType.EXAMPLE: ConceptTypeSpec(
        name=ConceptType.EXAMPLE,
        description="例题模式（用夹逼法求极限的典型题）",
        properties=_COMMON_CONCEPT_PROPS,
    ),
}


# ── 关系类型注册表 ──


RELATION_SPECS: dict[RelationType, RelationSpec] = {
    RelationType.PREREQUISITE_OF: RelationSpec(
        name=RelationType.PREREQUISITE_OF,
        src_types=frozenset({ConceptType.KP, ConceptType.THEOREM,
                              ConceptType.METHOD, ConceptType.DEFINITION}),
        dst_types=frozenset({ConceptType.KP, ConceptType.THEOREM, ConceptType.METHOD}),
        properties=_COMMON_RELATION_PROPS,
        is_symmetric=False,
        description="A 是 B 的前置知识（单向，方向: 难→易 或 高级→基础）",
    ),
    RelationType.DEFINES: RelationSpec(
        name=RelationType.DEFINES,
        src_types=frozenset({ConceptType.DEFINITION}),
        dst_types=frozenset({c for c in ConceptType}),
        properties=_COMMON_RELATION_PROPS,
        is_symmetric=False,
        description="A 定义了 B",
    ),
    RelationType.EXAMPLE_OF: RelationSpec(
        name=RelationType.EXAMPLE_OF,
        src_types=frozenset({ConceptType.EXAMPLE}),
        dst_types=frozenset({ConceptType.METHOD, ConceptType.THEOREM, ConceptType.FORMULA}),
        properties=_COMMON_RELATION_PROPS,
        is_symmetric=False,
        description="A 是 B 的一个例子",
    ),
    RelationType.USED_IN: RelationSpec(
        name=RelationType.USED_IN,
        src_types=frozenset({ConceptType.METHOD, ConceptType.FORMULA}),
        dst_types=frozenset({ConceptType.KP}),
        properties=_COMMON_RELATION_PROPS + (
            PropertySpec("frequency", "float", required=False, min_value=0.0, max_value=1.0),
        ),
        is_symmetric=False,
        description="A 方法/公式用于 B 考点",
    ),
    RelationType.COMMON_MISTAKE_OF: RelationSpec(
        name=RelationType.COMMON_MISTAKE_OF,
        src_types=frozenset({ConceptType.MISTAKE}),
        dst_types=frozenset({ConceptType.METHOD, ConceptType.THEOREM,
                              ConceptType.FORMULA, ConceptType.KP}),
        properties=_COMMON_RELATION_PROPS + (
            PropertySpec("rate", "float", required=False, min_value=0.0, max_value=1.0,
                         description="学生犯此错的概率"),
        ),
        is_symmetric=False,
        description="A 错因常出现在 B 知识点上",
    ),
    RelationType.GENERALIZES: RelationSpec(
        name=RelationType.GENERALIZES,
        src_types=frozenset({c for c in ConceptType}),
        dst_types=frozenset({c for c in ConceptType}),
        properties=_COMMON_RELATION_PROPS,
        is_symmetric=False,
        description="A 是 B 的一般化形式（如 定积分 generalizes 不定积分）",
    ),
    RelationType.SPECIALIZES: RelationSpec(
        name=RelationType.SPECIALIZES,
        src_types=frozenset({c for c in ConceptType}),
        dst_types=frozenset({c for c in ConceptType}),
        properties=_COMMON_RELATION_PROPS,
        is_symmetric=False,
        description="A 是 B 的特殊化形式（如 不定积分 specializes 换元积分法）",
    ),
    RelationType.CONTRASTS_WITH: RelationSpec(
        name=RelationType.CONTRASTS_WITH,
        src_types=frozenset({c for c in ConceptType}),
        dst_types=frozenset({c for c in ConceptType}),
        properties=_COMMON_RELATION_PROPS,
        is_symmetric=True,
        description="A 与 B 易混淆（双向）",
    ),
}


# ── id 命名规则 ──


ID_PREFIX_TO_TYPE: dict[str, ConceptType] = {
    "kp": ConceptType.KP,
    "theorem": ConceptType.THEOREM,
    "method": ConceptType.METHOD,
    "definition": ConceptType.DEFINITION,
    "formula": ConceptType.FORMULA,
    "mistake": ConceptType.MISTAKE,
    "example": ConceptType.EXAMPLE,
}


def type_from_id(concept_id: str) -> Optional[ConceptType]:
    """从 id 推断 type，如 'kp:MA-INT-001' → ConceptType.KP"""
    if ":" not in concept_id:
        return None
    prefix = concept_id.split(":", 1)[0]
    return ID_PREFIX_TO_TYPE.get(prefix)


def make_contrast_pair(a_id: str, b_id: str) -> list[tuple[str, str]]:
    """CONTRASTS_WITH 对称工具：返回 [(A,B), (B,A)]。

    写入 Neo4j 时用此函数生成两条边，避免单边记录导致反向查询失败。
    RelationSpec.is_symmetric=True 已声明此关系需要双向写入。
    """
    return [(a_id, b_id), (b_id, a_id)]


SUBJECT_VALUES: frozenset[str] = frozenset(s.value for s in Subject)


# ── 校验函数 ──


def validate_concept_properties(type_: ConceptType, props: dict) -> list[str]:
    """校验 Concept 属性。返回错误列表，空 = 通过。"""
    errors: list[str] = []
    spec = CONCEPT_TYPES.get(type_)
    if not spec:
        return [f"unknown concept type: {type_}"]
    for p in spec.properties:
        val = props.get(p.name)
        if val is None:
            if p.required:
                errors.append(f"missing required: {p.name}")
            continue
        _check_value(p, val, f"concept {props.get('id', '?')}.{p.name}", errors)
    return errors


def validate_relation(
    src_type: ConceptType, rel: RelationType, dst_type: ConceptType
) -> list[str]:
    """校验关系端点类型。"""
    errors: list[str] = []
    spec = RELATION_SPECS.get(rel)
    if not spec:
        return [f"unknown relation: {rel}"]
    if src_type not in spec.src_types:
        errors.append(
            f"src type {src_type} not allowed for {rel} "
            f"(allowed: {sorted(t.value for t in spec.src_types)})"
        )
    if dst_type not in spec.dst_types:
        errors.append(
            f"dst type {dst_type} not allowed for {rel} "
            f"(allowed: {sorted(t.value for t in spec.dst_types)})"
        )
    return errors


def validate_relation_properties(rel: RelationType, props: dict) -> list[str]:
    """校验关系属性。"""
    errors: list[str] = []
    spec = RELATION_SPECS.get(rel)
    if not spec:
        return [f"unknown relation: {rel}"]
    for p in spec.properties:
        val = props.get(p.name)
        if val is None:
            if p.required:
                errors.append(f"relation missing required: {p.name}")
            continue
        _check_value(p, val, f"relation.{p.name}", errors)
    return errors


def validate_extraction_payload(
    result: dict, existing_concept_ids: set[str] | None = None
) -> list[str]:
    """LLM 抽取结果的整体校验。

    result = {"concepts": [...], "relations": [...]}
    """
    errors: list[str] = []
    existing_concept_ids = existing_concept_ids or set()
    local_ids = {c["id"] for c in result.get("concepts", []) if "id" in c}
    valid_ids = existing_concept_ids | local_ids

    for c in result.get("concepts", []):
        cid = c.get("id", "?")
        try:
            type_ = ConceptType(c.get("type"))
        except (ValueError, KeyError):
            errors.append(f"concept {cid}: unknown type {c.get('type')!r}")
            continue
        inferred = type_from_id(cid)
        if inferred is not None and inferred != type_:
            errors.append(
                f"concept {cid}: id prefix implies {inferred.value} "
                f"but type field is {type_.value}"
            )
        errors.extend(f"concept {cid}: {e}" for e in validate_concept_properties(type_, c))

    for r in result.get("relations", []):
        from_id = r.get("from", "?")
        to_id = r.get("to", "?")
        rel_name = r.get("rel")
        try:
            rel = RelationType(rel_name)
        except ValueError:
            errors.append(f"relation {from_id}->{to_id}: unknown rel {rel_name!r}")
            continue

        if from_id not in valid_ids:
            errors.append(f"relation {from_id}-[{rel_name}]->{to_id}: unknown from")
            continue
        if to_id not in valid_ids:
            errors.append(f"relation {from_id}-[{rel_name}]->{to_id}: unknown to")
            continue

        from_type = type_from_id(from_id)
        to_type = type_from_id(to_id)
        if from_type and to_type:
            for e in validate_relation(from_type, rel, to_type):
                errors.append(f"relation {from_id}-[{rel_name}]->{to_id}: {e}")

        for e in validate_relation_properties(rel, r):
            errors.append(f"relation {from_id}-[{rel_name}]->{to_id}: {e}")

        if from_id == to_id:
            errors.append(f"relation {from_id}-[{rel_name}]->{to_id}: self-loop")

    return errors


# ── 内部 ──


def _check_value(p: PropertySpec, val: Any, label: str, errors: list[str]) -> None:
    if p.type == "str" and not isinstance(val, str):
        errors.append(f"{label}: expected str, got {type(val).__name__}")
    elif p.type == "int" and not isinstance(val, int):
        errors.append(f"{label}: expected int, got {type(val).__name__}")
    elif p.type == "float" and not isinstance(val, (int, float)):
        errors.append(f"{label}: expected float, got {type(val).__name__}")
    elif p.type == "bool" and not isinstance(val, bool):
        errors.append(f"{label}: expected bool, got {type(val).__name__}")
    elif p.type == "list[str]" and not (isinstance(val, list) and all(isinstance(x, str) for x in val)):
        errors.append(f"{label}: expected list[str], got {type(val).__name__}")
    elif p.type == "list[float]" and not (isinstance(val, list) and all(isinstance(x, (int, float)) for x in val)):
        errors.append(f"{label}: expected list[float], got {type(val).__name__}")
    elif p.type == "datetime" and not isinstance(val, str):
        pass

    if isinstance(val, (int, float)):
        if p.min_value is not None and val < p.min_value:
            errors.append(f"{label}: {val} < min {p.min_value}")
        if p.max_value is not None and val > p.max_value:
            errors.append(f"{label}: {val} > max {p.max_value}")
    if isinstance(val, str) and p.max_length is not None and len(val) > p.max_length:
        errors.append(f"{label}: length {len(val)} > max {p.max_length}")
