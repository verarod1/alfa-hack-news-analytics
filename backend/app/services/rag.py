import os
import glob
import chromadb
from chromadb.utils import embedding_functions
import pymupdf
import numpy as np
import easyocr
import cv2

PDF_DIR = "data/raw/bank_analytics"
CHROMA_DB_DIR = "data/chroma_db"

print("Загрузка модели эмбеддингов...")
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="intfloat/multilingual-e5-small"
)

print("Инициализация OCR (это может занять минуту при первом запуске)...")
reader = easyocr.Reader(['ru', 'en'], gpu=False)

client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

try:
    client.delete_collection("bank_analytics")
    print("Старая база удалена.")
except:
    pass

collection = client.get_or_create_collection(
    name="bank_analytics",
    embedding_function=embedding_fn
)

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def index_pdfs():
    pdf_files = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    
    if not pdf_files:
        print(f" PDF файлы не найдены в {PDF_DIR}. Проверь путь!")
        return

    print(f"Найдено {len(pdf_files)} PDF. Начинаю индексацию...")
    total_chunks = 0

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"\nЧитаю: {filename}")
        
        doc = pymupdf.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            text = page.get_text("text")
            
            if not text.strip():
                print(f"  -> Стр {page_num+1}: текст не найден, запускаю OCR...")
                pix = page.get_pixmap(dpi=150)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                
                ocr_result = reader.readtext(img, detail=0)
                text = "\n".join(ocr_result)
            
            if not text.strip():
                continue
                
            chunks = chunk_text(text)
            
            documents = chunks
            metadatas = [{"document_title": filename, "page": page_num + 1} for _ in chunks]
            ids = [f"{filename}_p{page_num+1}_c{i}" for i in range(len(chunks))]
            
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            total_chunks += len(chunks)
            
    print(f"\n Индексация завершена! Всего кусков в базе: {total_chunks}")

def retrieve_analytics(query: str, top_k: int = 3) -> list[dict]:
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    
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
    if collection.count() == 0:
        index_pdfs()
    
    print("\nТЕСТ ПОИСКА")
    test_query = "ключевая ставка инфляция"
    results = retrieve_analytics(test_query)
    
    for res in results:
        print(f"\n Файл: {res['document_title']} (Стр. {res['page']})")
        print(f" Текст: {res['text'][:300]}...")