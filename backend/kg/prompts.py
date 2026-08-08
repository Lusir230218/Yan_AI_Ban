"""LLM prompt 模板。

**关键**：节点类型 / 关系类型 / 端点约束都从 `kg.ontology` 动态生成——
ontology 是单一真值源。新增 ConceptType / RelationType 时 prompt 自动同步。

**花括号转义约定**：本 prompt 模板会被 Python `str.format()` 调用两次：
1. 模块加载时 `_PROMPT_TEMPLATE.format(node_types=..., relation_types=..., id_rules=..., endpoint_constraints=...)` —
   此时 `{{xxx}}` 占位符（动态字段）需用 `{{` `}}` 双重转义，输出单 `{xxx}`；
2. extract.py 调 `TEXTBOOK_EXTRACT_PROMPT.format(existing_concepts_json=..., subject=..., text_chunk=...)` —
   此时仍残留的 `{xxx}` 单占位符会被第二次替换。

为了让 LLM 看到的最终 prompt 仍含 JSON 字面 `{ ... }`，JSON 示例块中的 `{` `}`
必须用 **四重花括号** `{{{{` `}}}}`：
- 模块加载后 → `{{` `}}`
- extract.py 第二次 format 后 → `{` `}`（字面，LLM 看到的最终文本）
"""
from kg.ontology import (
    ConceptType, RelationType,
    CONCEPT_TYPES, RELATION_SPECS, ID_PREFIX_TO_TYPE,
)


def _format_node_types() -> str:
    """节点类型清单，description 来自 ontology。"""
    return "\n".join(
        f"- {ct.value}: {CONCEPT_TYPES[ct].description}"
        for ct in ConceptType
    )


def _format_relation_types() -> str:
    return "\n".join(
        f"- {rt.value}: {RELATION_SPECS[rt].description}"
        for rt in RelationType
    )


def _format_id_rules() -> str:
    """id 前缀 → type 映射，从 ID_PREFIX_TO_TYPE 自动生成。"""
    lines = [
        f"- {ct.value:<11} → {prefix}:<slug>（如 {prefix}:{ct.value.lower()}-example）"
        for prefix, ct in ID_PREFIX_TO_TYPE.items()
    ]
    lines.append("- slug = 小写英文 + 数字 + 连字符，如 limit、ramanujan-formula")
    return "\n".join(lines)


def _format_endpoint_constraints() -> str:
    """端点约束来自 RELATION_SPECS，按 ontology 字段自动生成。"""
    lines = []
    for rt in RelationType:
        spec = RELATION_SPECS[rt]
        src = " / ".join(sorted(t.value for t in spec.src_types))
        dst = " / ".join(sorted(t.value for t in spec.dst_types))
        lines.append(f"- {rt.value} 起点：{src}；终点：{dst}")
    return "\n".join(lines)


# Prompt 模板：module load 时填 ontology 派生字段，
# 运行时字段 {existing_concepts_json}/{subject}/{text_chunk} 在 extract.py 二次 .format()
#
# JSON 示例块里所有 `{` `}` 都用 `{{{{` `}}}}` 四重转义，保证 LLM 看到时是合法 JSON。
# 字符串内嵌的占位符 `{{subject}}` 保持双重转义（最终 `{subject}`，由 extract 替换）。
_PROMPT_TEMPLATE = """
你是考研领域的知识图谱构建助手。从以下教材段落中抽取"概念"和"概念之间的关系"。

## 已存在概念（不要重复，引用其 id）
{{existing_concepts_json}}

## 当前学科
{{subject}}

## 教材段落
{{text_chunk}}

## 节点类型
{node_types}

## 关系类型
{relation_types}

## id 命名规则
{id_rules}

## 端点约束
{endpoint_constraints}

## 输出格式（严格 JSON，无注释、无 markdown 围栏）
{{{{
  "concepts": [
    {{{{
      "id": "method:u-substitution",
      "name": "换元积分法",
      "type": "Method",
      "aliases": ["凑微分法", "变量替换法"],
      "definition": "通过引入新变量将复杂积分化为简单积分的方法",
      "difficulty": 0.6,
      "level": 2,
      "subject": "{{subject}}"
    }}}}
  ],
  "relations": [
    {{{{
      "from": "method:u-substitution",
      "rel": "PREREQUISITE_OF",
      "to": "kp:MA-INT-001",
      "confidence": 0.92
    }}}}
  ]
}}}}

## 重要约束
1. 严格输出 JSON，不要解释、不要 markdown 围栏
2. relations 端点必须出现在 concepts 或「已存在概念」列表中
3. confidence 范围 0.0-1.0
4. 不确定的关系宁可不要（conf < 0.6 不输出）
5. 教材中没有明确说"前置/定义/例子"的不强行抽取
6. 这段如果没有可抽取的概念，返回 {{{{"concepts": [], "relations": []}}}}
"""


TEXTBOOK_EXTRACT_PROMPT = _PROMPT_TEMPLATE.format(
    node_types=_format_node_types(),
    relation_types=_format_relation_types(),
    id_rules=_format_id_rules(),
    endpoint_constraints=_format_endpoint_constraints(),
)
# 此时 {existing_concepts_json}/{subject}/{text_chunk} 仍是占位符，
# extract.py 调 TEXTBOOK_EXTRACT_PROMPT.format(...) 时再填。


# 校验失败重抽 — 把错误信息反馈给 LLM 让它修
RETRY_PROMPT_TAIL = """
---

## 上次输出有如下错误，请修正后重新输出
{errors}

修正方式：
- 字段缺失/非法：补齐或改正
- type / id 前缀不一致：以 id 前缀为准改 type
- 端点不存在：要么把概念加入 concepts，要么删除这条关系
- 自环：删除该关系

再次输出严格 JSON。
"""