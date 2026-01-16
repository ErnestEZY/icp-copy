from typing import Tuple
from docx import Document
from pdfminer.high_level import extract_text
import os

def is_pdf(filename: str) -> bool:
    return filename.lower().endswith(".pdf")

def is_docx(filename: str) -> bool:
    return filename.lower().endswith(".docx") or filename.lower().endswith(".doc")

def extract_resume_text(path: str) -> Tuple[str, str]:
    name = os.path.basename(path)
    if is_pdf(name):
        text = extract_text(path)
        return text.strip(), "application/pdf"
    if name.lower().endswith(".doc"):
        raise ValueError("Please convert .doc to .docx or pdf")
    doc = Document(path)
    text = "\n".join([p.text for p in doc.paragraphs])
    return text.strip(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
