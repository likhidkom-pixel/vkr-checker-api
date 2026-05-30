from fastapi import FastAPI, UploadFile, File
import fitz
import pdfplumber
import tempfile
import os

app = FastAPI()


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"health": "ok"}


@app.post("/analyze")
async def analyze_pdf(file: UploadFile = File(...)):

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        pdf_path = tmp.name

    result = {
        "title_page": None,
        "task_page": None,
        "review_page": None,
        "recension_page": None,
        "toc_page": None,
        "table_pages": [],
        "figure_pages": []
    }

    try:

        doc = fitz.open(pdf_path)

        pages = []

        for i in range(len(doc)):
            text = doc[i].get_text().upper()

            pages.append({
                "page": i + 1,
                "text": text
            })

        for page in pages[:10]:

            text = page["text"]
            num = page["page"]

            if (
                "МИНИСТЕРСТВО НАУКИ" in text
                and "МАГНИТОГОРСКИЙ" in text
                and "ВЫПУСКНАЯ КВАЛИФИКАЦИОННАЯ РАБОТА" in text
                and "ЗАДАНИЕ" not in text
                and result["title_page"] is None
            ):
                result["title_page"] = num

            if (
                "МИНИСТЕРСТВО НАУКИ" in text
                and "ВЫПУСКНАЯ КВАЛИФИКАЦИОННАЯ РАБОТА" in text
                and "ЗАДАНИЕ" in text
                and result["task_page"] is None
            ):
                result["task_page"] = num

            if "ОТЗЫВ" in text and result["review_page"] is None:
                result["review_page"] = num

            if "РЕЦЕНЗИЯ" in text and result["recension_page"] is None:
                result["recension_page"] = num

            if (
                ("СОДЕРЖАНИЕ" in text or "ОГЛАВЛЕНИЕ" in text)
                and result["toc_page"] is None
            ):
                result["toc_page"] = num

        with pdfplumber.open(pdf_path) as pdf:

            for page_num, page in enumerate(pdf.pages, start=1):

                try:
                    tables = page.find_tables()

                    if len(tables) > 0:
                        result["table_pages"].append(page_num)

                except:
                    pass

        for page_num in range(len(doc)):

            page = doc[page_num]

            images = page.get_images()

            if len(images) > 0:
                result["figure_pages"].append(page_num + 1)

        doc.close()

        return result

    finally:

        if os.path.exists(pdf_path):
            os.remove(pdf_path)
