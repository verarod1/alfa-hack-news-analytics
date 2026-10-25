import sys
from pathlib import Path

# Добавляем папку backend в пути поиска Python
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os
import glob
import json
import base64
import tempfile
import pymupdf
import chromadb
from chromadb.utils import embedding_functions
from app.services.llm_client import client

# Настройка путей
BASE_DIR = Path(__file__).resolve().parents[2]
if (BASE_DIR.parent / "data").exists():
    DATA_DIR = BASE_DIR.parent / "data"
else:
    DATA_DIR = BASE_DIR / "data"

PDF_DIR = str(DATA_DIR / "raw" / "bank_analytics")

# Теперь мы используем постоянные папки, которые проброшены в Docker
CHROMA_DB_DIR = str(DATA_DIR / "chroma_db")
CACHE_DIR = DATA_DIR / "cache"
CACHE_FILE = str(CACHE_DIR / "extracted_text_cache.json")

# Создаем папки, если их нет
os.makedirs(CHROMA_DB_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

print("Загрузка модели эмбеддингов...")
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="intfloat/multilingual-e5-small"
)

client_db = chromadb.PersistentClient(path=CHROMA_DB_DIR)

# Не удаляем коллекцию, чтобы не парсить всё заново при каждом запуске
collection = client_db.get_or_create_collection(
    name="bank_analytics",
    embedding_function=embedding_fn
)

def extract_with_qwen_vl(pdf_path: str) -> str:
    """Извлечение текста из PDF через Qwen-VL (самая эффективная из разрешенных)."""
    doc = pymupdf.open(pdf_path)
    all_text = ""
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=120)
        img_bytes = pix.tobytes("png")
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        
        print(f"  -> Отправляю стр. {page_num+1} в Qwen-VL...")
        try:
            response = client.chat.completions.create(
                model="qwen/qwen3-vl-30b-a3b-instruct", 
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Распознай весь текст на этой картинке. Выведи только чистый текст без комментариев."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }],
                max_tokens=2000
            )
            all_text += f"\n Страница {page_num+1} \n" + response.choices[0].message.content
        except Exception as e:
            print(f" Ошибка Qwen-VL: {e}")
            all_text += f"\n Страница {page_num+1} \n(Текст не распознан)"
            
    return all_text

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def process_pdfs():
    # Если база уже собрана и не пуста, пропускаем (чтобы не парсить при каждом вызове)
    if collection.count() > 0:
        print(f" База уже содержит {collection.count()} кусков. Пропускаем загрузку.")
        return

    pdf_files = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    if not pdf_files:
        print(" PDF файлы не найдены!")
        return

    # Загружаем кэш, если он есть. Если нет - создаем пустой словарь.
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
            print(f" Загружен кэш. В нем {len(cache)} файлов.")

    new_files_found = False

    # Проходимся по PDF. Если файла нет в кэше - запускаем CV (Qwen-VL).
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        if filename not in cache:
            print(f" Найден НОВЫЙ файл: {filename}. Запускаю Qwen-VL...")
            cache[filename] = extract_with_qwen_vl(pdf_path)
            new_files_found = True

    # Сохраняем обновленный кэш
    if new_files_found:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(" Кэш обновлен!")

    print("Нарезаю текст и загружаю в векторную базу...")
    total_chunks = 0
    for filename, file_data in cache.items():
        full_text = "\n".join([str(text) for page, text in file_data.items()]) if isinstance(file_data, dict) else str(file_data)
        if not full_text.strip():
            continue
        
        chunks = chunk_text(full_text)
        metadatas = [{"document_title": filename, "page": 1} for _ in chunks]
        ids = [f"{filename}_c{i}" for i in range(len(chunks))]
        
        collection.add(documents=chunks, metadatas=metadatas, ids=ids)
        total_chunks += len(chunks)

    print(f" База готова! Всего кусков: {total_chunks}")

def retrieve_analytics(query: str, top_k: int = 3) -> list[dict]:
    try:
        results = collection.query(query_texts=[query], n_results=top_k)
    except Exception:
        return []

    formatted_results = []
    if results['documents'] and results['documents'][0]:
        for i in range(len(results['documents'][0])):
            formatted_results.append({
                "text": results['documents'][0][i],
                "document_title": results['metadatas'][0][i]["document_title"],
                "page": results['metadatas'][0][i]["page"]
            })
    return formatted_results

if __name__ == "__main__":
    process_pdfs()
    print("\nТЕСТ ПОИСКА")
    results = retrieve_analytics("ключевая ставка инфляция")
    for res in results:
        print(f" {res['document_title']}: {res['text'][:100]}...")