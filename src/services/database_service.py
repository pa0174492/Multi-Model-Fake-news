"""
MongoDB Database Service for Veritas Multimodal Intelligence.
Provides persistent storage, live telemetry, real-time training sample streaming,
and instant fallback caching if the database is in local/offline mode.
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/veritas_db")
DEFAULT_DB_NAME = os.environ.get("MONGODB_DB_NAME", "veritas_db")

# Fallback in-memory seed records for immediate testing & demonstration
MOCK_PREDICTIONS_SEED = [
    {
        "_id": "rec_001",
        "headline": "NASA discovers traces of ancient micro-organisms in Martian subterranean riverbeds",
        "modality_type": "Multimodal (Text + Vision + Engagement)",
        "input_format": "Document (PDF)",
        "prediction": "Authentic News",
        "is_fake_binary": 0,
        "fake_probability": 0.082,
        "real_probability": 0.918,
        "confidence": 0.918,
        "upvote_ratio": 0.92,
        "post_score": 4200,
        "num_comments": 850,
        "source": "NASA Jet Propulsion Lab / Nature Astronomy",
        "timestamp": "2026-10-10 03:15:22",
        "has_image": True,
        "evidence_summary": "Peer-reviewed findings published in Nature Astronomy corroborating spectroscopic analysis from Perseverance Rover."
    },
    {
        "_id": "rec_002",
        "headline": "World Health Organization announces mandatory global chip implant by end of 2026",
        "modality_type": "Multimodal (Text + Vision)",
        "input_format": "Voice Speech Dictation",
        "prediction": "Fake News / Misinformation",
        "is_fake_binary": 1,
        "fake_probability": 0.965,
        "real_probability": 0.035,
        "confidence": 0.965,
        "upvote_ratio": 0.41,
        "post_score": 12,
        "num_comments": 4,
        "source": "Unverified Social Media Post",
        "timestamp": "2026-10-10 03:45:10",
        "has_image": True,
        "evidence_summary": "Fabricated conspiracy claim without administrative documentation or WHO director general briefing."
    },
    {
        "_id": "rec_003",
        "headline": "Global renewable energy capacity surges 50% year-over-year in milestone solar transition",
        "modality_type": "Multimodal (Text + Metadata)",
        "input_format": "Web Article URL Scraper",
        "prediction": "Authentic News",
        "is_fake_binary": 0,
        "fake_probability": 0.114,
        "real_probability": 0.886,
        "confidence": 0.886,
        "upvote_ratio": 0.89,
        "post_score": 1850,
        "num_comments": 310,
        "source": "International Energy Agency (IEA) Annual Report",
        "timestamp": "2026-10-10 04:02:44",
        "has_image": False,
        "evidence_summary": "Official statistics released by the IEA verified across European and North American power grid disclosures."
    },
    {
        "_id": "rec_004",
        "headline": "New diffusion model generates functional 3D biomolecular proteins in under 5 seconds",
        "modality_type": "Multimodal (Text + Vision + Metadata)",
        "input_format": "Raw Article Text",
        "prediction": "Authentic News",
        "is_fake_binary": 0,
        "fake_probability": 0.142,
        "real_probability": 0.858,
        "confidence": 0.858,
        "upvote_ratio": 0.94,
        "post_score": 3100,
        "num_comments": 420,
        "source": "DeepMind Biomolecular Research Group",
        "timestamp": "2026-10-10 04:18:00",
        "has_image": True,
        "evidence_summary": "Verified preprint code release on GitHub with open-source PyTorch weights."
    },
    {
        "_id": "rec_005",
        "headline": "BREAKING: Volcano erupts in central Paris creating 200ft magma lake near Eiffel Tower",
        "modality_type": "Multimodal (Text + AI Synthetic Image)",
        "input_format": "Raw Article Text",
        "prediction": "Fake News / Misinformation",
        "is_fake_binary": 1,
        "fake_probability": 0.988,
        "real_probability": 0.012,
        "confidence": 0.988,
        "upvote_ratio": 0.28,
        "post_score": 5,
        "num_comments": 1,
        "source": "Viral Twitter/X Hoax Channel",
        "timestamp": "2026-10-10 04:22:15",
        "has_image": True,
        "evidence_summary": "Image contains 98% synthetic diffusion artifacts (ELA noise plane anomaly). No seismic activity registered by USGS or French Geological Survey."
    }
]


class DatabaseService:
    """Manages persistent MongoDB collections and fallback local storage."""

    def __init__(self, uri: Optional[str] = None, db_name: Optional[str] = None):
        self.uri = uri or os.environ.get("MONGODB_URI", DEFAULT_MONGO_URI)
        self.db_name = db_name or os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
        self.client: Optional[MongoClient] = None
        self.db = None
        self.is_connected = False
        self._local_predictions = list(MOCK_PREDICTIONS_SEED)
        self._local_ai_scans: List[Dict[str, Any]] = []
        self._local_training_samples: List[Dict[str, Any]] = []
        self._init_connection()

    def _init_connection(self):
        """Attempts to establish connection with MongoDB."""
        if not self.uri:
            self.is_connected = False
            return

        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000)
            # Trigger server selection ping
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.is_connected = True
            logger.info(f"Connected to MongoDB successfully: {self.db_name}")
            self._ensure_indexes()
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            logger.info(f"MongoDB connection offline ({e}). Operating with local in-memory persistence.")
            self.is_connected = False
            self.client = None
            self.db = None

    def _ensure_indexes(self):
        """Creates indexes for fast searching and sorting."""
        if self.is_connected and self.db is not None:
            try:
                self.db.predictions.create_index([("timestamp", pymongo.DESCENDING)])
                self.db.predictions.create_index([("headline", pymongo.TEXT)])
                self.db.ai_scans.create_index([("timestamp", pymongo.DESCENDING)])
                self.db.realtime_samples.create_index([("timestamp", pymongo.DESCENDING)])
            except Exception as e:
                logger.warning(f"Index creation warning: {e}")

    def update_uri(self, new_uri: str, db_name: Optional[str] = None) -> Tuple[bool, str]:
        """Tests and saves a new MongoDB connection URI."""
        if not new_uri.strip():
            self.uri = ""
            self.is_connected = False
            self.client = None
            self.db = None
            return True, "Switched to local database mode."

        try:
            test_client = MongoClient(new_uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000)
            test_client.admin.command('ping')
            target_db = db_name or self.db_name
            
            # Close old connection
            if self.client:
                self.client.close()

            self.uri = new_uri
            self.db_name = target_db
            self.client = test_client
            self.db = self.client[self.db_name]
            self.is_connected = True
            self._ensure_indexes()

            # Persist in environment
            os.environ["MONGODB_URI"] = new_uri
            return True, f"Connected to MongoDB '{target_db}' successfully!"
        except Exception as e:
            return False, f"Failed to connect to MongoDB: {str(e)}"

    def get_status(self) -> Dict[str, Any]:
        """Returns connection health and telemetry counts."""
        if self.is_connected and self.db is not None:
            try:
                pred_count = self.db.predictions.count_documents({})
                ai_count = self.db.ai_scans.count_documents({})
                rt_count = self.db.realtime_samples.count_documents({})
                return {
                    "connected": True,
                    "mode": "MongoDB Cluster / Server",
                    "uri_masked": self._mask_uri(self.uri),
                    "database": self.db_name,
                    "collections": {
                        "predictions": pred_count,
                        "ai_scans": ai_count,
                        "realtime_samples": rt_count
                    },
                    "total_records": pred_count + ai_count + rt_count,
                    "status_message": "🟢 Live Database Connected"
                }
            except Exception as e:
                logger.warning(f"Status check failed: {e}")

        # Local mode telemetry
        return {
            "connected": False,
            "mode": "Local In-Memory Cache (MongoDB Offline)",
            "uri_masked": self._mask_uri(self.uri) if self.uri else "None",
            "database": self.db_name,
            "collections": {
                "predictions": len(self._local_predictions),
                "ai_scans": len(self._local_ai_scans),
                "realtime_samples": len(self._local_training_samples)
            },
            "total_records": len(self._local_predictions) + len(self._local_ai_scans) + len(self._local_training_samples),
            "status_message": "🟡 Local In-Memory Mode (Enter URI in Settings to connect MongoDB)"
        }

    def _mask_uri(self, uri: str) -> str:
        """Masks sensitive password tokens in URI string."""
        if "@" in uri:
            parts = uri.split("@")
            prefix = parts[0].split("://")[0]
            return f"{prefix}://*****:*****@{parts[1]}"
        return uri

    def save_prediction(self, record: Dict[str, Any]) -> str:
        """Saves a prediction dossier into database."""
        record_copy = dict(record)
        if "timestamp" not in record_copy:
            record_copy["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if self.is_connected and self.db is not None:
            try:
                res = self.db.predictions.insert_one(record_copy)
                return str(res.inserted_id)
            except Exception as e:
                logger.warning(f"Failed to write prediction to MongoDB: {e}")

        # Fallback local
        rec_id = f"loc_{int(time.time() * 1000)}"
        record_copy["_id"] = rec_id
        self._local_predictions.insert(0, record_copy)
        return rec_id

    def save_ai_scan(self, scan_data: Dict[str, Any]) -> str:
        """Saves an AI image forensic scan into database."""
        scan_copy = dict(scan_data)
        if "timestamp" not in scan_copy:
            scan_copy["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self.is_connected and self.db is not None:
            try:
                res = self.db.ai_scans.insert_one(scan_copy)
                return str(res.inserted_id)
            except Exception as e:
                logger.warning(f"Failed to write AI scan to MongoDB: {e}")

        rec_id = f"ai_{int(time.time() * 1000)}"
        scan_copy["_id"] = rec_id
        self._local_ai_scans.insert(0, scan_copy)
        return rec_id

    def save_realtime_sample(self, sample_data: Dict[str, Any]) -> str:
        """Ingests a real-time sample into the training collection."""
        sample_copy = dict(sample_data)
        if "timestamp" not in sample_copy:
            sample_copy["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self.is_connected and self.db is not None:
            try:
                res = self.db.realtime_samples.insert_one(sample_copy)
                return str(res.inserted_id)
            except Exception as e:
                logger.warning(f"Failed to write realtime sample to MongoDB: {e}")

        rec_id = f"rt_{int(time.time() * 1000)}"
        sample_copy["_id"] = rec_id
        self._local_training_samples.insert(0, sample_copy)
        return rec_id

    def get_records(
        self,
        collection_name: str = "predictions",
        query_text: Optional[str] = None,
        label_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Retrieves and paginates database records."""
        if self.is_connected and self.db is not None:
            try:
                coll = self.db[collection_name]
                filter_dict: Dict[str, Any] = {}
                
                if query_text:
                    filter_dict["$or"] = [
                        {"headline": {"$regex": query_text, "$options": "i"}},
                        {"source": {"$regex": query_text, "$options": "i"}},
                        {"input_format": {"$regex": query_text, "$options": "i"}}
                    ]
                
                if label_filter and label_filter != "all":
                    if label_filter == "fake":
                        filter_dict["is_fake_binary"] = 1
                    elif label_filter == "real":
                        filter_dict["is_fake_binary"] = 0
                    elif label_filter == "ai_generated":
                        filter_dict["is_ai"] = True
                    elif label_filter == "human_authentic":
                        filter_dict["is_ai"] = False

                total = coll.count_documents(filter_dict)
                cursor = coll.find(filter_dict).sort("timestamp", pymongo.DESCENDING).skip(offset).limit(limit)
                
                records = []
                for doc in cursor:
                    doc["_id"] = str(doc["_id"])
                    records.append(doc)

                return {
                    "status": "success",
                    "collection": collection_name,
                    "total": total,
                    "count": len(records),
                    "records": records,
                    "source": "mongodb"
                }
            except Exception as e:
                logger.warning(f"MongoDB query failed: {e}. Returning local.")

        # Local in-memory filtering
        target_list = []
        if collection_name == "predictions":
            target_list = self._local_predictions
        elif collection_name == "ai_scans":
            target_list = self._local_ai_scans
        elif collection_name == "realtime_samples":
            target_list = self._local_training_samples

        filtered = []
        for r in target_list:
            text_match = True
            if query_text:
                q_low = query_text.lower()
                text_match = (
                    q_low in str(r.get("headline", "")).lower() or
                    q_low in str(r.get("source", "")).lower() or
                    q_low in str(r.get("input_format", "")).lower()
                )
            
            label_match = True
            if label_filter and label_filter != "all":
                if label_filter == "fake" and r.get("is_fake_binary") != 1:
                    label_match = False
                elif label_filter == "real" and r.get("is_fake_binary") != 0:
                    label_match = False
                elif label_filter == "ai_generated" and not r.get("is_ai"):
                    label_match = False
                elif label_filter == "human_authentic" and r.get("is_ai"):
                    label_match = False

            if text_match and label_match:
                filtered.append(r)

        sliced = filtered[offset: offset + limit]
        return {
            "status": "success",
            "collection": collection_name,
            "total": len(filtered),
            "count": len(sliced),
            "records": sliced,
            "source": "local_cache"
        }

    def delete_record(self, collection_name: str, record_id: str) -> bool:
        """Deletes a record from the database or local storage."""
        if self.is_connected and self.db is not None:
            try:
                from bson.objectid import ObjectId
                try:
                    obj_id = ObjectId(record_id)
                    res = self.db[collection_name].delete_one({"_id": obj_id})
                    if res.deleted_count > 0:
                        return True
                except Exception:
                    pass
                res = self.db[collection_name].delete_one({"_id": record_id})
                return res.deleted_count > 0
            except Exception as e:
                logger.warning(f"Delete failed on MongoDB: {e}")

        # Local delete
        target_list = []
        if collection_name == "predictions":
            target_list = self._local_predictions
        elif collection_name == "ai_scans":
            target_list = self._local_ai_scans
        elif collection_name == "realtime_samples":
            target_list = self._local_training_samples

        for i, item in enumerate(target_list):
            if str(item.get("_id")) == str(record_id):
                target_list.pop(i)
                return True
        return False


# Singleton instance
db_service = DatabaseService()
