"""Существующий RAG: постоянный индекс, постраничный кэш и явное добавление PDF.

Индексация запускается отдельно. Импорт модуля и запросы API не вызывают OCR.
"""
import base64
import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from app.settings import ROOT, Settings
from app.services.llm_client import get_client, model_name


def local_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def manifest_path():
    # Пользовательский BANK_MATERIALS_PATH читается Backend отдельно и не перезаписывается.
    return local_path(Settings().ocr_cache_dir) / "bank_materials.json"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


@lru_cache(maxsize=1)
def get_collection():
    settings = Settings()
    os.environ["HF_HOME"] = str(local_path(settings.hf_home))
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    path = local_path(settings.chroma_db_dir)
    path.mkdir(parents=True, exist_ok=True)
    embedding = SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
    client = chromadb.PersistentClient(path=str(path), settings=ChromaSettings(anonymized_telemetry=False))
    # Другие эмбеддинги требуют отдельного индекса. Старые коллекции сохраняются.
    name = "bank_analytics_" + hashlib.sha256(settings.embedding_model.encode()).hexdigest()[:12]
    return client.get_or_create_collection(name, embedding_function=embedding)


def extract_with_qwen_vl(page):
    """Один явный OCR-вызов одной страницы, только по флагу --allow-ocr."""
    image = base64.b64encode(page.get_pixmap(dpi=120).tobytes("png")).decode("ascii")
    response = get_client().chat.completions.create(
        model=model_name("ocr"),
        messages=[{"role": "user", "content": [
            {"type": "text", "text": "Распознай весь текст страницы без комментариев. Не добавляй отсутствующий текст."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image}},
        ]}], max_tokens=Settings().llm_max_tokens,
    )
    choice = response.choices[0]
    text = choice.message.content
    if choice.finish_reason != "stop" or not text or not text.strip():
        raise ValueError("OCR вернул неполную страницу; она не сохранена в кэш")
    return text


def chunk_text(text, chunk_size=600, overlap=100):
    if not 0 <= overlap < chunk_size:
        raise ValueError("Требуется 0 <= overlap < chunk_size")
    return [text[start:start + chunk_size] for start in range(0, len(text), chunk_size - overlap)]


def process_pdfs(*, allow_ocr=False, limit=5):
    # Два индексатора не расходуют OCR-бюджет на одни страницы одновременно.
    import fcntl
    folder = local_path(Settings().ocr_cache_dir)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "index.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _process_pdfs(allow_ocr=allow_ocr, limit=limit)


def _process_pdfs(*, allow_ocr=False, limit=5):
    import pymupdf
    if not 1 <= limit <= 100:
        raise ValueError("limit: 1..100")
    settings = Settings()
    pdfs = sorted(local_path(settings.bank_pdf_dir).glob("*.pdf"))
    documents, indexed, pending = [], [], []
    processed = 0
    seen = set()
    for pdf in pdfs:
        content_hash = hashlib.sha256()
        with pdf.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                content_hash.update(block)
        digest = content_hash.hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        document_id = "bank_" + digest
        cache_path = local_path(settings.ocr_cache_dir) / (digest + ".json")
        cached = json.loads(cache_path.read_text()) if cache_path.exists() else {"pages": {}, "indexed_model": None}
        # Ограничение относится к новым/изменённым документам, уже готовые остаются в манифесте.
        needs_work = cached.get("indexed_model") != settings.embedding_model
        if needs_work and processed >= limit:
            pending.append(pdf.name)
            continue
        if needs_work:
            processed += 1
        with pymupdf.open(pdf) as doc:
            for index, page in enumerate(doc):
                number = str(index + 1)
                if number in cached["pages"]:
                    continue
                text = page.get_text().strip()
                if not text and allow_ocr:
                    text = extract_with_qwen_vl(page)
                if text:
                    cached["pages"][number] = text
                    # Оплаченная страница сохраняется до индексации/обработки следующей.
                    write_json(cache_path, cached)
            complete = len(cached["pages"]) == len(doc)
        if not complete:
            pending.append(pdf.name)
            continue
        pages = [{"page": int(number), "text": text} for number, text in sorted(cached["pages"].items(), key=lambda item: int(item[0]))]
        if needs_work:
            collection = get_collection()
            for page in pages:
                chunks = chunk_text(page["text"])
                collection.upsert(
                    ids=[f"{document_id}_p{page['page']}_c{i}" for i in range(len(chunks))],
                    documents=chunks,
                    metadatas=[{"document_id": document_id, "document_title": pdf.name,
                                "page": page["page"]} for _ in chunks],
                )
            cached["indexed_model"] = settings.embedding_model
            write_json(cache_path, cached)
            indexed.append(pdf.name)
        documents.append({"document_id": document_id, "title": pdf.name, "url": None, "pages": pages})
    write_json(manifest_path(), documents)
    return {"indexed": indexed, "pending": pending, "documents": len(documents)}


def retrieve_analytics(query, top_k=3):
    # Пустой/неподготовленный RAG не загружает модель и не обращается к OCR.
    path = manifest_path()
    if not path.exists() or not local_path(Settings().chroma_db_dir).is_dir():
        return []
    documents = json.loads(path.read_text())
    ids = [item["document_id"] for item in documents]
    if not ids:
        return []
    collection = get_collection()
    count = collection.count()
    if not count:
        return []
    results = collection.query(query_texts=[query], n_results=min(top_k, count),
                               where={"document_id": {"$in": ids}})
    return [{"text": text, **metadata} for text, metadata in
            zip(results["documents"][0], results["metadatas"][0])]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-ocr", action="store_true", help="Разрешить платное распознавание новых страниц")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        print(json.dumps(process_pdfs(allow_ocr=args.allow_ocr, limit=args.limit), ensure_ascii=False))
    except Exception:
        import sys
        print("Индексация не завершена. Проверьте PDF, кэш, embedding-модель и настройки OCR; сохранённые страницы остаются в кэше.", file=sys.stderr)
        sys.exit(1)
