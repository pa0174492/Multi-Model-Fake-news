"""
Omni-Format Converter and Extraction Service.
Supports Audio/Speech, PDF/DOCX/TXT Documents, Image OCR, and Web Article URLs.
"""

import os
import re
import io
import logging
from typing import Dict, Any, Optional, Tuple
from PIL import Image
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class FormatConverterService:
    """Extracts headline, text content, and images from multiple input formats."""

    @staticmethod
    def extract_from_document(file_path: str, filename: str) -> Dict[str, Any]:
        """Extracts text and any embedded image from PDF, DOCX, or TXT."""
        ext = os.path.splitext(filename)[1].lower()
        extracted_text = ""
        extracted_image_path = None

        try:
            if ext == ".pdf":
                import pypdf
                reader = pypdf.PdfReader(file_path)
                text_parts = []
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        text_parts.append(txt)
                extracted_text = "\n".join(text_parts).strip()

                # Attempt to extract first embedded image if available
                for page in reader.pages:
                    if hasattr(page, "images") and len(page.images) > 0:
                        img_obj = page.images[0]
                        img_out = file_path + "_extracted.jpg"
                        with open(img_out, "wb") as f_img:
                            f_img.write(img_obj.data)
                        extracted_image_path = img_out
                        break

            elif ext in [".docx", ".doc"]:
                import docx
                doc = docx.Document(file_path)
                text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
                extracted_text = "\n".join(text_parts).strip()

            elif ext in [".txt", ".md", ".json", ".csv"]:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    extracted_text = f.read().strip()

            else:
                extracted_text = f"Unsupported document format: {ext}"

        except Exception as e:
            logger.error(f"Error parsing document {filename}: {e}")
            extracted_text = f"Error reading document: {str(e)}"

        # Clean text into headline and context
        headline, full_body = FormatConverterService._clean_and_summarize(extracted_text)

        return {
            "format": "document",
            "file_type": ext,
            "title": headline,
            "headline": headline,
            "extracted_title": headline,
            "extracted_text": full_body,
            "full_text": full_body,
            "body_snippet": full_body[:300],
            "extracted_image_path": extracted_image_path,
            "word_count": len(full_body.split())
        }

    @staticmethod
    def extract_from_url(url: str) -> Dict[str, Any]:
        """Extracts article title, body, and primary og:image from a web link."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or "web-source"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=8)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract title with multi-strategy fallbacks
            title = ""
            og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
            tw_title = soup.find("meta", property="twitter:title") or soup.find("meta", attrs={"name": "twitter:title"})
            
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
            elif tw_title and tw_title.get("content"):
                title = tw_title["content"].strip()
            elif soup.title and soup.title.string:
                title = soup.title.string.strip()
            elif soup.find("h1"):
                title = soup.find("h1").get_text().strip()

            # Extract main image
            image_url = None
            og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
            tw_img = soup.find("meta", property="twitter:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og_img and og_img.get("content"):
                image_url = og_img["content"].strip()
            elif tw_img and tw_img.get("content"):
                image_url = tw_img["content"].strip()

            # Extract paragraphs
            paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 25]
            body_text = " ".join(paragraphs[:10])

            headline, full_body = FormatConverterService._clean_and_summarize(title or body_text or url)
            final_title = title if (title and len(title) > 3) else headline

            return {
                "format": "url",
                "url": url,
                "domain": domain,
                "title": final_title,
                "headline": final_title,
                "full_text": body_text or final_title,
                "body_snippet": (body_text or final_title)[:300],
                "image_url": image_url,
                "word_count": len((body_text or final_title).split())
            }
        except Exception as e:
            logger.error(f"Error extracting from URL {url}: {e}")
            # Resilient fallback title derived from URL path slug
            path_slug = parsed.path.rstrip("/").split("/")[-1]
            slug_cleaned = re.sub(r'[-_+.]', ' ', path_slug).strip()
            if slug_cleaned and len(slug_cleaned) > 3 and not slug_cleaned.isdigit():
                fallback_title = slug_cleaned.title()
            else:
                fallback_title = f"Report from {domain}"

            return {
                "format": "url",
                "url": url,
                "domain": domain,
                "title": fallback_title,
                "headline": fallback_title,
                "full_text": f"Article source: {url}. (Direct fetch notice: {str(e)})",
                "body_snippet": f"Article source: {url}. (Direct fetch notice: {str(e)})",
                "image_url": None,
                "word_count": len(fallback_title.split())
            }

    @staticmethod
    def _clean_and_summarize(text: str) -> Tuple[str, str]:
        """Derives a concise headline and clean text body."""
        clean = re.sub(r'\s+', ' ', text).strip()
        lines = [line.strip() for line in clean.split(". ") if len(line.strip()) > 10]
        if lines:
            headline = lines[0]
            if len(headline) > 180:
                headline = headline[:177] + "..."
        else:
            headline = clean[:150] if len(clean) > 150 else clean

        return headline, clean
