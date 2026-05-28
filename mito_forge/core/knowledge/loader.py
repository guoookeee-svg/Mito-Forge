"""
Document loaders for the knowledge base.

Supports loading from Markdown, YAML (FAQ), and JSON (run experience) sources.
"""

import re
from pathlib import Path
from typing import List, Optional
import yaml

from . import Document


class BaseLoader:
    def load(self, source: Path) -> List[Document]:
        raise NotImplementedError


class MarkdownLoader(BaseLoader):
    def load(self, source: Path) -> List[Document]:
        text = source.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r"\n(?=#{1,3}\s)", text)
        docs: List[Document] = []
        for section in sections:
            section = section.strip()
            if not section:
                continue
            title_match = re.match(r"^#{1,3}\s+(.+)", section)
            title = title_match.group(1).strip() if title_match else source.stem
            docs.append(Document(
                content=section,
                metadata={"title": title, "format": "markdown", "source_file": source.name},
                source=str(source),
            ))
        if not docs:
            docs.append(Document(
                content=text,
                metadata={"title": source.stem, "format": "markdown", "source_file": source.name},
                source=str(source),
            ))
        return docs


class YAMLLoader(BaseLoader):
    def load(self, source: Path) -> List[Document]:
        text = source.read_text(encoding="utf-8", errors="replace")
        items = yaml.safe_load(text)
        if not isinstance(items, list):
            items = [items]
        docs: List[Document] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            faq_id = item.get("id", "unknown")
            tool = item.get("tool", "")
            category = item.get("category", "")
            symptoms = item.get("symptoms", [])
            root_cause = item.get("root_cause", "")
            fix_strategy = item.get("fix_strategy", "")
            suggestions = item.get("suggestions", [])
            sug_text = "\n".join(
                f"  - {s.get('action', '')} (params: {s.get('params', {})})"
                for s in suggestions
            )
            content_parts = [
                f"FAQ: {faq_id}",
                f"Tool: {tool}",
                f"Category: {category}",
                f"Symptoms: {'; '.join(symptoms)}",
                f"Root cause: {root_cause}",
                f"Fix strategy: {fix_strategy}",
                f"Suggestions:\n{sug_text}",
            ]
            content = "\n".join(content_parts)
            docs.append(Document(
                content=content,
                metadata={
                    "faq_id": faq_id,
                    "tool": tool,
                    "category": category,
                    "error_pattern": item.get("error_pattern", ""),
                    "fix_strategy": fix_strategy,
                    "confidence": item.get("confidence", 0.0),
                    "format": "yaml_faq",
                    "source_file": source.name,
                },
                source=str(source),
                doc_id=f"faq_{faq_id}",
            ))
        return docs


class JSONLoader(BaseLoader):
    def load(self, source: Path) -> List[Document]:
        import json
        text = source.read_text(encoding="utf-8", errors="replace")
        data = json.loads(text)
        if isinstance(data, dict):
            data = [data]
        docs: List[Document] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            summary = item.get("summary", "")
            event_type = item.get("event_type", "")
            agent_name = item.get("agent_name", "")
            tags = item.get("tags", [])
            content = f"[{agent_name}] {event_type}: {summary}" if summary else str(item)
            docs.append(Document(
                content=content,
                metadata={
                    "agent_name": agent_name,
                    "event_type": event_type,
                    "tags": tags,
                    "timestamp": item.get("timestamp", ""),
                    "format": "json_experience",
                    "source_file": source.name,
                },
                source=str(source),
            ))
        return docs


def auto_load(source: Path) -> List[Document]:
    suffix = source.suffix.lower()
    if suffix in (".md", ".markdown"):
        return MarkdownLoader().load(source)
    elif suffix in (".yaml", ".yml"):
        return YAMLLoader().load(source)
    elif suffix == ".json":
        return JSONLoader().load(source)
    else:
        return MarkdownLoader().load(source)
