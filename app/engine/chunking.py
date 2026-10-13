import uuid
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.core.config import settings

MARKDOWN_HEADERS = [
    ("#", "header_1"),
    ("##", "header_2"),
    ("###", "header_3"),
]


def chunk_documents(documents: list[Document]) -> list[Document]:
    if not documents:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    md_header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS,
        strip_headers=False,
    )

    all_chunks: List[Document] = []

    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        is_markdown = (
            source.lower().endswith(".md")
            or doc.metadata.get("file_type") == "md"
            or ("\n#" in doc.page_content or doc.page_content.startswith("#"))
        )

        if is_markdown and len(doc.page_content) > settings.CHUNK_OVERLAP:
            try:
                header_splits = md_header_splitter.split_text(doc.page_content)
                for h_split in header_splits:
                    combined_meta = {**doc.metadata, **h_split.metadata}
                    headers_found = [
                        h_split.metadata[k]
                        for k in ["header_1", "header_2", "header_3"]
                        if k in h_split.metadata
                    ]
                    if headers_found:
                        combined_meta["section_path"] = " > ".join(headers_found)

                    section_doc = Document(
                        page_content=h_split.page_content,
                        metadata=combined_meta,
                    )
                    if len(section_doc.page_content) > settings.CHUNK_SIZE:
                        all_chunks.extend(text_splitter.split_documents([section_doc]))
                    else:
                        all_chunks.append(section_doc)
                continue
            except Exception:
                pass

        all_chunks.extend(text_splitter.split_documents([doc]))

    for index, chunk in enumerate(all_chunks):
        source = chunk.metadata.get("source", "unknown")
        chunk.metadata["chunk_index"] = index
        chunk.metadata["chunk_id"] = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"{source}:{index}:{chunk.page_content[:80]}")
        )

    return all_chunks
