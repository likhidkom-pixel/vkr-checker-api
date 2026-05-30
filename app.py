from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import fitz
import pdfplumber
import tempfile
import os

app = FastAPI()


def analyze_document(pdf_path):

    result = {
        "title_page": None,
        "task_page": None,
        "review_page": None,
        "recension_page": None,
        "toc_page": None,
        "table_pages": [],
        "figure_pages": []
    }

    doc = fitz.open(pdf_path)

    pages = []

    for i in range(len(doc)):
        text = doc[i].get_text().upper()

        pages.append({
            "page": i + 1,
            "text": text
        })

    # Поиск титула, задания, отзыва, рецензии и содержания
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

    # Поиск таблиц
    with pdfplumber.open(pdf_path) as pdf:

        for page_num, page in enumerate(pdf.pages, start=1):

            try:
                tables = page.find_tables()

                if len(tables) > 0:
                    result["table_pages"].append(page_num)

            except:
                pass

    # Поиск рисунков
    for page_num in range(len(doc)):

        page = doc[page_num]

        images = page.get_images()

        if len(images) > 0:
            result["figure_pages"].append(page_num + 1)

    doc.close()

    return result


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

    try:

        result = analyze_document(pdf_path)

        return result

    finally:

        if os.path.exists(pdf_path):
            os.remove(pdf_path)


@app.post("/extract-pages")
async def extract_pages(file: UploadFile = File(...)):

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        pdf_path = tmp.name

    output_pdf = pdf_path.replace(".pdf", "_filtered.pdf")

    try:

        analysis = analyze_document(pdf_path)

        pages_to_keep = []

        for key in [
            "title_page",
            "task_page",
            "review_page",
            "recension_page",
            "toc_page"
        ]:
            if analysis[key]:
                pages_to_keep.append(analysis[key])

        pages_to_keep.extend(analysis["table_pages"][:10])
        pages_to_keep.extend(analysis["figure_pages"][:10])

        pages_to_keep = sorted(list(set(pages_to_keep)))

        source_doc = fitz.open(pdf_path)

        result_doc = fitz.open()

        for page_num in pages_to_keep:

            result_doc.insert_pdf(
                source_doc,
                from_page=page_num - 1,
                to_page=page_num - 1
            )

        result_doc.save(output_pdf)

        result_doc.close()
        source_doc.close()

        return FileResponse(
            output_pdf,
            media_type="application/pdf",
            filename="filtered_vkr.pdf"
        )

    finally:

        if os.path.exists(pdf_path):
            os.remove(pdf_path)
