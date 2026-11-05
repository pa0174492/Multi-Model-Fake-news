"""
Enterprise Authentication, Role-Based Access Control (RBAC) & Secure Email OTP Service.
Supports two primary clearance levels:
  - 'admin': Full access to Datasets & Streams (Fakeddit Dataset Explorer, Real-Time Model Builder,
             MongoDB Data Explorer), System Settings, and Identity & Access Control (Promote/Demote users).
  - 'user':  Standard access to Veracity Detector, AI Media Forensics, Batch Audit, Virality Simulator,
             Linguistic Scanner, Cross-Modal Alignment, and AI Chatbot.
"""

import os
import json
import time
import hmac
import base64
import hashlib
import secrets
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

from src.services.database_service import db_service
from src.services.email_service import email_service

load_dotenv()
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("VERITAS_JWT_SECRET", "veritas_forensic_hmac_secret_key_2026_iso27037")
AUTH_STORE_PATH = os.path.join("artifacts", "auth_store.json")


class AuthService:
    """Manages users with MongoDB primary persistence, PBKDF2 password hashing, JWT tokens, and secure OTP verification."""

    def __init__(self):
        self.smtp_config: Dict[str, Any] = {}
        self._refresh_smtp_from_env()
        self._users: List[Dict[str, Any]] = []
        self._otp_records: Dict[str, Dict[str, Any]] = {}
        self._audit_logs: List[Dict[str, Any]] = []
        self._outbox_messages: List[Dict[str, Any]] = []
        self._load_or_seed_store()

    def _refresh_smtp_from_env(self):
        """Reloads SMTP settings from .env so changes take effect immediately."""
        load_dotenv(override=True)
        raw_pass = os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS") or ""
        host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
        port = int(os.environ.get("SMTP_PORT", "465") or 465)
        secure_str = os.environ.get("SMTP_SECURE", "true").strip().lower()
        secure = (secure_str in ("true", "1", "yes")) or (port == 465)
        user = os.environ.get("SMTP_USER", "").strip()
        clean_pass = raw_pass.replace(" ", "").strip() if "gmail" in host.lower() else raw_pass.strip()
        from_hdr = os.environ.get("SMTP_FROM", "").strip() or (f"Veritas AI Security <{user}>" if user else "Veritas AI Security <security@veritas-forensics.ai>")

        if not self.smtp_config.get("manual_override"):
            self.smtp_config = {
                "host": host,
                "port": port,
                "secure": secure,
                "user": user,
                "pass": clean_pass,
                "from": from_hdr,
                "manual_override": False
            }

    # ==========================================
    # Cryptographic Helpers (PBKDF2 + JWT)
    # ==========================================

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> str:
        if not salt:
            salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            120000
        )
        return f"{salt}${dk.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        try:
            if "$" not in stored_hash:
                return False
            salt, _ = stored_hash.split("$", 1)
            expected = AuthService.hash_password(password, salt)
            return hmac.compare_digest(expected, stored_hash)
        except Exception:
            return False

    @staticmethod
    def _hash_otp(otp: str, email: str) -> str:
        return hmac.new(
            JWT_SECRET.encode("utf-8"),
            f"{email.lower().strip()}:{otp.strip()}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def generate_token(self, user: Dict[str, Any], expires_hours: int = 168) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "sub": str(user.get("_id") or user.get("id")),
            "email": user.get("email"),
            "name": user.get("name"),
            "role": user.get("role", "user"),
            "is_verified": bool(user.get("is_verified", False)),
            "iat": now,
            "exp": now + (expires_hours * 3600)
        }
        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("utf-8").rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        s_b64 = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")
        return f"{h_b64}.{p_b64}.{s_b64}"

    def verify_token(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        clean = token.replace("Bearer ", "").strip()
        parts = clean.split(".")
        if len(parts) != 3:
            return None
        try:
            h_b64, p_b64, s_b64 = parts
            signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
            expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
            expected_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
            if not hmac.compare_digest(expected_b64, s_b64):
                return None

            pad = "=" * (-len(p_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(p_b64 + pad).decode("utf-8"))
            if payload.get("exp", 0) < int(time.time()):
                return None

            # Always sync with latest user state in MongoDB/store
            user = self.get_user_by_email(payload.get("email", ""))
            if user:
                return self._sanitize_user(user)

            return {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "name": payload.get("name"),
                "role": payload.get("role", "user"),
                "is_verified": payload.get("is_verified", False)
            }
        except Exception:
            return None

    # ==========================================
    # Persistence & MongoDB Integration
    # ==========================================

    def _load_or_seed_store(self):
        """Loads users primarily from MongoDB with local file fallback."""
        os.makedirs(os.path.dirname(AUTH_STORE_PATH), exist_ok=True)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        default_seed_users = [
            {
                "_id": "usr_admin_001",
                "name": "Chief Forensic Administrator",
                "email": "admin@veritas.ai",
                "password_hash": self.hash_password("Admin@123"),
                "role": "admin",
                "department": "Cybernetic Threat & Dataset Governance",
                "is_verified": True,
                "created_at": "2026-10-01 09:00:00",
                "last_login": now_str,
                "promoted_by": "System Root Genesis"
            },
            {
                "_id": "usr_std_002",
                "name": "Sarah Jenkins (Forensic Analyst)",
                "email": "analyst@veritas.ai",
                "password_hash": self.hash_password("User@123"),
                "role": "user",
                "department": "Media Verification Desk",
                "is_verified": True,
                "created_at": "2026-10-05 14:20:00",
                "last_login": now_str,
                "promoted_by": None
            },
            {
                "_id": "usr_std_003",
                "name": "Marcus Vance (OSINT Investigator)",
                "email": "investigator@veritas.ai",
                "password_hash": self.hash_password("User@123"),
                "role": "user",
                "department": "Disinformation Counter-Ops",
                "is_verified": True,
                "created_at": "2026-10-08 11:15:00",
                "last_login": "2026-10-10 18:30:00",
                "promoted_by": None
            },
            {
                "_id": "usr_std_004",
                "name": "Dr. Elena Rostova (ML Auditor)",
                "email": "elena.rostova@veritas.ai",
                "password_hash": self.hash_password("User@123"),
                "role": "admin",
                "department": "Neural Architecture & Fakeddit Lab",
                "is_verified": True,
                "created_at": "2026-10-03 10:05:00",
                "last_login": "2026-10-11 08:45:00",
                "promoted_by": "admin@veritas.ai"
            }
        ]

        # 1. Primary check: Read from MongoDB
        mongo_loaded = False
        if db_service.is_connected and db_service.db is not None:
            try:
                count = db_service.db.users.count_documents({})
                if count > 0:
                    mongo_users = list(db_service.db.users.find({}))
                    self._users = []
                    for doc in mongo_users:
                        doc["_id"] = str(doc.get("_id"))
                        self._users.append(doc)
                    mongo_loaded = True
                    logger.info(f"Loaded {len(self._users)} user account(s) directly from MongoDB.")
                else:
                    # Seed MongoDB directly with default accounts
                    for u in default_seed_users:
                        db_service.db.users.update_one(
                            {"email": u["email"]},
                            {"$set": u},
                            upsert=True
                        )
                    self._users = list(default_seed_users)
                    mongo_loaded = True
                    logger.info("Seeded initial user accounts into MongoDB.")
            except Exception as e:
                logger.warning(f"MongoDB user store load warning: {e}")

        # 2. Secondary fallback: Local JSON file
        if not mongo_loaded:
            if os.path.exists(AUTH_STORE_PATH):
                try:
                    with open(AUTH_STORE_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._users = data.get("users", [])
                        self._audit_logs = data.get("audit_logs", [])
                except Exception as e:
                    logger.warning(f"Could not read auth_store.json: {e}")

            if not self._users:
                self._users = list(default_seed_users)
                self._persist_store()

        # Seed initial audit log if empty
        if not self._audit_logs:
            self._audit_logs = [
                {
                    "id": "aud_001",
                    "timestamp": now_str,
                    "actor_email": "admin@veritas.ai",
                    "action": "SYSTEM_IAM_INITIALIZED",
                    "target_email": "admin@veritas.ai",
                    "details": "Identity & Access Control initialized with MongoDB primary persistence."
                }
            ]

    def _persist_store(self):
        """Persists user state to MongoDB as primary, syncing with local JSON backup."""
        # 1. Write to MongoDB
        if db_service.is_connected and db_service.db is not None:
            try:
                for u in self._users:
                    doc = dict(u)
                    email = doc.get("email")
                    if email:
                        db_service.db.users.update_one(
                            {"email": email},
                            {"$set": doc},
                            upsert=True
                        )
            except Exception as e:
                logger.debug(f"MongoDB user persist notice: {e}")

        # 2. Local file sync backup
        try:
            with open(AUTH_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "users": self._users,
                        "audit_logs": self._audit_logs[:200]
                    },
                    f,
                    indent=2
                )
        except Exception as e:
            logger.warning(f"Failed to persist auth_store.json backup: {e}")

    def _log_audit(self, actor_email: str, action: str, target_email: str, details: str):
        entry = {
            "id": f"aud_{int(time.time() * 1000)}_{secrets.token_hex(2)}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "actor_email": actor_email,
            "action": action,
            "target_email": target_email,
            "details": details
        }
        self._audit_logs.insert(0, entry)
        self._persist_store()
        if db_service.is_connected and db_service.db is not None:
            try:
                db_service.db.auth_audit_logs.insert_one(dict(entry))
            except Exception:
                pass

    @staticmethod
    def _sanitize_user(u: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(u.get("_id") or u.get("id")),
            "name": u.get("name", "User"),
            "email": u.get("email", ""),
            "role": u.get("role", "user"),
            "department": u.get("department", "Forensic Operations"),
            "is_verified": bool(u.get("is_verified", False)),
            "created_at": u.get("created_at", ""),
            "last_login": u.get("last_login", ""),
            "promoted_by": u.get("promoted_by")
        }

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        clean = (email or "").strip().lower()
        if not clean:
            return None
        # Check MongoDB first (case-insensitive)
        if db_service.is_connected and db_service.db is not None:
            try:
                import re
                doc = db_service.db.users.find_one({"email": {"$regex": f"^{re.escape(clean)}$", "$options": "i"}})
                if doc:
                    doc["_id"] = str(doc.get("_id"))
                    return doc
            except Exception as e:
                logger.debug(f"MongoDB read user by email notice: {e}")

        # Check in-memory store
        for u in self._users:
            if u.get("email", "").lower() == clean:
                return u
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        target_id = str(user_id)
        # Check MongoDB first
        if db_service.is_connected and db_service.db is not None:
            try:
                doc = db_service.db.users.find_one({"_id": target_id}) or db_service.db.users.find_one({"id": target_id})
                if doc:
                    doc["_id"] = str(doc.get("_id"))
                    return doc
            except Exception as e:
                logger.debug(f"MongoDB read user by id notice: {e}")

        for u in self._users:
            if str(u.get("_id") or u.get("id")) == target_id:
                return u
        return None

    # ==========================================
    # Secure OTP Generation & Email Delivery
    # ==========================================

    def generate_and_send_otp(
        self,
        email: str,
        name: str = "Investigator",
        purpose: str = "email_verification",
        role: str = "user",
        force_resend: bool = False
    ) -> Dict[str, Any]:
        clean_email = email.strip().lower()
        now = time.time()

        existing = self._otp_records.get(clean_email)
        if existing and not force_resend:
            cooldown_left = int(existing.get("resend_available_at", 0) - now)
            if cooldown_left > 0:
                return {
                    "status": "cooldown",
                    "cooldown_seconds": cooldown_left,
                    "message": f"Please wait {cooldown_left}s before requesting another verification code."
                }

        otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
        expires_minutes = 10
        otp_entry = {
            "otp_hash": self._hash_otp(otp_code, clean_email),
            "email": clean_email,
            "purpose": purpose,
            "created_at": now,
            "expires_at": now + (expires_minutes * 60),
            "resend_available_at": now + 15,
            "attempts": 0,
            "max_attempts": 5
        }
        self._otp_records[clean_email] = otp_entry

        # Record in MongoDB otp collection if available
        if db_service.is_connected and db_service.db is not None:
            try:
                db_service.db.otp_records.update_one(
                    {"email": clean_email},
                    {"$set": otp_entry},
                    upsert=True
                )
            except Exception:
                pass

        # Dispatch via Encrypted Email Service
        ok, send_msg, dispatch_info = email_service.send_otp_sync(
            to_email=clean_email,
            name=name,
            otp_code=otp_code,
            purpose=purpose,
            role=role,
            expires_minutes=expires_minutes
        )

        if not ok:
            logger.error(f"Failed to dispatch OTP to {clean_email}: {send_msg}")
            return {
                "status": "error",
                "email": clean_email,
                "message": send_msg or f"Failed to deliver verification code to {clean_email}."
            }

        # Record masked entry in outbox (Admin audit log only — NEVER leak OTP to users)
        masked_otp = f"{otp_code[:2]}****"
        outbox_entry = {
            "id": f"mail_{int(now * 1000)}",
            "to": clean_email,
            "name": name,
            "otp_masked": masked_otp,
            "purpose": purpose,
            "role": role,
            "subject": f"[Veritas AI] Security Verification Code",
            "delivery_mode": dispatch_info.get("delivery_mode", "Secure SMTP Delivery"),
            "message_id": dispatch_info.get("message_id", ""),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self._outbox_messages.insert(0, outbox_entry)
        self._outbox_messages = self._outbox_messages[:30]

        self._log_audit(
            actor_email=clean_email,
            action="SECURITY_OTP_DISPATCHED",
            target_email=clean_email,
            details=f"Dispatched 6-digit verification code via {outbox_entry['delivery_mode']} (Purpose: {purpose})"
        )

        return {
            "status": "success",
            "email": clean_email,
            "expires_in_seconds": expires_minutes * 60,
            "resend_cooldown_seconds": 15,
            "delivery_status": {
                "delivery_mode": outbox_entry["delivery_mode"],
                "message_id": outbox_entry["message_id"],
                "smtp_configured": email_service.is_configured()
            },
            "message": f"A secure 6-digit verification code has been dispatched to {clean_email}. Please check your inbox and spam folder."
        }

    def verify_otp_code(self, email: str, otp_code: str, purpose: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        clean_email = (email or "").strip().lower()
        clean_otp = (otp_code or "").strip()

        rec = self._otp_records.get(clean_email)
        if not rec and db_service.is_connected and db_service.db is not None:
            try:
                rec = db_service.db.otp_records.find_one({"email": clean_email})
            except Exception:
                pass

        if not rec:
            return False, "No active verification code found for this email. Please request a new code.", None

        now = time.time()
        if now > rec.get("expires_at", 0):
            self._otp_records.pop(clean_email, None)
            return False, "This verification code has expired (10-minute window elapsed). Please request a new code.", None

        if rec.get("attempts", 0) >= rec.get("max_attempts", 5):
            self._otp_records.pop(clean_email, None)
            return False, "Maximum verification attempts (5) exceeded. For security, please request a new verification code.", None

        rec["attempts"] = rec.get("attempts", 0) + 1
        expected_hash = self._hash_otp(clean_otp, clean_email)

        if not hmac.compare_digest(expected_hash, rec.get("otp_hash", "")):
            remaining = rec.get("max_attempts", 5) - rec["attempts"]
            return False, f"Invalid verification code. {remaining} attempt(s) remaining.", None

        # Valid OTP! Consume it and mark user verified
        self._otp_records.pop(clean_email, None)
        if db_service.is_connected and db_service.db is not None:
            try:
                db_service.db.otp_records.delete_one({"email": clean_email})
            except Exception:
                pass

        user = self.get_user_by_email(clean_email)
        if user:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user["is_verified"] = True
            user["last_login"] = now_str
            self._persist_store()

            # Update MongoDB directly
            if db_service.is_connected and db_service.db is not None:
                try:
                    db_service.db.users.update_one(
                        {"email": clean_email},
                        {"$set": {"is_verified": True, "last_login": now_str}}
                    )
                except Exception:
                    pass

            self._log_audit(
                actor_email=clean_email,
                action="EMAIL_OTP_VERIFIED",
                target_email=clean_email,
                details="Verified email ownership via 6-digit security code."
            )
            return True, "Email verified successfully!", self._sanitize_user(user)

        return True, "Verification code confirmed successfully.", None

    # ==========================================
    # Registration, Login & Password Reset
    # ==========================================

    def register_user(
        self,
        name: str,
        email: str,
        password: str,
        department: str = "Forensic Investigation Unit"
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        clean_email = (email or "").strip().lower()
        clean_name = (name or "").strip()

        if not clean_email or "@" not in clean_email:
            return False, "Please provide a valid email address.", None
        if len(password or "") < 6:
            return False, "Password must be at least 6 characters long.", None
        if not clean_name:
            return False, "Please provide your full name or investigator handle.", None

        existing = self.get_user_by_email(clean_email)
        if existing:
            if not existing.get("is_verified"):
                existing["name"] = clean_name
                existing["password_hash"] = self.hash_password(password)
                existing["department"] = department

                # Update MongoDB directly
                if db_service.is_connected and db_service.db is not None:
                    try:
                        db_service.db.users.update_one(
                            {"email": clean_email},
                            {"$set": {
                                "name": clean_name,
                                "password_hash": self.hash_password(password),
                                "department": department
                            }}
                        )
                    except Exception as e:
                        logger.error(f"MongoDB unverified user update error: {e}")

                # Ensure in-memory list has this user
                found_in_mem = False
                for idx, u in enumerate(self._users):
                    if u.get("email", "").lower() == clean_email:
                        self._users[idx] = existing
                        found_in_mem = True
                        break
                if not found_in_mem:
                    self._users.append(existing)

                self._persist_store()
                otp_res = self.generate_and_send_otp(
                    email=clean_email,
                    name=clean_name,
                    purpose="email_verification",
                    role=existing.get("role", "user"),
                    force_resend=True
                )
                if otp_res.get("status") == "error":
                    return False, otp_res.get("message", "Unable to deliver verification code via email. Please check SMTP settings."), None
                return True, "Account exists but is unverified. A fresh verification code has been dispatched to your email.", {
                    "user": self._sanitize_user(existing),
                    "requires_otp": True,
                    "otp_dispatch": otp_res
                }
            return False, f"An account with email '{clean_email}' is already registered and verified.", None

        # Check existing admins
        has_admin = any(u.get("role") == "admin" for u in self._users)
        assigned_role = "user" if has_admin else "admin"

        new_user = {
            "_id": f"usr_{int(time.time() * 1000)}_{secrets.token_hex(2)}",
            "name": clean_name,
            "email": clean_email,
            "password_hash": self.hash_password(password),
            "role": assigned_role,
            "department": department or "Forensic Analysis Unit",
            "is_verified": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_login": "",
            "promoted_by": "Initial Setup" if assigned_role == "admin" else None
        }
        self._users.append(new_user)
        self._persist_store()

        self._log_audit(
            actor_email=clean_email,
            action="USER_REGISTERED",
            target_email=clean_email,
            details=f"Registered new '{assigned_role}' account ({clean_name}). Stored in MongoDB."
        )

        otp_res = self.generate_and_send_otp(
            email=clean_email,
            name=clean_name,
            purpose="email_verification",
            role=assigned_role,
            force_resend=True
        )

        if otp_res.get("status") == "error":
            # Remove newly created user if initial dispatch fails so they can retry cleanly
            self._users = [u for u in self._users if u.get("email") != clean_email]
            if db_service.is_connected and db_service.db is not None:
                try:
                    db_service.db.users.delete_one({"email": clean_email})
                except Exception:
                    pass
            self._persist_store()
            return False, otp_res.get("message", "Unable to deliver verification code via email. Please check SMTP settings."), None

        return True, "Registration initiated! Please enter the 6-digit code sent to your email.", {
            "user": self._sanitize_user(new_user),
            "requires_otp": True,
            "otp_dispatch": otp_res
        }

    def login_user(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        clean_email = (email or "").strip().lower()
        user = self.get_user_by_email(clean_email)
        if not user:
            return False, "No account found matching that email address.", None

        if not self.verify_password(password or "", user.get("password_hash", "")):
            self._log_audit(
                actor_email=clean_email,
                action="LOGIN_FAILED",
                target_email=clean_email,
                details="Invalid password attempt."
            )
            return False, "Invalid password. Please check your credentials and try again.", None

        if not user.get("is_verified", False):
            otp_res = self.generate_and_send_otp(
                email=clean_email,
                name=user.get("name", "Investigator"),
                purpose="email_verification",
                role=user.get("role", "user"),
                force_resend=True
            )
            return False, "Your email is not verified yet. We just sent a new 6-digit verification code to your email.", {
                "requires_otp": True,
                "email": clean_email,
                "user": self._sanitize_user(user),
                "otp_dispatch": otp_res
            }

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user["last_login"] = now_str
        self._persist_store()

        sanitized = self._sanitize_user(user)
        token = self.generate_token(user)

        self._log_audit(
            actor_email=clean_email,
            action="USER_AUTHENTICATED",
            target_email=clean_email,
            details=f"Authenticated session started with '{sanitized['role'].upper()}' clearance."
        )

        return True, f"Welcome back, {sanitized['name']}!", {
            "user": sanitized,
            "token": token,
            "requires_otp": False
        }

    def reset_password_with_otp(
        self,
        email: str,
        otp_code: str,
        new_password: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        clean_email = (email or "").strip().lower()
        if len(new_password or "") < 6:
            return False, "New password must be at least 6 characters long.", None

        user = self.get_user_by_email(clean_email)
        if not user:
            return False, f"No account found with email '{clean_email}'.", None

        ok, msg, _ = self.verify_otp_code(clean_email, otp_code, purpose="password_reset")
        if not ok:
            return False, msg, None

        new_hash = self.hash_password(new_password)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Update in-memory user list
        found_in_mem = False
        for u in self._users:
            if u.get("email", "").lower() == clean_email:
                u["password_hash"] = new_hash
                u["is_verified"] = True
                u["last_login"] = now_str
                found_in_mem = True
                user = u
                break

        if not found_in_mem:
            user["password_hash"] = new_hash
            user["is_verified"] = True
            user["last_login"] = now_str
            self._users.append(user)

        # 2. Update MongoDB directly
        if db_service.is_connected and db_service.db is not None:
            try:
                db_service.db.users.update_one(
                    {"email": clean_email},
                    {"$set": {
                        "password_hash": new_hash,
                        "is_verified": True,
                        "last_login": now_str
                    }},
                    upsert=True
                )
            except Exception as e:
                logger.error(f"MongoDB password reset update error: {e}")

        self._persist_store()

        self._log_audit(
            actor_email=clean_email,
            action="PASSWORD_RESET_COMPLETED",
            target_email=clean_email,
            details="Password reset completed via secure email code verification."
        )

        sanitized = self._sanitize_user(user)
        token = self.generate_token(user)
        return True, "Password updated successfully! Welcome back to your workspace.", {
            "user": sanitized,
            "token": token
        }

    # ==========================================
    # Admin Access Control (Promote / Demote / Manage)
    # ==========================================

    def update_user_role(
        self,
        admin_user: Dict[str, Any],
        target_user_id: str,
        new_role: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        if admin_user.get("role") != "admin":
            return False, "Access Denied: Only Administrators can modify user clearance roles.", None

        clean_role = (new_role or "").strip().lower()
        if clean_role not in ("admin", "user"):
            return False, "Invalid role specified. Must be 'admin' or 'user'.", None

        target = self.get_user_by_id(target_user_id) or self.get_user_by_email(target_user_id)
        if not target:
            return False, f"User '{target_user_id}' not found.", None

        old_role = target.get("role", "user")
        if old_role == clean_role:
            return True, f"{target.get('name')} already has '{clean_role.upper()}' clearance.", self._sanitize_user(target)

        # Prevent demoting primary root admin or last remaining admin
        if old_role == "admin" and clean_role == "user":
            if target.get("email", "").lower() == "admin@veritas.ai":
                return False, "Cannot demote the Primary Root System Administrator (admin@veritas.ai).", None
            admin_count = sum(1 for u in self._users if u.get("role") == "admin")
            if admin_count <= 1:
                return False, "Cannot demote the last remaining Administrator in the system.", None

        target["role"] = clean_role
        if clean_role == "admin":
            target["promoted_by"] = admin_user.get("email", "admin")
        else:
            target["promoted_by"] = None

        self._persist_store()

        action_type = "ROLE_PROMOTED_TO_ADMIN" if clean_role == "admin" else "ROLE_DEMOTED_TO_USER"
        action_verb = "Promoted to ADMIN (Full Datasets & Streams Access)" if clean_role == "admin" else "Demoted to standard USER (Restricted Datasets & Streams)"

        self._log_audit(
            actor_email=admin_user.get("email", "admin"),
            action=action_type,
            target_email=target.get("email", ""),
            details=f"{action_verb} by {admin_user.get('name')} ({admin_user.get('email')})."
        )

        return True, f"Successfully updated {target.get('name')} ({target.get('email')}) to {clean_role.upper()}!", self._sanitize_user(target)

    def admin_verify_user(self, admin_user: Dict[str, Any], target_user_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        if admin_user.get("role") != "admin":
            return False, "Only Administrators can manually verify user accounts.", None

        target = self.get_user_by_id(target_user_id) or self.get_user_by_email(target_user_id)
        if not target:
            return False, "Target user not found.", None

        target["is_verified"] = True
        self._persist_store()
        self._log_audit(
            actor_email=admin_user.get("email", "admin"),
            action="ADMIN_MANUAL_VERIFICATION",
            target_email=target.get("email", ""),
            details=f"Manually verified email status by administrator {admin_user.get('email')}."
        )
        return True, f"Verified account {target.get('email')}.", self._sanitize_user(target)

    def admin_delete_user(self, admin_user: Dict[str, Any], target_user_id: str) -> Tuple[bool, str]:
        if admin_user.get("role") != "admin":
            return False, "Only Administrators can remove user accounts."

        target = self.get_user_by_id(target_user_id) or self.get_user_by_email(target_user_id)
        if not target:
            return False, "Target user not found."

        if target.get("email", "").lower() == "admin@veritas.ai":
            return False, "Cannot delete the Primary Root System Administrator."
        if str(target.get("_id")) == str(admin_user.get("id")):
            return False, "You cannot delete your own active administrator session."

        self._users = [u for u in self._users if str(u.get("_id")) != str(target.get("_id"))]
        self._persist_store()

        if db_service.is_connected and db_service.db is not None:
            try:
                db_service.db.users.delete_one({"email": target.get("email")})
            except Exception:
                pass

        self._log_audit(
            actor_email=admin_user.get("email", "admin"),
            action="USER_ACCOUNT_REMOVED",
            target_email=target.get("email", ""),
            details=f"Removed user account ({target.get('name')}) from MongoDB."
        )
        return True, f"Removed account {target.get('email')}."

    def list_users_for_admin(
        self,
        query: Optional[str] = None,
        role_filter: str = "all"
    ) -> Dict[str, Any]:
        # Refresh from MongoDB if connected
        if db_service.is_connected and db_service.db is not None:
            try:
                mongo_users = list(db_service.db.users.find({}))
                if mongo_users:
                    self._users = mongo_users
            except Exception:
                pass

        sanitized_list = [self._sanitize_user(u) for u in self._users]
        filtered = []
        for u in sanitized_list:
            if role_filter and role_filter != "all":
                if role_filter == "unverified" and u["is_verified"]:
                    continue
                elif role_filter in ("admin", "user") and u["role"] != role_filter:
                    continue
            if query:
                q = query.lower().strip()
                if (
                    q not in u["name"].lower()
                    and q not in u["email"].lower()
                    and q not in u.get("department", "").lower()
                ):
                    continue
            filtered.append(u)

        total_users = len(sanitized_list)
        admin_count = sum(1 for u in sanitized_list if u["role"] == "admin")
        user_count = sum(1 for u in sanitized_list if u["role"] == "user")
        verified_count = sum(1 for u in sanitized_list if u["is_verified"])

        return {
            "users": filtered,
            "stats": {
                "total": total_users,
                "admins": admin_count,
                "standard_users": user_count,
                "verified": verified_count,
                "unverified": total_users - verified_count
            },
            "audit_logs": self._audit_logs[:40],
            "outbox": self._outbox_messages[:15],
            "smtp_status": {
                "host": self.smtp_config.get("host"),
                "port": self.smtp_config.get("port"),
                "user": self.smtp_config.get("user"),
                "from": self.smtp_config.get("from"),
                "configured": email_service.is_configured()
            }
        }

    def update_smtp_settings(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: Optional[str] = None,
        secure: bool = False
    ) -> Tuple[bool, str]:
        clean_host = host.strip() or "smtp.gmail.com"
        clean_pass = password.replace(" ", "").strip() if "gmail" in clean_host.lower() else password.strip()
        self.smtp_config = {
            "host": clean_host,
            "port": int(port or 465),
            "secure": bool(secure or int(port or 465) == 465),
            "user": user.strip(),
            "pass": clean_pass,
            "from": (from_addr or "").strip() or (f"Veritas AI Security <{user.strip()}>" if user.strip() else "Veritas AI Security <security@veritas-forensics.ai>"),
            "manual_override": True
        }
        os.environ["SMTP_HOST"] = self.smtp_config["host"]
        os.environ["SMTP_PORT"] = str(self.smtp_config["port"])
        os.environ["SMTP_USER"] = self.smtp_config["user"]
        os.environ["SMTP_PASS"] = self.smtp_config["pass"]
        os.environ["SMTP_PASSWORD"] = self.smtp_config["pass"]
        os.environ["SMTP_FROM"] = self.smtp_config["from"]

        email_service._refresh_config()

        if self.smtp_config["user"] and self.smtp_config["pass"]:
            return True, f"Encrypted SMTP configured for {self.smtp_config['user']} ({self.smtp_config['host']}:{self.smtp_config['port']})!"
        return True, "Switched to Local Security Dispatch mode."


auth_service = AuthService()
