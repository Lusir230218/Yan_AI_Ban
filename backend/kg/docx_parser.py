"""docx 教材解析 + chunking + 落盘。

切分规则（按 Word 段落样式 Heading 1/2/3）：
1. Heading 1 出现 → flush 当前段，开启新章
2. Heading 2/3 → 嵌套小节
3. Normal 段累积进 current list
4. flush 时按 MIN/MAX_CHUNK 切（500-2000 字），不足吞并、过长硬切
5. 标题含 NON_CONTENT_KEYWORDS 的段丢弃

落盘：每个 chunk 一个 JSON 文件 + index.json（详见 to_chunk_files / read_chunk_files）。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from docx import Document


MIN_CHUNK = 300
MAX_CHUNK = 2000
NON_CONTENT_KEYWORDS = ("目录", "前言", "习题", "参考答案", "索引")


@dataclass
class Chunk:
    chunk_id: str          # e.g. "tongji:ch3:s3.2"
    text: str
    chapter: int | None
    section: str | None
    page_hint: str | None


def parse_docx(docx_path: str | Path) -> list[Chunk]:
    """读 docx，按段落样式 Heading 1/2/3 切分。

    假设输入 docx 的标题已用 Word 的 Heading 1/2/3 样式。
    """
    path = Path(docx_path)
    source_label = path.stem
    paragraphs = _iter_paragraphs(path)
    return _split_by_heading(paragraphs, source_label)


def _iter_paragraphs(path: Path) -> list[tuple[str, str]]:
    """返回 [(style_name, text)]，跳过空段。"""
    doc = Document(path)
    out: list[tuple[str, str]] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name if p.style is not None else "Normal"
        out.append((style, text))
    return out


def _split_by_heading(
    paragraphs: list[tuple[str, str]],
    source: str,
) -> list[Chunk]:
    """按 Heading 1/2/3 样式切。每节单独算 chunk_size + 滑窗。"""
    out: list[Chunk] = []
    current: list[tuple[str, str]] = []
    current_h1: str | None = None
    current_h2: str | None = None
    current_h3: str | None = None

    def flush():
        nonlocal current, current_h2, current_h3
        if not current:
            return
        body = "\n".join(t for _, t in current).strip()
        current = []
        if not body:
            return
        first_heading = current_h1 or current_h2 or current_h3 or ""
        if any(k in first_heading for k in NON_CONTENT_KEYWORDS):
            return
        chapter_idx = _extract_chapter_index(current_h1)
        for sub in _window(body, MIN_CHUNK, MAX_CHUNK):
            cid = (
                f"{source}:{_slug(current_h1 or '')}"
                f":{_slug(current_h2 or current_h3 or '')}"
            )
            out.append(Chunk(
                chunk_id=cid,
                text=sub,
                chapter=chapter_idx,
                section=current_h2 or current_h3,
                page_hint=None,
            ))

    for style, text in paragraphs:
        if style == "Heading 1":
            flush()
            current_h1 = text
            current_h2 = None
            current_h3 = None
            current = [(style, text)]
        elif style == "Heading 2":
            flush()
            current_h2 = text
            current_h3 = None
            current.append((style, text))
        elif style == "Heading 3":
            flush()
            current_h3 = text
            current.append((style, text))
        else:
            current.append((style, text))
    flush()
    return out


def _window(text: str, min_size: int, max_size: int) -> list[str]:
    """把长文本切成 ≥min_size 的块，每块 ≤max_size，按段落硬切。"""
    if len(text) <= max_size:
        return [text] if len(text) >= min_size else []
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        candidate = (buf + "\n\n" + p).strip() if buf else p
        if len(candidate) <= max_size:
            buf = candidate
        else:
            if len(buf) >= min_size:
                chunks.append(buf)
            buf = p
    if len(buf) >= min_size:
        chunks.append(buf)
    return chunks


def _extract_chapter_index(h1: str | None) -> int | None:
    if not h1:
        return None
    m = re.match(r"[第]?\s*(\d+)", h1)
    return int(m.group(1)) if m else None


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9一-鿿]+", "-", s.lower()).strip("-")[:64]


# ===== chunk 落盘：每文件 1 个 JSON + 1 个 index =====


def to_chunk_files(
    chunks: list[Chunk],
    output_dir: str | Path,
    source: str,
    subject: str,
) -> Path:
    """把每个 chunk 写成单独 JSON 文件，再写一份 index.json 记录顺序。

    目录布局:
        output_dir/
        ├── index.json
        └── chunks/
            ├── 0001_<safe_chunk_id>.json
            ├── 0002_<safe_chunk_id>.json
            └── ...

    Returns index.json path。
    """
    output_dir = Path(output_dir)
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    chunk_ids: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        safe_id = chunk.chunk_id.replace(":", "-")
        chunk_file = chunks_dir / f"{i:04d}_{safe_id}.json"
        with chunk_file.open("w", encoding="utf-8") as f:
            json.dump(
                {"chunk_id": chunk.chunk_id, "chunk_text": chunk.text},
                f, ensure_ascii=False,
                indent=2,
            )
        chunk_ids.append(chunk.chunk_id)

    index = {
        "source": source,
        "subject": subject,
        "total_chunks": len(chunks),
        "created_at": datetime.utcnow().isoformat(),
        "chunk_ids": chunk_ids,
    }
    index_path = output_dir / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return index_path


def read_chunk_files(index_path: str | Path) -> list[Chunk]:
    """从 index.json + chunks/*.json 还原 list[Chunk]。"""
    base = Path(index_path).parent
    index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    out: list[Chunk] = []
    for i, cid in enumerate(index["chunk_ids"], start=1):
        safe_id = cid.replace(":", "-")
        chunk_file = base / "chunks" / f"{i:04d}_{safe_id}.json"
        data = json.loads(chunk_file.read_text(encoding="utf-8"))
        out.append(Chunk(
            chunk_id=data["chunk_id"],
            text=data["chunk_text"],
            chapter=None,
            section=None,
            page_hint=None,
        ))
    return out