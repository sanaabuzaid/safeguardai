import logging
from pathlib import Path
from typing import Dict, List

import chromadb
from chromadb.config import Settings as ChromaSettings
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger('safety')

_rag_instance = None


def get_rag() -> 'SafetyRAG':
    """Return a shared SafetyRAG singleton to avoid re-creating clients per request."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = SafetyRAG()
    return _rag_instance


class SafetyRAG:
    """Chroma-backed RAG: chunk, embed with OpenAI, store and search in Chroma."""

    def __init__(self):
        cfg = settings.SAFEGUARDAI
        self.CHUNK_SIZE = cfg['RAG_CHUNK_SIZE']
        self.CHUNK_OVERLAP = cfg['RAG_CHUNK_OVERLAP']
        self.EMBEDDING_MODEL = cfg['RAG_EMBEDDING_MODEL']

        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        persist_dir = cfg['CHROMA_PERSIST_DIR']
        self.collection_name = cfg['CHROMA_COLLECTION_NAME']
        persist_dir = str(Path(persist_dir).resolve())

        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        count = self.collection.count()
        logger.info(
            f"SafetyRAG initialised | chunks={count} | persist_dir={persist_dir}"
        )

    def load_document(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"Document loaded | path={file_path} | size={len(content)} chars")
            return content
        except FileNotFoundError:
            logger.error(f"Document not found | path={file_path}")
            raise
        except IOError as e:
            logger.error(f"Failed to read document | path={file_path} | error={e}")
            raise

    def chunk_text(self, text: str) -> List[str]:
        words = text.split()
        chunks = []
        start = 0

        while start < len(words):
            current_chunk = []
            current_length = 0
            i = start

            while i < len(words) and current_length < self.CHUNK_SIZE:
                current_chunk.append(words[i])
                current_length += len(words[i]) + 1
                i += 1

            chunks.append(' '.join(current_chunk))

            overlap_chars = 0
            step_back = 0
            for word in reversed(current_chunk):
                overlap_chars += len(word) + 1
                step_back += 1
                if overlap_chars >= self.CHUNK_OVERLAP:
                    break

            start = i - step_back

            if start <= (i - len(current_chunk)):
                start = i - len(current_chunk) + 1

        logger.debug(f"Text chunked | total_chunks={len(chunks)}")
        return chunks

    def get_embedding(self, text: str) -> List[float]:
        try:
            response = self.openai_client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed | error={e}")
            raise

    def _get_sources_list(self) -> List[str]:
        """Return sorted list of unique source names from Chroma metadata."""
        try:
            # Chroma returns all when no ids/where given; limit to metadata only
            data = self.collection.get(include=["metadatas"])
            metadatas = data.get("metadatas") or []
            sources = set()
            for m in metadatas:
                if isinstance(m, dict) and m.get("source"):
                    sources.add(str(m["source"]))
            return sorted(sources)
        except Exception as e:
            logger.warning(f"RAG: _get_sources_list failed: {e}")
        return []

    def is_document_indexed(self, document_title: str) -> bool:
        try:
            return document_title in self._get_sources_list()
        except Exception:
            return False

    def add_document(self, file_path: str, document_title: str, force: bool = False):
        already_indexed = self.is_document_indexed(document_title)

        if not force and already_indexed:
            logger.info(f"Document already indexed — skipping | title={document_title}")
            return

        logger.info(f"Indexing document | title={document_title}")

        text = self.load_document(file_path)
        chunks = self.chunk_text(text)
        logger.info(f"Document chunked | title={document_title} | chunks={len(chunks)}")

        if force and already_indexed:
            try:
                self.collection.delete(where={"source": document_title})
            except Exception as e:
                logger.warning(f"RAG: delete existing source failed: {e}")

        ids = []
        embeddings = []
        metadatas = []
        documents = []
        first_error = None
        for i, chunk in enumerate(chunks):
            try:
                embedding = self.get_embedding(chunk)
                chunk_id = f"{document_title}_chunk_{i}"
                ids.append(chunk_id)
                embeddings.append(embedding)
                metadatas.append({
                    "source": document_title,
                    "chunk_index": i,
                    "file_path": file_path,
                })
                documents.append(chunk)
            except Exception as e:
                if first_error is None:
                    first_error = e
                logger.error(
                    f"Failed to index chunk | "
                    f"title={document_title} | chunk={i} | error={e}"
                )

        if ids:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )
        elif chunks and first_error is not None:
            msg = str(first_error).strip() or "Embedding API error"
            if "api_key" in msg.lower() or "authentication" in msg.lower():
                msg = "OpenAI API key is missing or invalid. Check OPENAI_API_KEY in .env"
            elif "connection" in msg.lower() or "timeout" in msg.lower():
                msg = "Could not reach OpenAI (connection or timeout). Check network and try again."
            raise RuntimeError(f"Indexing failed: {msg}")

        logger.info(
            f"Document indexed | title={document_title} | "
            f"chunks={len(ids)}/{len(chunks)}"
        )

    def search(self, query: str, n_results: int = 5) -> List[Dict]:
        try:
            count = self.collection.count()
            if count == 0:
                logger.warning("RAG search skipped — collection is empty")
                return []

            query_embedding = self.get_embedding(query)
            k = min(n_results, count)
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )

            # Chroma returns lists of lists (one per query)
            doc_lists = result.get("documents") or [[]]
            meta_lists = result.get("metadatas") or [[]]
            dist_lists = result.get("distances") or [[]]
            docs = doc_lists[0] if doc_lists else []
            metas = meta_lists[0] if meta_lists else []
            dists = dist_lists[0] if dist_lists else []

            formatted = []
            for i, text in enumerate(docs):
                meta = metas[i] if i < len(metas) else {}
                source = meta.get("source", "") if isinstance(meta, dict) else ""
                dist = dists[i] if i < len(dists) else None
                if isinstance(text, str) and text.strip():
                    formatted.append({
                        "text": text,
                        "source": source,
                        "distance": dist,
                    })

            logger.info(
                f"Search complete | query='{query[:50]}' | results={len(formatted)}"
            )
            return formatted

        except Exception as e:
            logger.error(f"Search failed | query='{query[:50]}' | error={e}")
            return []

    def get_stats(self) -> Dict:
        count = self.collection.count()
        sources = self._get_sources_list() if count > 0 else []

        return {
            "total_chunks": count,
            "collection_name": self.collection_name,
            "indexed_sources": sources,
            "total_documents": len(sources),
        }
