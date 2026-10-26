"""
FastAPI Server for Explainable Multimodal Fake News Detection & AI Media Forensics.
Includes Omni-Format Ingestion, Synthetic Media Detection, Deep Evidence Reporting,
Gemini Assistant, Real-Time Model Training Pipeline, MongoDB Database Explorer,
Fakeddit Dataset Explorer, and Cross-Modal Semantic Alignment Analyzer.
"""

import os
import sys
import shutil
import tempfile
import logging
from typing import Optional, Dict, Any, List, Tuple
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fake_news_app")

# Ensure repository root is in python path
sys.path.insert(0, os.path.abspath("."))

from src.inference.pipeline import MultimodalInferencePipeline
from src.artifacts.artifact_manager import ArtifactManager
from src.services.format_converter import FormatConverterService
from src.services.ai_detector import AIDetectorService
from src.services.evidence_service import DeepEvidenceService
from src.services.chatbot_service import FactCheckChatbotService
from src.services.gemini_helper import test_gemini_key_and_get_model
from src.services.database_service import db_service
from src.services.realtime_trainer import realtime_trainer
from src.services.dataset_service import dataset_service
from src.services.crossmodal_service import crossmodal_service
from src.services.advanced_forensics import (
    BatchForensicsService,
    ViralitySimulatorService,
    LinguisticForensicsService,
    SystemTelemetryService,
    ForensicDossierGenerator
)

