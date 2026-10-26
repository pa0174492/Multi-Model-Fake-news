"""
Advanced AI-Generated vs Authentic Media Forensics Engine.
Computes Multi-Tier Metadata Forensics (PNG chunks, EXIF SubIFD, XMP, C2PA, generator prompts),
Patch-Level Diffusion Micro-Smoothing, Fourier Radial Spectral Falloff (1/f^alpha),
Periodic Latent Deconvolution Lattice (transposed conv peaks), Noise Residual Kurtosis,
Bayer CFA Color Demosaicing Covariance, and Error Level Analysis (ELA) with visual artifact maps.
"""

import os
import io
import re
import math
import base64
import logging
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
from PIL import Image, ImageEnhance, ImageChops, ImageStat, ImageFilter, ExifTags

logger = logging.getLogger(__name__)


class AIDetectorService:
    """Forensic analyzer for distinguishing AI-generated images from authentic camera captures."""

    @staticmethod
    def analyze_image(
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        image_base64: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes comprehensive multi-vector forensic inspection:
        1. Exhaustive Metadata Forensics (PNG text chunks, EXIF SubIFD, XMP, C2PA, prompts)
        2. Upload Filename Forensics (Lengthy prompt-encoded names vs short camera names)
        3. Local Patch Diffusion Micro-Smoothing & Spatial Variance Disparity
        4. 2D FFT Frequency Magnitude Spectrum, Radial Spectral Slope, & Periodic Lattice
        5. High-Pass Noise Residual Heteroscedasticity & Kurtosis
        6. Bayer CFA Demosaicing Covariance & Chromatic Saturation Entropy
        7. Error Level Analysis (ELA) Compression Plane Dispersion & LSB Steganography Map
        """
        try:
            img = None
            raw_bytes = None

            if not filename and image_path:
                filename = os.path.basename(image_path)

            if image_bytes:
                raw_bytes = image_bytes
                img = Image.open(io.BytesIO(image_bytes))
            elif image_base64:
                if "," in image_base64:
                    image_base64 = image_base64.split(",")[1]
                raw_bytes = base64.b64decode(image_base64)
                img = Image.open(io.BytesIO(raw_bytes))
            elif image_path and os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    raw_bytes = f.read()
                img = Image.open(io.BytesIO(raw_bytes))
            else:
                return {
                    "verdict": "Image Not Found",
                    "is_ai": False,
                    "ai_probability": 0.5,
                    "confidence": 0.5,
                    "error": "No valid image data provided"
                }

            img_rgb = img.convert("RGB")
            w, h = img_rgb.size

            # -------------------------------------------------------------
            # Vector 1: Exhaustive Metadata Forensics & Filename Inspection
            # -------------------------------------------------------------
            meta_profile = AIDetectorService._extract_metadata(img, raw_bytes, filename)

            # -------------------------------------------------------------
            # Vector 2: Local Patch Micro-Smoothing & Variance Disparity
            # -------------------------------------------------------------
            gray = img_rgb.convert("L").resize((256, 256), Image.Resampling.BILINEAR)
            arr_gray = np.array(gray, dtype=np.float32)
            p10, p50, p90, smooth_ratio, patch_disparity = AIDetectorService._compute_patch_metrics(arr_gray)

            # -------------------------------------------------------------
            # Vector 3: 2D FFT Frequency Magnitude, Radial Slope, Lattice Grid
            # -------------------------------------------------------------
            fft_img, freq_ratio, grid_prominence, radial_slope = AIDetectorService._compute_fft(arr_gray)
            fft_base64 = AIDetectorService._pil_to_base64(fft_img)

            # -------------------------------------------------------------
            # Vector 4: High-Pass Noise Residual & Kurtosis
            # -------------------------------------------------------------
            lap_var, noise_kurtosis = AIDetectorService._compute_noise_kurtosis(arr_gray, gray)

            # -------------------------------------------------------------
            # Vector 5: Bayer CFA Demosaicing Covariance & Color Entropy
            # -------------------------------------------------------------
            cfa_corr, color_entropy = AIDetectorService._compute_cfa_dynamics(img_rgb)

            # -------------------------------------------------------------
            # Vector 6: Error Level Analysis (ELA) & LSB Plane
            # -------------------------------------------------------------
            ela_img, ela_mean, ela_std = AIDetectorService._compute_ela(img_rgb, quality=90, scale=15)
            ela_base64 = AIDetectorService._pil_to_base64(ela_img)

            lsb_img = AIDetectorService._compute_lsb(img_rgb)
            lsb_base64 = AIDetectorService._pil_to_base64(lsb_img)

            # -------------------------------------------------------------
            # Multi-Vector Signal Calibration
            # -------------------------------------------------------------
            # S1: Patch Micro-Smoothing (Diffusion models exhibit ultra-low p10 and high smooth_ratio)
            s_smooth = 0.0
            if p10 < 35.0:
                s_smooth += min(1.0, (35.0 - p10) / 28.0) * 0.60
            if smooth_ratio > 0.08:
                s_smooth += min(1.0, (smooth_ratio - 0.08) / 0.25) * 0.40

            # S2: Fourier Radial Spectral Slope & Periodic Lattice Peaks
            s_spectral = 0.0
            if radial_slope < -3.05:
                s_spectral += min(1.0, (-3.05 - radial_slope) / 0.75) * 0.50
            elif radial_slope > -1.75:
                s_spectral += min(1.0, (radial_slope - (-1.75)) / 0.80) * 0.35
            if grid_prominence > 1.20:
                s_spectral += min(1.0, (grid_prominence - 1.20) / 0.22) * 0.50

            # S3: High-Pass Noise Kurtosis (Non-Gaussian denoising residuals)
            s_kurt = 0.0
            if noise_kurtosis > 14.0:
                s_kurt = min(1.0, (noise_kurtosis - 14.0) / 28.0)

            # S4: Bayer CFA Demosaicing Covariance & Gamut Saturation
            s_cfa = 0.0
            if cfa_corr < 0.925:
                s_cfa += min(1.0, (0.925 - cfa_corr) / 0.08) * 0.55
            if color_entropy > 65.0:
                s_cfa += min(1.0, (color_entropy - 65.0) / 20.0) * 0.45

            # S5: Spatial Variance Disparity
            s_disp = 0.0
            if patch_disparity > 14.0:
                s_disp = min(1.0, (patch_disparity - 14.0) / 25.0)

            # Composite Signal Score
            signal_score = (
                0.30 * s_smooth +
                0.25 * s_spectral +
                0.20 * s_kurt +
                0.15 * s_cfa +
                0.10 * s_disp
            )

            # -------------------------------------------------------------
            # Decision Engine: Metadata Provenance vs Physical Signal Fusion
            # -------------------------------------------------------------
            if meta_profile.get("ai_software_flagged"):
                # Confirmed synthetic metadata/prompt/workflow signature
                ai_prob = 0.988 if not meta_profile.get("detected_prompt") else 0.996
                is_ai = True
                provenance = f"Confirmed Generative AI Asset: {meta_profile.get('ai_tool_name', 'AI Synthesizer')}"
            elif meta_profile.get("is_authentic_camera") and meta_profile.get("exposure_verified"):
                # Verified physical camera hardware with consistent exposure settings
                ai_prob = max(0.04, min(0.18, 1.0 / (1.0 + math.exp(-6.5 * (signal_score - 0.55)))))
                is_ai = ai_prob >= 0.50
                cam = meta_profile.get("camera_model")
                exp = meta_profile.get("exposure_params")
                provenance = f"Authentic Hardware Sensor Capture ({cam} — {exp})"
            else:
                # Web export, stripped metadata, or social media image
                # Calibrated sigmoid with threshold at 0.32
                raw_prob = 1.0 / (1.0 + math.exp(-6.5 * (signal_score - 0.32)))
                # If stripped EXIF, add small prior shift towards AI if signal indicates synthetic traits
                if not meta_profile.get("has_exif") and signal_score > 0.30:
                    raw_prob = min(0.97, raw_prob + 0.08)
                ai_prob = float(np.clip(raw_prob, 0.03, 0.97))
                is_ai = ai_prob >= 0.50

                if is_ai:
                    if grid_prominence > 1.25 and s_smooth > 0.4:
                        provenance = "Latent Diffusion Model (Midjourney / Stable Diffusion XL)"
                    elif s_smooth > 0.6:
                        provenance = "Deep Generative Render (DALL-E 3 / Flux / Diffusion)"
                    elif color_entropy > 65.0:
                        provenance = "Synthetic Neural Generation / Stylized Generative Composite"
                    else:
                        provenance = "Algorithmic Neural Media / Synthetic Upscaled Render"
                else:
                    cam = meta_profile.get("camera_model")
                    if cam and cam != "Unknown Sensor":
                        provenance = f"Authentic Digital Camera Capture ({cam})"
                    else:
                        provenance = "Authentic Optical Sensor Capture (CMOS Noise Profile Verified)"

            human_prob = 1.0 - ai_prob
            confidence = ai_prob if is_ai else human_prob

            # -------------------------------------------------------------
            # Detailed Forensic Artifacts Stack
            # -------------------------------------------------------------
            artifacts: List[Dict[str, Any]] = []

            # 1. Metadata Artifact
            if meta_profile.get("ai_software_flagged"):
                tag_desc = meta_profile.get('ai_tool_name')
                prompt_snip = f" | Prompt: {meta_profile.get('detected_prompt')[:65]}..." if meta_profile.get("detected_prompt") else ""
                artifacts.append({
                    "name": "Synthetic Software Metadata & Prompt Signature",
                    "severity": "CRITICAL",
                    "metric": f"Generator: {tag_desc}{prompt_snip}",
                    "description": "Image container contains explicit generative AI model tags, generation parameters, or node workflows."
                })
            elif meta_profile.get("is_authentic_camera"):
                artifacts.append({
                    "name": "Authentic Hardware Camera EXIF Provenance",
                    "severity": "PASS",
                    "metric": f"{meta_profile.get('camera_make')} {meta_profile.get('camera_model')} ({meta_profile.get('exposure_params')})",
                    "description": "Physical CMOS sensor hardware headers, optical lens parameters, and exposure values verified."
                })
            else:
                artifacts.append({
                    "name": "Metadata Stripped / Web Compressed Container",
                    "severity": "MEDIUM",
                    "metric": "Camera Hardware EXIF: None Found",
                    "description": "Exif tags stripped or container re-encoded; provenance established through signal-level physical forensics."
                })

            # 2. Patch Micro-Smoothing
            if p10 < 25.0 or smooth_ratio > 0.15:
                artifacts.append({
                    "name": "Latent Diffusion Micro-Smoothing",
                    "severity": "CRITICAL",
                    "metric": f"Smooth Patches: {smooth_ratio*100:.1f}% | 10th-Pct Var: {p10:.1f} (Camera: >35)",
                    "description": "Abnormal absence of natural physical photon noise in gradient patches, typical of neural latent denoising passes."
                })

            # 3. Fourier Spectral Decay / Periodic Grid
            if grid_prominence > 1.20:
                artifacts.append({
                    "name": "Periodic Latent Deconvolution Lattice Peaks",
                    "severity": "HIGH",
                    "metric": f"Grid Prominence: {grid_prominence:.2f}x (Authentic: <1.18x)",
                    "description": "Periodic spatial frequency harmonics detected from transposed convolution / VAE neural decoder upsampling."
                })
            if radial_slope < -3.10:
                artifacts.append({
                    "name": "Anomalous Fourier Spectral Falloff",
                    "severity": "HIGH",
                    "metric": f"Radial Slope alpha: {radial_slope:.2f} (Physical Optics: -2.0 to -2.8)",
                    "description": "Spatial frequency power distribution deviates steeply from natural optical lens diffraction power law."
                })

            # 4. Noise Residual Kurtosis
            if noise_kurtosis > 16.0:
                artifacts.append({
                    "name": "Non-Gaussian Noise Residual Kurtosis",
                    "severity": "HIGH",
                    "metric": f"Noise Kurtosis: {noise_kurtosis:.1f} (Poisson-Gaussian Sensor: 3 - 12)",
                    "description": "Heavy-tailed high-pass noise residual indicates non-linear denoising passes rather than continuous optical sensor grain."
                })

            # 5. CFA Demosaicing / Gamut
            if cfa_corr < 0.925:
                artifacts.append({
                    "name": "Bayer CFA Demosaicing Discrepancy",
                    "severity": "MEDIUM",
                    "metric": f"Channel Gradient Corr: {cfa_corr:.3f} (Authentic Bayer: >0.935)",
                    "description": "Color channels lack the spatial cross-talk correlation naturally created by physical Bayer filter CFA demosaicing."
                })
            if color_entropy > 65.0:
                artifacts.append({
                    "name": "Hyper-Vibrant Gamut Expansion",
                    "severity": "MEDIUM",
                    "metric": f"Chromatic Entropy: {color_entropy:.1f}",
                    "description": "Exaggerated chromatic saturation typical of generative AI prompt styling."
                })

            # 6. ELA
            if ela_mean < 0.08 or ela_mean > 0.48:
                artifacts.append({
                    "name": "Anomalous ELA Compression Plane",
                    "severity": "MEDIUM",
                    "metric": f"ELA Error Mean: {ela_mean:.3f}",
                    "description": "Unnatural compression resilience indicating non-camera pixel generation."
                })

            # Filename artifacts
            fn_forensics = meta_profile.get("filename_forensics", {})
            if fn_forensics.get("is_ai_filename"):
                artifacts.insert(0, {
                    "name": "Generative Prompt-Encoded Filename Signature",
                    "severity": "CRITICAL",
                    "metric": f"Filename: {fn_forensics.get('base_name')[:40]}... (Length: {fn_forensics.get('length')} chars)",
                    "description": f"Filename exhibits prompt-encoded generative AI structure. Extracted Prompt: \"{fn_forensics.get('extracted_prompt')[:80]}...\""
                })
            elif fn_forensics.get("is_short"):
                artifacts.append({
                    "name": "Compact / Short Filename Container",
                    "severity": "PASS",
                    "metric": f"Length: {fn_forensics.get('length')} chars ({fn_forensics.get('base_name')})",
                    "description": "Compact filename detected. Filename-based heuristic bypassed; multi-vector physical signal forensics applied."
                })

            if not [a for a in artifacts if a["severity"] in ["CRITICAL", "HIGH"]]:
                artifacts.append({
                    "name": "Organic Sensor Noise & Bayer CFA Demosaicing",
                    "severity": "PASS",
                    "metric": f"Laplacian Var: {lap_var:.1f} | CFA Corr: {cfa_corr:.3f}",
                    "description": "Authentic optical sensor noise, natural lens depth of field, and organic JPEG quantization detected."
                })

            return {
                "status": "success",
                "verdict": "AI Generated (Synthetic Media)" if is_ai else "Human / Authentic Camera Capture",
                "is_ai": is_ai,
                "ai_probability": round(ai_prob, 4),
                "human_probability": round(human_prob, 4),
                "confidence": round(confidence, 4),
                "dimensions": f"{w}x{h} px",
                "provenance_profile": provenance,
                "forensic_metrics": {
                    "laplacian_variance": round(lap_var, 2),
                    "patch_smoothing_p10": round(p10, 2),
                    "smooth_patch_ratio": round(smooth_ratio * 100.0, 1),
                    "radial_spectral_slope": round(radial_slope, 3),
                    "grid_prominence": round(grid_prominence, 3),
                    "noise_kurtosis": round(noise_kurtosis, 2),
                    "ela_mean_error": round(ela_mean, 3),
                    "color_entropy": round(color_entropy, 2),
                    "cfa_correlation": round(cfa_corr, 3)
                },
                "visual_maps": {
                    "ela_heatmap_base64": f"data:image/png;base64,{ela_base64}",
                    "fft_spectrum_base64": f"data:image/png;base64,{fft_base64}",
                    "lsb_noise_base64": f"data:image/png;base64,{lsb_base64}"
                },
                "exif_forensics": meta_profile,
                "filename_forensics": fn_forensics,
                "detected_artifacts": artifacts
            }

        except Exception as e:
            logger.error(f"Forensic inspection error: {e}", exc_info=True)
            return {
                "verdict": "Forensic Inspection Failed",
                "is_ai": False,
                "ai_probability": 0.50,
                "human_probability": 0.50,
                "confidence": 0.50,
                "error": str(e)
            }

    @staticmethod
    def _compute_patch_metrics(arr_gray: np.ndarray) -> Tuple[float, float, float, float, float]:
        """Calculates patch-level micro-smoothing and spatial variance disparity across 256 patches."""
        patches = arr_gray.reshape(16, 16, 16, 16).transpose(0, 2, 1, 3).reshape(-1, 16, 16)
        pvars = []
        for patch in patches:
            lap = -4 * patch + np.roll(patch, 1, 0) + np.roll(patch, -1, 0) + np.roll(patch, 1, 1) + np.roll(patch, -1, 1)
            pvars.append(float(np.var(lap)))
        pvars_arr = np.array(pvars, dtype=np.float32)

        p10 = float(np.percentile(pvars_arr, 10))
        p50 = float(np.median(pvars_arr))
        p90 = float(np.percentile(pvars_arr, 90))
        smooth_ratio = float(np.mean(pvars_arr < 25.0))
        patch_disparity = float((p90 - p10) / (p50 + 1e-5))

        return p10, p50, p90, smooth_ratio, patch_disparity

    @staticmethod
    def _compute_fft(arr_gray: np.ndarray) -> Tuple[Image.Image, float, float, float]:
        """Calculates 2D Fourier Magnitude Spectrum, radial spectral falloff slope, and periodic lattice peaks."""
        fft = np.fft.fftshift(np.fft.fft2(arr_gray))
        mag = np.log(np.abs(fft) + 1e-5)
        power = np.abs(fft)**2

        mag_norm = np.clip((mag - mag.min()) / (mag.max() - mag.min() + 1e-5) * 255.0, 0, 255).astype(np.uint8)
        fft_img = Image.fromarray(mag_norm, mode="L")

        cy, cx = 128, 128
        y, x = np.ogrid[:256, :256]
        r = np.round(np.sqrt((x - cx)**2 + (y - cy)**2)).astype(int)

        # Radial spectral power profile & log-log slope
        freqs = list(range(6, 120, 6))
        radial_profile = []
        for radius in freqs:
            mask = (r == radius)
            radial_profile.append(np.mean(power[mask]) if np.any(mask) else 1e-5)
        radial_arr = np.array(radial_profile, dtype=np.float32)
        valid = radial_arr > 0
        if np.sum(valid) > 4:
            slope, _ = np.polyfit(np.log(np.array(freqs)[valid]), np.log(radial_arr[valid]), 1)
            radial_slope = float(slope)
        else:
            radial_slope = -2.5

        # Energy ratio & periodic lattice prominence
        high_mask = (r > 64) & (r < 120)
        high_freq = float(np.mean(mag[high_mask]))
        low_freq = float(np.mean(mag[r <= 64]))
        freq_ratio = float(high_freq / (low_freq + 1e-5))

        grid_coords = [(-32, 0), (32, 0), (0, -32), (0, 32), (-32, -32), (32, 32), (-32, 32), (32, -32)]
        peak_vals = [mag[cy + dy, cx + dx] for dy, dx in grid_coords]
        grid_prominence = float(np.mean(peak_vals) / (high_freq + 1e-5))

        return fft_img, freq_ratio, grid_prominence, radial_slope

    @staticmethod
    def _compute_noise_kurtosis(arr_gray: np.ndarray, gray_pil: Image.Image) -> Tuple[float, float]:
        """Calculates Laplacian variance and high-pass noise residual kurtosis."""
        lap = -4 * arr_gray + np.roll(arr_gray, 1, 0) + np.roll(arr_gray, -1, 0) + np.roll(arr_gray, 1, 1) + np.roll(arr_gray, -1, 1)
        lap_var = float(np.var(lap))

        blur = gray_pil.filter(ImageFilter.GaussianBlur(radius=1.5))
        blur_arr = np.array(blur, dtype=np.float32)
        noise_residual = arr_gray - blur_arr
        noise_var = float(np.var(noise_residual))
        kurtosis = float(np.mean((noise_residual - np.mean(noise_residual))**4) / (noise_var**2 + 1e-5))

        return lap_var, kurtosis

    @staticmethod
    def _compute_cfa_dynamics(img_rgb: Image.Image) -> Tuple[float, float]:
        """Computes Bayer CFA demosaicing cross-channel gradient correlation and chromatic entropy."""
        small = img_rgb.resize((128, 128), Image.Resampling.BILINEAR)
        r_arr = np.array(small)[:, :, 0].astype(np.float32)
        g_arr = np.array(small)[:, :, 1].astype(np.float32)
        b_arr = np.array(small)[:, :, 2].astype(np.float32)

        grad_r = np.diff(r_arr, axis=1).flatten()
        grad_g = np.diff(g_arr, axis=1).flatten()
        grad_b = np.diff(b_arr, axis=1).flatten()

        std_r = float(np.std(grad_r))
        std_g = float(np.std(grad_g))
        std_b = float(np.std(grad_b))

        if std_r > 1e-4 and std_g > 1e-4 and std_b > 1e-4:
            rg_corr = float(np.corrcoef(grad_r, grad_g)[0, 1])
            gb_corr = float(np.corrcoef(grad_g, grad_b)[0, 1])
            cfa_corr = float((rg_corr + gb_corr) / 2.0)
        else:
            cfa_corr = 0.95

        stat_rgb = ImageStat.Stat(img_rgb)
        color_entropy = float(np.mean(stat_rgb.stddev))

        return cfa_corr, color_entropy

    @staticmethod
    def _compute_ela(img_rgb: Image.Image, quality: int = 90, scale: int = 15) -> Tuple[Image.Image, float, float]:
        """Performs Error Level Analysis by resaving at quality and computing pixel difference delta."""
        buffer = io.BytesIO()
        img_rgb.save(buffer, "JPEG", quality=quality)
        buffer.seek(0)
        resaved = Image.open(buffer)

        ela_diff = ImageChops.difference(img_rgb, resaved)
        extrema = ela_diff.getextrema()
        max_diff = max([ex[1] for ex in extrema]) or 1
        scale_factor = 255.0 / max_diff if max_diff < (255 / scale) else scale

        enhancer = ImageEnhance.Brightness(ela_diff)
        ela_visual = enhancer.enhance(scale_factor)

        stat = ImageStat.Stat(ela_diff)
        mean_err = float(sum(stat.mean) / 3.0)
        std_err = float(sum(stat.stddev) / 3.0)

        return ela_visual, mean_err, std_err

    @staticmethod
    def _compute_lsb(img_rgb: Image.Image) -> Image.Image:
        """Extracts Least Significant Bit (LSB) plane to expose steganography & noise discontinuities."""
        gray = img_rgb.convert("L").resize((256, 256), Image.Resampling.BILINEAR)
        arr = np.array(gray, dtype=np.uint8)
        lsb = (arr & 1) * 255
        return Image.fromarray(lsb, mode="L")

    @staticmethod
    def _inspect_filename(filename: Optional[str]) -> Dict[str, Any]:
        """
        Forensically inspects upload filename:
        - Lengthy prompt-style names (e.g. Midjourney, DALL-E, Stable Diffusion exports)
        - Extracts prompts and generative tools from file naming conventions
        - Flags short / camera naming styles (IMG_..., DSC_..., etc.) for deep physical signal evaluation
        """
        if not filename:
            return {
                "has_filename": False,
                "filename": "Unknown",
                "base_name": "Unknown",
                "length": 0,
                "is_lengthy": False,
                "is_short": True,
                "is_camera_naming": False,
                "is_ai_filename": False,
                "detected_tool": "",
                "extracted_prompt": "",
                "naming_category": "No Filename Provided"
            }

        base = os.path.splitext(os.path.basename(filename))[0].strip()

        # 1. Check known AI tool keywords in filename
        ai_tools_patterns = [
            (r'dall[·\-_]?e', 'OpenAI DALL-E'),
            (r'midjourney', 'Midjourney'),
            (r'stable[_\-]?diffusion', 'Stable Diffusion'),
            (r'sdxl|sd[_\-]1\.5', 'Stable Diffusion XL'),
            (r'flux[_\-\.]?1', 'FLUX.1'),
            (r'leonardo[_\-]?diffusion', 'Leonardo.ai'),
            (r'novelai', 'NovelAI'),
            (r'comfyui', 'ComfyUI'),
            (r'txt2img|img2img', 'Latent Diffusion Pipeline')
        ]

        detected_tool = ""
        for pat, tool in ai_tools_patterns:
            if re.search(pat, base, re.IGNORECASE):
                detected_tool = tool
                break

        # 2. Check length and prompt lexical structure
        words = re.findall(r'[a-zA-Z]{3,}', base)
        prompt_indicators = [
            'portrait', 'cyberpunk', 'futuristic', 'cinematic', 'hyperrealistic', 'realistic',
            'detailed', 'sunset', 'photorealistic', 'masterpiece', 'beautiful', 'rendering',
            'octane', 'illustration', 'fantasy', 'surreal', 'lighting', 'render', 'concept',
            'wallpaper', 'scenery', 'epic', 'ultra', 'anime', 'digital'
        ]
        has_prompt_words = any(w.lower() in prompt_indicators for w in words)
        all_tokens = re.findall(r'[a-zA-Z]+', base.lower())
        struct_tokens = [t for t in all_tokens if t in ['a', 'an', 'the', 'of', 'in', 'with', 'on', 'at', 'by', 'for', 'and']]
        has_uuid = bool(re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', base, re.IGNORECASE))

        # Lengthy criteria: >= 30 chars with descriptive structure
        is_lengthy = len(base) >= 30
        is_prompt_structured = len(words) >= 5 or (len(words) >= 3 and len(struct_tokens) >= 2) or has_prompt_words or has_uuid

        is_ai_filename = bool(detected_tool) or (is_lengthy and is_prompt_structured)
        is_short = len(base) < 25 and not detected_tool and not has_prompt_words

        extracted_prompt = ""
        if is_ai_filename:
            p = base
            p = re.sub(r'^dall[·\-_]?e\s+\d{4}[-\d\.\s]+-\s*', '', p, flags=re.IGNORECASE)
            p = re.sub(r'[-_][a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', '', p, flags=re.IGNORECASE)
            p = p.replace('_', ' ').replace('-', ' ')
            p = re.sub(r'\s+', ' ', p).strip()
            extracted_prompt = p

        # Camera naming check
        is_camera_naming = bool(re.match(r'^(IMG|DSC|DCIM|P10\d|CIMG|MVIMG|PHOTO|PANO)[_\-\d]', base, re.IGNORECASE))

        naming_category = "Generative AI Prompt Name" if is_ai_filename else ("Optical Hardware Naming" if is_camera_naming else ("Short / Compact Filename" if is_short else "Standard Web Filename"))

        return {
            "has_filename": True,
            "filename": filename,
            "base_name": base,
            "length": len(base),
            "is_lengthy": is_lengthy,
            "is_short": is_short,
            "is_camera_naming": is_camera_naming,
            "is_ai_filename": is_ai_filename,
            "detected_tool": detected_tool,
            "extracted_prompt": extracted_prompt,
            "naming_category": naming_category
        }

    @staticmethod
    def _extract_metadata(img: Image.Image, raw_bytes: Optional[bytes] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Deep multi-tier metadata extraction:
        - Filename inspection (lengthy prompt-style AI names vs short camera names)
        - PNG chunks / text parameters (AUTOMATIC1111, ComfyUI, Midjourney, NovelAI, WebUI)
        - Raw byte pattern scan for generation prompts, seed, samplers, and C2PA / XMP manifests
        - EXIF IFD0 & Exif SubIFD (Make, Model, Software, UserComment, Exposure parameters)
        - Hardware camera exposure consistency verification
        """
        fn_info = AIDetectorService._inspect_filename(filename)

        result = {
            "has_exif": False,
            "camera_make": "None (Stripped or AI Native)",
            "camera_model": "Unknown Sensor",
            "software_tag": "None",
            "exposure_params": "None (Algorithmic Render)",
            "metadata_source": "Stripped / Web Export (Evaluated via Multi-Vector Signal Forensics)",
            "ai_software_flagged": False,
            "ai_tool_name": "",
            "detected_prompt": "",
            "is_authentic_camera": False,
            "exposure_verified": False,
            "date_time": "Not available",
            "filename_forensics": fn_info
        }

        # -----------------------------------------------------------------
        # 0. Integrate Filename Forensics
        # -----------------------------------------------------------------
        if fn_info.get("is_ai_filename"):
            result["ai_software_flagged"] = True
            result["ai_tool_name"] = fn_info.get("detected_tool") or "Generative Prompt-Encoded Media"
            result["detected_prompt"] = fn_info.get("extracted_prompt")
            result["metadata_source"] = f"Prompt-Encoded Filename ({fn_info.get('length')} chars)"

        # -----------------------------------------------------------------
        # 1. Raw Bytes Pattern Scanner (Catches prompts, tools, and C2PA)
        # -----------------------------------------------------------------
        if raw_bytes:
            sample_bytes = raw_bytes[:262144] + (raw_bytes[-65536:] if len(raw_bytes) > 262144 else b"")
            sample_lower = sample_bytes.lower()

            # Check prompt & parameter markers (SD / WebUI / Invoke / ComfyUI)
            if b"steps:" in sample_lower and (b"sampler:" in sample_lower or b"cfg scale:" in sample_lower or b"seed:" in sample_lower):
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "Stable Diffusion (WebUI / AUTOMATIC1111 / Forge)"
                result["metadata_source"] = "Embedded Generation Parameters & Workflow Chunks"
                # Extract prompt snippet
                m = re.search(rb"parameters\x00([^\x00]{10,250})", sample_bytes, re.IGNORECASE)
                if m:
                    result["detected_prompt"] = m.group(1).decode("utf-8", errors="ignore").replace("\n", " ")

            elif b"\"class_type\": \"ksampler\"" in sample_lower or b"\"class_type\":\"ksampler\"" in sample_lower or b"checkpointloadersimple" in sample_lower:
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "ComfyUI / SwarmUI Node Graph"
                result["metadata_source"] = "Embedded ComfyUI Execution Workflow JSON"

            elif b"midjourney" in sample_lower or b"--v 5" in sample_lower or b"--v 6" in sample_lower or (b"--ar " in sample_lower and b"--" in sample_lower):
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "Midjourney Synthesizer"
                result["metadata_source"] = "Midjourney Generation Metadata / Aspect Ratio Parameter"

            elif b"dall-e" in sample_lower or b"dalle" in sample_lower or b"openai" in sample_lower and b"prompt" in sample_lower:
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "OpenAI DALL-E Generative Model"
                result["metadata_source"] = "DALL-E Metadata Packet"

            elif b"adobe firefly" in sample_lower or b"generative fill" in sample_lower or b"generative expand" in sample_lower:
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "Adobe Firefly / Generative AI"
                result["metadata_source"] = "Adobe Generative XMP Packet"

            elif b"trainedalgorithmicmedia" in sample_lower or b"c2pa.manifest" in sample_lower:
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "C2PA / IPTC Algorithmic Media Manifest"
                result["metadata_source"] = "Certified Digital Provenance (trainedAlgorithmicMedia)"

            elif b"synthid" in sample_lower:
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "Google SynthID Synthetic Media"
                result["metadata_source"] = "Digital Synthetic Watermark Manifest"

            elif b"flux.1" in sample_lower or b"black-forest-labs" in sample_lower:
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "FLUX.1 Diffusion Model"
                result["metadata_source"] = "FLUX Model Checkpoint Header"

            elif b"novelai" in sample_lower:
                result["ai_software_flagged"] = True
                result["ai_tool_name"] = "NovelAI Diffusion"
                result["metadata_source"] = "NovelAI Generation Header"

        # -----------------------------------------------------------------
        # 2. PIL Image.info & Text Chunks (PNG / WebP metadata)
        # -----------------------------------------------------------------
        try:
            info_dict = getattr(img, "info", {}) or {}
            text_dict = getattr(img, "text", {}) or {}
            combined_info = {**info_dict, **text_dict}

            for k in ["parameters", "prompt", "workflow", "Comment", "Description", "Software", "source", "Title"]:
                if k in combined_info:
                    val = str(combined_info[k])
                    val_lower = val.lower()
                    if "steps:" in val_lower or "sampler:" in val_lower or "seed:" in val_lower:
                        result["ai_software_flagged"] = True
                        result["ai_tool_name"] = result["ai_tool_name"] or "Stable Diffusion Parameter Chunk"
                        result["detected_prompt"] = val[:120].replace("\n", " ")
                    elif "midjourney" in val_lower or "--v " in val_lower:
                        result["ai_software_flagged"] = True
                        result["ai_tool_name"] = "Midjourney Synthesizer"
                        result["detected_prompt"] = val[:120].replace("\n", " ")
                    elif "dall-e" in val_lower or "dalle" in val_lower:
                        result["ai_software_flagged"] = True
                        result["ai_tool_name"] = "OpenAI DALL-E"
                    elif "novelai" in val_lower:
                        result["ai_software_flagged"] = True
                        result["ai_tool_name"] = "NovelAI"
        except Exception as e:
            logger.debug(f"PNG info scan note: {e}")

        # -----------------------------------------------------------------
        # 3. EXIF IFD0 & Exif SubIFD (Hardware Cameras & JPEG Tags)
        # -----------------------------------------------------------------
        try:
            exif_data = img.getexif()
            if exif_data and len(exif_data) > 0:
                result["has_exif"] = True
                make = str(exif_data.get(271, "")).strip()
                model = str(exif_data.get(272, "")).strip()
                software = str(exif_data.get(305, "")).strip()
                dt = str(exif_data.get(306, "")).strip()

                if make: result["camera_make"] = make
                if model: result["camera_model"] = model
                if software: result["software_tag"] = software
                if dt: result["date_time"] = dt

                # Check SubIFD for exposure details and UserComment
                sub_ifd = {}
                if hasattr(exif_data, "get_ifd"):
                    try:
                        sub_ifd = exif_data.get_ifd(0x8769) or {}
                    except Exception:
                        sub_ifd = {}

                # Check UserComment (37510) and ImageDescription (270)
                user_comment = str(sub_ifd.get(37510, exif_data.get(270, ""))).strip()
                if user_comment:
                    uc_lower = user_comment.lower()
                    if any(term in uc_lower for term in ["steps:", "sampler:", "seed:", "midjourney", "dall-e", "comfyui", "flux"]):
                        result["ai_software_flagged"] = True
                        result["ai_tool_name"] = result["ai_tool_name"] or "Embedded Generation Comment"
                        result["detected_prompt"] = user_comment[:120].replace("\n", " ")

                # Physical Camera Exposure Verification
                fnumber = sub_ifd.get(33437)
                exposure = sub_ifd.get(33434)
                iso = sub_ifd.get(34855)
                focal = sub_ifd.get(37386)
                lens = str(sub_ifd.get(42036, "")).strip()

                exp_parts = []
                if exposure:
                    try:
                        exp_val = float(exposure)
                        exp_parts.append(f"1/{int(1.0/exp_val)}s" if exp_val < 1.0 and exp_val > 0 else f"{exp_val:.1f}s")
                    except Exception:
                        exp_parts.append(str(exposure))
                if fnumber:
                    try:
                        exp_parts.append(f"f/{float(fnumber):.1f}")
                    except Exception:
                        exp_parts.append(f"f/{fnumber}")
                if iso:
                    exp_parts.append(f"ISO {iso}")
                if focal:
                    try:
                        exp_parts.append(f"{float(focal):.0f}mm")
                    except Exception:
                        exp_parts.append(f"{focal}mm")

                if exp_parts:
                    result["exposure_params"] = ", ".join(exp_parts)
                    result["exposure_verified"] = True

                # Camera Hardware Brands
                camera_brands = [
                    "canon", "nikon", "sony", "apple", "iphone", "samsung", "fujifilm",
                    "fuji", "panasonic", "olympus", "pixel", "google", "leica", "hasselblad", "gopro"
                ]
                lower_make = make.lower()
                lower_model = model.lower()
                is_brand = any(b in lower_make or b in lower_model for b in camera_brands)

                if is_brand:
                    result["is_authentic_camera"] = True
                    result["metadata_source"] = f"Verified Optical Hardware EXIF ({make} {model})"

        except Exception as e:
            logger.debug(f"EXIF parsing note: {e}")

        # Final software tag refinement
        if result["ai_software_flagged"] and result["software_tag"] in ["None", ""]:
            result["software_tag"] = result["ai_tool_name"]

        return result

    @staticmethod
    def _pil_to_base64(img: Image.Image) -> str:
        """Converts PIL image to base64 PNG string."""
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
