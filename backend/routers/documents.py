"""Document upload and management endpoints."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from datetime import datetime, timezone
import io
import os
import uuid
from shared import db, uploads_col, logger

router = APIRouter()


@router.get("/uploaded-documents")
async def get_uploaded_documents():
    docs = await uploads_col.find({}, {"_id": 0}).sort("uploaded_at", -1).to_list(100)
    return {"documents": docs, "count": len(docs)}


@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    allowed_types = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-excel": "xls",
        "text/plain": "txt"
    }

    content_type = file.content_type
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not supported. Allowed: PDF, Word, Excel, TXT")

    file_type = allowed_types[content_type]
    file_content = await file.read()

    extracted_text = ""
    try:
        if file_type == "pdf":
            from PyPDF2 import PdfReader
            pdf_reader = PdfReader(io.BytesIO(file_content))
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() or ""
        elif file_type in ["docx", "doc"]:
            from docx import Document
            doc = Document(io.BytesIO(file_content))
            extracted_text = "\n".join([para.text for para in doc.paragraphs])
        elif file_type in ["xlsx", "xls"]:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(file_content))
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    extracted_text += " | ".join([str(cell) for cell in row if cell]) + "\n"
        elif file_type == "txt":
            extracted_text = file_content.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error extracting text from {file.filename}: {e}")
        extracted_text = f"Error extracting text: {str(e)}"

    doc_record = {
        "id": str(uuid.uuid4()),
        "filename": file.filename,
        "file_type": file_type,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "content_summary": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
        "extracted_text": extracted_text[:10000],
        "ai_analysis": "",
        "region": "",
        "processed": False
    }

    await uploads_col.insert_one(doc_record)

    if background_tasks:
        background_tasks.add_task(analyze_uploaded_document, doc_record["id"])

    return {
        "message": "Document uploaded successfully",
        "document_id": doc_record["id"],
        "filename": file.filename,
        "extracted_chars": len(extracted_text)
    }


@router.delete("/uploaded-documents/{doc_id}")
async def delete_uploaded_document(doc_id: str):
    result = await uploads_col.delete_one({"id": doc_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


async def analyze_uploaded_document(doc_id: str):
    """Analyze an uploaded document using AI."""
    doc = await uploads_col.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        logger.error(f"Document {doc_id} not found")
        return

    extracted_text = doc.get("extracted_text", "")
    if not extracted_text:
        logger.warning(f"No text extracted from document {doc_id}")
        return

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json

        EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

        analysis_prompt = """You are a military intelligence analyst. Analyze this document and provide:
1. A concise summary (3-4 lines)
2. Key intelligence points relevant to India's North Eastern Region, Bangladesh, or Myanmar
3. Any security implications
4. Recommended attention level (Immediate Action Required, Priority Monitoring, Active Monitoring, Monitor)
5. Primary region affected (if identifiable): Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Bangladesh, Myanmar, or National/International

Respond in JSON format:
{
  "summary": "...",
  "key_points": ["...", "..."],
  "security_implications": "...",
  "attention_level": "...",
  "region": "..."
}"""

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"doc-{doc_id}",
            system_message=analysis_prompt
        ).with_model("anthropic", "claude-haiku-4-5-20251001")

        user_message = UserMessage(text=f"Analyze this document:\n\n{extracted_text[:4000]}")
        response = await chat.send_message(user_message)

        response_text = str(response)

        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            analysis = json.loads(response_text[json_start:json_end])
        else:
            analysis = {"summary": response_text[:500], "region": ""}

        await uploads_col.update_one(
            {"id": doc_id},
            {"$set": {
                "ai_analysis": analysis.get("summary", "") + "\n\nKey Points:\n" + "\n".join(analysis.get("key_points", [])),
                "region": analysis.get("region", ""),
                "processed": True
            }}
        )

        logger.info(f"Successfully analyzed document {doc_id}")

    except Exception as e:
        logger.error(f"Error analyzing document {doc_id}: {e}")
        await uploads_col.update_one(
            {"id": doc_id},
            {"$set": {"ai_analysis": f"Analysis failed: {str(e)}", "processed": True}}
        )
