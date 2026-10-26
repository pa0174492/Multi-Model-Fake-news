"""
Direct Google Gemini API Helper with dynamic ModelService discovery via REST and SDK.
"""

import os
import logging
from typing import Optional, List, Dict, Any, Tuple
import requests
import google.generativeai as genai

logger = logging.getLogger(__name__)

PREFERENCE_ORDER = [
    "gemini-3.8-flash",
    "gemini-3.8-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-8b"
]


def list_gemini_models_for_key(api_key: str) -> Tuple[List[str], Optional[str]]:
    """
    Directly queries Google Generative Language ModelService via REST endpoint
    to retrieve the exact list of models that support generateContent for this key.
    """
    if not api_key:
        return [], "API key is empty."

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=7)
        if resp.status_code == 200:
            data = resp.json()
            models_raw = data.get("models", [])
            supported = []
            for m in models_raw:
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = m.get("name", "").replace("models/", "")
                    if name:
                        supported.append(name)
            return supported, None
        else:
            try:
                err_data = resp.json()
                msg = err_data.get("error", {}).get("message", f"HTTP {resp.status_code}")
                return [], msg
            except Exception:
                return [], f"HTTP Error {resp.status_code}: {resp.text[:120]}"
    except Exception as e:
        logger.warning(f"REST model listing failed: {e}. Trying SDK fallback...")

    # SDK Fallback
    try:
        genai.configure(api_key=api_key)
        sdk_models = []
        for m in genai.list_models():
            if "generateContent" in getattr(m, "supported_generation_methods", []):
                name = m.name.replace("models/", "")
                sdk_models.append(name)
        return sdk_models, None
    except Exception as e:
        return [], str(e)


def resolve_best_gemini_model(api_key: str) -> str:
    """Discovers available models and selects the optimal one for content generation."""
    models, err = list_gemini_models_for_key(api_key)
    if not models:
        return "gemini-1.5-flash"

    # Match in preference order
    for pref in PREFERENCE_ORDER:
        if pref in models:
            return pref
        for m in models:
            if pref in m:
                return m

    return models[0]


def test_gemini_key_and_get_model(api_key: str, chosen_model: Optional[str] = None) -> Tuple[bool, str, List[str], str]:
    """
    Validates API key against Google's API, discovers supported models, and executes test generation.
    Returns: (success: bool, model_name: str, available_models: List[str], message: str)
    """
    if not api_key:
        return False, "", [], "API key is required."

    models, err = list_gemini_models_for_key(api_key)
    if not models:
        return False, "", [], f"API key error: {err or 'No generateContent models found'}"

    target_model = chosen_model if (chosen_model and chosen_model in models) else resolve_best_gemini_model(api_key)

    # Test generation with chosen model
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(target_model)
        res = model.generate_content("Ping test. Reply with 'OK'.")
        if res and res.text:
            return True, target_model, models, f"Connected to {target_model} successfully!"
    except Exception as e:
        # Try second best if first failed
        for alt in models:
            if alt != target_model:
                try:
                    model = genai.GenerativeModel(alt)
                    res = model.generate_content("Ping test. Reply with 'OK'.")
                    if res and res.text:
                        return True, alt, models, f"Connected to {alt} successfully!"
                except Exception:
                    continue
        return False, target_model, models, f"Model generation error on {target_model}: {str(e)}"

    return True, target_model, models, f"Discovered {len(models)} models. Active: {target_model}"