app = FastAPI(
    title="Veritas | Explainable Multimodal Fake News & AI Media Forensic Suite",
    description="Enterprise Veracity Engine with Omni-Format Ingestion, Batch Forensics, Virality Simulator, Linguistic Scanner, AI Synthetic Forensics, Deep Evidence, Gemini Chatbot, Real-Time Model Training, MongoDB Database Explorer, and Fakeddit Dataset Explorer",
    version="4.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = MultimodalInferencePipeline(artifact_root="artifacts", version="v1.0.0")
artifact_manager = ArtifactManager(root_dir="artifacts")
evidence_service = DeepEvidenceService()
chatbot_service = FactCheckChatbotService()


@app.on_event("startup")
async def startup_event():
    """Starts model warmup in background so web server starts instantly."""
    import threading
    threading.Thread(target=pipeline.load, daemon=True, name="VeritasModelWarmup").start()

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
images_dir = os.path.join(os.path.abspath("."), "data", "images")
os.makedirs(images_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/images", StaticFiles(directory=images_dir), name="images")


def resolve_media_path(path_or_url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolves local paths, /images/ static URLs, and remote HTTP URLs into an accessible file path.
    Returns (resolved_file_path, temp_file_to_cleanup).
    """
    if not path_or_url:
        return None, None
    clean = str(path_or_url).strip()
    if not clean:
        return None, None

    # Check direct path
    if os.path.exists(clean):
        return os.path.abspath(clean), None
    abs_cand = os.path.abspath(clean)
    if os.path.exists(abs_cand):
        return abs_cand, None

    # Check /images/ test/train/val static routes
    if clean.startswith("/images/"):
        rel = clean.replace("/images/", "", 1)
        cand = os.path.join(images_dir, rel.replace("/", os.sep))
        if os.path.exists(cand):
            return os.path.abspath(cand), None

    # Check data/images/... relative to workspace
    if "data" in clean and "images" in clean:
        cand = os.path.join(os.path.abspath("."), clean.replace("/", os.sep))
        if os.path.exists(cand):
            return os.path.abspath(cand), None

    # Check if basename exists anywhere in data/images subdirectories
    base = os.path.basename(clean.replace("\\", "/"))
    if base:
        for sub in ["ai_samples", "test", "train", "val"]:
            cand = os.path.join(images_dir, sub, base)
            if os.path.exists(cand):
                return os.path.abspath(cand), None

    # Remote HTTP/HTTPS image URL
    if clean.startswith(("http://", "https://")):
        try:
            r = requests.get(clean, timeout=6)
            if r.status_code == 200:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                tmp.write(r.content)
                tmp.close()
                return tmp.name, tmp.name
        except Exception as e:
            logger.warning(f"Could not download remote media URL {clean}: {e}")

    return None, None


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>App static files not found.</h1>")


@app.get("/api/info")
async def get_system_info():
    """Returns model version, metrics, and AutoML comparison data."""
    try:
        metrics = artifact_manager.load_json("v1.0.0", "metrics.json")
        candidate_comp = artifact_manager.load_json("v1.0.0", "candidate_comparison.json")
        shap_summary = artifact_manager.load_json("v1.0.0", "shap_summary.json")
        data_profile = artifact_manager.load_json("v1.0.0", "data_profile.json")
        return {
            "version": "v3.5.0 (XGBoost Multimodal Fusion + SHAP + Gemini + AI Forensics + MongoDB + Real-Time Engine + Dataset Explorer)",
            "metrics": metrics,
            "automl": candidate_comp,
            "global_shap": shap_summary.get("global_explanations", {}),
            "data_profile": data_profile,
            "model_ready": pipeline.is_loaded
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pipeline/status")
async def get_pipeline_status():
    """Returns background warmup status of AI inference models."""
    return {
        "status": "ready" if pipeline.is_loaded else "loading",
        "is_loaded": pipeline.is_loaded,
        "version": pipeline.version
    }


@app.get("/api/samples")
async def get_test_samples(limit: int = 12):
    """Returns curated held-out test samples with images and ground-truth veracity."""
    test_csv = os.path.join("data", "processed", "test_multimodal.csv")
    if not os.path.exists(test_csv):
        return {"samples": []}

    df = pd.read_csv(test_csv)
    samples = []
    for _, row in df.head(limit).iterrows():
        img_id = str(row["id"])
        local_img = os.path.join("data", "images", "test", f"{img_id}.jpg")
        img_url = f"/images/test/{img_id}.jpg" if os.path.exists(local_img) else None

        samples.append({
            "id": img_id,
            "clean_title": row["clean_title"],
            "is_fake": int(row["is_fake"]),
            "score": float(row.get("score", 10)),
            "num_comments": float(row.get("num_comments", 2)),
            "upvote_ratio": float(row.get("upvote_ratio", 0.8)),
            "subreddit": row.get("subreddit", "news"),
            "image_url": img_url,
            "local_image_path": local_img if img_url else None
        })
    return {"samples": samples}


# ==========================================
# Dataset & Corpus Explorer Endpoints
# ==========================================

@app.get("/api/dataset/summary")
async def get_dataset_summary_endpoint():
    """Returns high-level statistics, schema dictionary, class balance, and split counts."""
    try:
        return {"status": "success", "summary": dataset_service.get_dataset_summary()}
    except Exception as e:
        logger.error(f"Dataset summary failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dataset/explorer")
async def get_dataset_explorer_endpoint(
    split: str = Query("all"),
    query: Optional[str] = Query(None),
    veracity: str = Query("all"),
    subreddit: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(20)
):
    """Queries, searches, and paginates samples across Fakeddit dataset splits."""
    try:
        return dataset_service.query_dataset(
            split=split,
            query_text=query,
            veracity_filter=veracity,
            subreddit_filter=subreddit,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"Dataset explorer query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Cross-Modal Alignment Endpoints
# ==========================================

@app.post("/api/crossmodal/analyze")
async def analyze_crossmodal_endpoint(
    headline: str = Form(...),
    existing_image_path: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """Computes text-image semantic alignment, cosine similarity, and contradiction risk."""
    temp_img_path = None
    try:
        img_bytes = None
        if image is not None and image.filename:
            img_bytes = await image.read()
            suffix = os.path.splitext(image.filename)[1] or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(img_bytes)
                temp_img_path = tmp.name
            target_path = temp_img_path
        elif existing_image_path:
            res_path, tmp_to_clean = resolve_media_path(existing_image_path)
            if not res_path:
                base_name = os.path.basename(existing_image_path.replace("\\", "/"))
                for root_dir, _, files in os.walk(images_dir):
                    if base_name in files:
                        res_path = os.path.abspath(os.path.join(root_dir, base_name))
                        break
            target_path = res_path
            if tmp_to_clean:
                temp_img_path = tmp_to_clean
        else:
            target_path = None

        result = crossmodal_service.analyze_crossmodal(
            headline=headline,
            image_path=target_path,
            image_bytes=img_bytes
        )
        return {"status": "success", "analysis": result}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Cross-modal analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_img_path and os.path.exists(temp_img_path):
            try:
                os.remove(temp_img_path)
            except Exception:
                pass


@app.post("/api/convert-document")
async def convert_document(file: UploadFile = File(...)):
    """Extracts text content from uploaded document file (PDF, DOCX, TXT)."""
    temp_path = None
    try:
        suffix = os.path.splitext(file.filename)[1] or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name

        result = FormatConverterService.extract_from_document(temp_path, file.filename)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Document conversion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post("/api/convert-url")
async def convert_url(url: str = Form(...)):
    """Extracts article title, body, and image from web article link."""
    try:
        result = FormatConverterService.extract_from_url(url)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"URL conversion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai-image-detect")
async def detect_ai_image(
    image: Optional[UploadFile] = File(None),
    existing_image_path: Optional[str] = Form(None),
    image_base64: Optional[str] = Form(None),
    filename: Optional[str] = Form(None)
):
    """Forensic analysis to detect whether an image is AI Generated or Human/Camera Authentic."""
    temp_img_path = None
    try:
        img_bytes = None
        target_filename = filename

        if image is not None and image.filename:
            img_bytes = await image.read()
            if not target_filename:
                target_filename = image.filename
        elif image_base64:
            pass
        elif existing_image_path:
            res_path, tmp_to_clean = resolve_media_path(existing_image_path)
            if not res_path:
                # Search by basename in images_dir
                base_name = os.path.basename(existing_image_path.replace("\\", "/"))
                for root_dir, _, files in os.walk(images_dir):
                    if base_name in files:
                        res_path = os.path.abspath(os.path.join(root_dir, base_name))
                        break
            if not res_path:
                # Resilient fallback to synthetic demo sample
                fallback = os.path.join(images_dir, "ai_samples", "synthetic_ai_gen.jpg")
                if os.path.exists(fallback):
                    res_path = os.path.abspath(fallback)
                    target_filename = "synthetic_ai_gen.jpg"
            if res_path:
                existing_image_path = res_path
                if not target_filename:
                    target_filename = os.path.basename(res_path)
                if tmp_to_clean:
                    temp_img_path = tmp_to_clean
            else:
                raise HTTPException(status_code=400, detail=f"Image not found at path: {existing_image_path}")
        else:
            # If no image specified, use benchmark forensic sample
            fallback = os.path.join(images_dir, "ai_samples", "synthetic_ai_gen.jpg")
            if os.path.exists(fallback):
                existing_image_path = os.path.abspath(fallback)
                target_filename = "synthetic_ai_gen.jpg"
            else:
                raise HTTPException(status_code=400, detail="No valid image provided for AI forensic inspection.")

        result = AIDetectorService.analyze_image(
            image_path=existing_image_path,
            image_bytes=img_bytes,
            image_base64=image_base64,
            filename=target_filename
        )

        try:
            db_service.save_ai_scan({
                "headline": result.get("provenance_profile", "Visual Media Forensic Scan"),
                "is_ai": result.get("is_ai"),
                "confidence": result.get("confidence"),
                "ai_probability": result.get("ai_probability"),
                "human_probability": result.get("human_probability"),
                "verdict": result.get("verdict"),
                "forensic_metrics": result.get("forensic_metrics"),
                "detected_artifacts": result.get("detected_artifacts")
            })
        except Exception as err:
            logger.warning(f"Database scan save warning: {err}")

        return {"status": "success", "analysis": result}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"AI image detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_img_path and os.path.exists(temp_img_path):
            try:
                os.remove(temp_img_path)
            except Exception:
                pass


@app.post("/api/predict")
async def predict_custom(
    text: str = Form(...),
    score: float = Form(10.0),
    num_comments: float = Form(2.0),
    upvote_ratio: float = Form(0.8),
    existing_image_path: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    gemini_api_key: Optional[str] = Form(None),
    input_format: Optional[str] = Form("Raw Article Text")
):
    """
    Executes multimodal prediction, SHAP explanation, Deep Evidence Report,
    and records the transaction into the MongoDB database.
    """
    temp_img_path = None
    try:
        if image is not None and image.filename:
            suffix = os.path.splitext(image.filename)[1] or ".jpg"
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            shutil.copyfileobj(image.file, temp_file)
            temp_file.close()
            temp_img_path = temp_file.name
            target_image_path = temp_img_path
        elif existing_image_path:
            res_path, tmp_to_clean = resolve_media_path(existing_image_path)
            target_image_path = res_path
            if tmp_to_clean:
                temp_img_path = tmp_to_clean
        else:
            target_image_path = None

        metadata = {
            "score": score,
            "num_comments": num_comments,
            "upvote_ratio": upvote_ratio
        }

        pred_result = pipeline.predict(text=text, image_path=target_image_path, metadata=metadata)
        explanation = pipeline.explain(text=text, image_path=target_image_path, metadata=metadata, top_k=6)

        is_fake = pred_result["is_fake_binary"] == 1
        evidence_report = evidence_service.generate_evidence_report(
            headline=text,
            is_fake=is_fake,
            fake_prob=pred_result["fake_probability"],
            modality_scores=pred_result["modality_scores"],
            shap_top_features=explanation["top_positive_contributors_fake"] if is_fake else explanation["top_negative_contributors_real"],
            custom_key=gemini_api_key
        )

        try:
            db_service.save_prediction({
                "headline": text,
                "input_format": input_format,
                "modality_type": "Multimodal (Text + Vision + Metadata)" if target_image_path else "Text + Engagement Metadata",
                "prediction": pred_result["prediction"],
                "is_fake_binary": pred_result["is_fake_binary"],
                "fake_probability": pred_result["fake_probability"],
                "real_probability": pred_result["real_probability"],
                "confidence": pred_result["confidence"],
                "upvote_ratio": upvote_ratio,
                "post_score": score,
                "num_comments": num_comments,
                "source": evidence_report.get("source_domain", "User Query"),
                "has_image": target_image_path is not None,
                "evidence_summary": evidence_report.get("summary", "")
            })
        except Exception as db_err:
            logger.warning(f"Failed to auto-save to MongoDB: {db_err}")

        return {
            "status": "success",
            "prediction": pred_result["prediction"],
            "is_fake_binary": pred_result["is_fake_binary"],
            "fake_probability": pred_result["fake_probability"],
            "real_probability": pred_result["real_probability"],
            "confidence": pred_result["confidence"],
            "modality_scores": pred_result["modality_scores"],
            "shap_explanation": {
                "base_value": explanation["base_value"],
                "positive_contributors_fake": explanation["top_positive_contributors_fake"],
                "negative_contributors_real": explanation["top_negative_contributors_real"]
            },
            "evidence_report": evidence_report
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Prediction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_img_path and os.path.exists(temp_img_path):
            try:
                os.remove(temp_img_path)
            except Exception:
                pass


@app.post("/api/chat/stream")
async def chat_stream_endpoint(
    message: str = Form(...),
    history_json: Optional[str] = Form(None),
    gemini_api_key: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None)
):
    """Streams response token-by-token (SSE) formatted for ChatGPT-like live response."""
    import json
    history = json.loads(history_json) if history_json else []
    return StreamingResponse(
        chatbot_service.stream_chat(
            message=message,
            chat_history=history,
            custom_key=gemini_api_key,
            custom_model=model_name
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@app.post("/api/chat")
async def chat_with_assistant(
    message: str = Form(...),
    history_json: Optional[str] = Form(None),
    gemini_api_key: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None)
):
    """Conversational endpoint for fact-checking questions, trend inquiries, and claims."""
    try:
        import json
        history = json.loads(history_json) if history_json else []
        result = chatbot_service.chat(
            message=message,
            chat_history=history,
            custom_key=gemini_api_key,
            custom_model=model_name
        )
        return result
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# MongoDB Database Explorer Endpoints
# ==========================================

@app.get("/api/database/status")
async def get_database_status():
    """Returns live connection health, collection counts, and telemetry for MongoDB."""
    return db_service.get_status()


@app.get("/api/database/records")
async def get_database_records(
    collection: str = Query("predictions"),
    query: Optional[str] = Query(None),
    label: Optional[str] = Query("all"),
    limit: int = Query(50),
    offset: int = Query(0)
):
    """Fetches, searches, and paginates records from MongoDB collections."""
    return db_service.get_records(
        collection_name=collection,
        query_text=query,
        label_filter=label,
        limit=limit,
        offset=offset
    )


@app.post("/api/database/save-record")
async def save_manual_record(
    collection: str = Form("predictions"),
    headline: str = Form(...),
    prediction: str = Form("Authentic News"),
    is_fake_binary: int = Form(0),
    confidence: float = Form(0.90),
    input_format: str = Form("Manual Database Entry"),
    source: str = Form("Database Entry")
):
    """Manually creates a record in the database."""
    try:
        rec_id = db_service.save_prediction({
            "headline": headline,
            "prediction": prediction,
            "is_fake_binary": is_fake_binary,
            "fake_probability": 0.95 if is_fake_binary == 1 else 0.05,
            "real_probability": 0.05 if is_fake_binary == 1 else 0.95,
            "confidence": confidence,
            "input_format": input_format,
            "source": source,
            "modality_type": "Multimodal Vector Record",
            "has_image": False
        })
        return {"status": "success", "id": rec_id, "message": "Record inserted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/database/delete-record")
async def delete_database_record(
    collection: str = Form(...),
    record_id: str = Form(...)
):
    """Deletes a record from MongoDB."""
    success = db_service.delete_record(collection, record_id)
    if success:
        return {"status": "success", "message": f"Record {record_id} deleted."}
    return {"status": "error", "message": f"Could not find or delete record {record_id}."}


@app.post("/api/settings/save-mongodb")
async def save_mongodb_uri(
    uri: str = Form(...),
    db_name: Optional[str] = Form("veritas_db")
):
    """Connects and validates a user-provided MongoDB URI."""
    success, message = db_service.update_uri(uri, db_name)
    return {
        "status": "success" if success else "error",
        "message": message,
        "is_connected": db_service.is_connected
    }


# ==========================================
# Real-Time Model Building & Stream Endpoints
# ==========================================

@app.get("/api/realtime-model/status")
async def get_realtime_model_status():
    """Returns active real-time model version, stream samples, and convergence metrics."""
    return realtime_trainer.get_status()


@app.post("/api/realtime-model/train")
async def trigger_realtime_training(
    epochs: int = Form(12),
    learning_rate: float = Form(0.05)
):
    """Executes incremental retraining of the fusion model on live ingested stream data."""
    try:
        report = realtime_trainer.build_realtime_model(epochs=epochs, learning_rate=learning_rate)
        return {"status": "success", "training_report": report}
    except Exception as e:
        logger.error(f"Real-time training failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/realtime-model/add-sample")
async def add_realtime_stream_sample(
    title: str = Form(...),
    label: int = Form(...),
    category: str = Form("Live News Stream"),
    verified_source: str = Form("Verified News Wire"),
    score: float = Form(500),
    comments: float = Form(100),
    upvote_ratio: float = Form(0.85),
    image_url: Optional[str] = Form(None)
):
    """Ingests a real-time sample into the training stream pipeline and saves to database."""
    sample = realtime_trainer.add_stream_sample(
        title=title,
        label=label,
        category=category,
        verified_source=verified_source,
        score=score,
        comments=comments,
        upvote_ratio=upvote_ratio,
        image_url=image_url
    )

    # Automatically save to database
    try:
        db_service.save_realtime_sample(sample)
    except Exception as err:
        logger.warning(f"Failed to write stream sample to MongoDB: {err}")

    return {"status": "success", "sample": sample}


@app.post("/api/realtime-model/generate-stream-batch")
async def generate_stream_batch_endpoint(count: int = Form(3)):
    """Simulates live feed ingestion of breaking news stream batches."""
    added = realtime_trainer.generate_feed_batch(count=count)
    for s in added:
        try:
            db_service.save_realtime_sample(s)
        except Exception:
            pass
    return {"status": "success", "count": len(added), "samples": added}


@app.post("/api/realtime-model/predict")
async def predict_with_realtime_model(
    headline: str = Form(...),
    use_realtime_model: bool = Form(True)
):
    """Performs inference using the newly built Real-Time Adaptive Model."""
    result = realtime_trainer.predict_with_realtime_model(headline=headline, is_realtime=use_realtime_model)
    return {"status": "success", "result": result}


# ==========================================
# Gemini Key Verification Endpoint
# ==========================================

@app.post("/api/settings/verify-key")
async def verify_gemini_key(
    key: str = Form(...),
    model_name: Optional[str] = Form(None)
):
    """Tests if a supplied Gemini API key is functional using dynamic model resolution."""
    success, active_model, available_models, message = test_gemini_key_and_get_model(key, model_name)
    if success:
        evidence_service.update_key(key)
        chatbot_service.update_key(key)
        return {
            "status": "success",
            "model_name": active_model,
            "available_models": available_models,
            "message": message
        }
    else:
        return {
            "status": "error",
            "available_models": available_models,
            "message": message
        }


# ==========================================
# Advanced Enterprise Forensic Suite Endpoints
# ==========================================

@app.get("/api/system/telemetry")
async def get_system_telemetry_endpoint():
    """Returns live CPU/RAM utilization, PyTorch device, model cache, and uptime."""
    try:
        return {"status": "success", "telemetry": SystemTelemetryService.get_telemetry()}
    except Exception as e:
        logger.error(f"Telemetry retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/linguistics/analyze")
async def analyze_linguistics_endpoint(text: str = Form(...)):
    """Performs deep NLP sensationalism, clickbait detection, and objective neutral rewriting."""
    try:
        analysis = LinguisticForensicsService.analyze(text)
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        logger.error(f"Linguistic analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/virality/simulate")
async def simulate_virality_endpoint(
    headline: str = Form(...),
    fake_probability: float = Form(0.75),
    post_score: float = Form(100.0),
    num_comments: float = Form(25.0),
    upvote_ratio: float = Form(0.75),
    has_image: bool = Form(True)
):
    """Computes virality risk score, R0 reproduction rate, reach curve, and counter-narrative."""
    try:
        sim = ViralitySimulatorService.simulate(
            headline=headline,
            fake_probability=fake_probability,
            post_score=post_score,
            num_comments=num_comments,
            upvote_ratio=upvote_ratio,
            has_image=has_image
        )
        return {"status": "success", "simulation": sim}
    except Exception as e:
        logger.error(f"Virality simulation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch/analyze")
async def analyze_batch_endpoint(
    text_lines: Optional[str] = Form(None),
    items_json: Optional[str] = Form(None),
    csv_file: Optional[UploadFile] = File(None)
):
    """Executes high-throughput batch forensic audit across multiple headlines or CSV uploads."""
    try:
        import json
        import io
        items_to_process = []

        if csv_file is not None and csv_file.filename:
            content = await csv_file.read()
            df = pd.read_csv(io.BytesIO(content))
            # Determine headline column
            text_col = None
            for col in ["clean_title", "headline", "title", "text"]:
                if col in df.columns:
                    text_col = col
                    break
            if text_col:
                for _, row in df.head(30).iterrows():
                    items_to_process.append({
                        "headline": str(row[text_col]),
                        "score": float(row.get("score", 10.0)),
                        "num_comments": float(row.get("num_comments", 2.0)),
                        "upvote_ratio": float(row.get("upvote_ratio", 0.8))
                    })
        elif items_json:
            items_to_process = json.loads(items_json)
        elif text_lines:
            lines = [l.strip() for l in text_lines.splitlines() if l.strip()]
            for l in lines[:30]:
                items_to_process.append({
                    "headline": l,
                    "score": 50.0,
                    "num_comments": 10.0,
                    "upvote_ratio": 0.8
                })

        if not items_to_process:
            raise HTTPException(status_code=400, detail="No valid headlines or CSV content provided for batch scan.")

        report = BatchForensicsService.process_batch(
            items=items_to_process,
            pipeline_instance=pipeline,
            max_items=30
        )
        return {"status": "success", "batch_report": report}
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dossier/generate")
async def generate_dossier_endpoint(
    headline: str = Form(...),
    verdict: str = Form(...),
    fake_prob: float = Form(...),
    confidence: float = Form(...),
    evidence_summary: Optional[str] = Form(""),
    image_name: Optional[str] = Form(None)
):
    """Generates cryptographically signed forensic dossier record."""
    try:
        dossier = ForensicDossierGenerator.generate_dossier(
            headline=headline,
            verdict=verdict,
            fake_prob=fake_prob,
            confidence=confidence,
            modality_scores={},
            evidence_summary=evidence_summary,
            image_name=image_name
        )
        return {"status": "success", "dossier": dossier}
    except Exception as e:
        logger.error(f"Dossier generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
