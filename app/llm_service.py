"""
LLM extraction service.

Uses NVIDIA NIM's free hosted API (OpenAI-compatible endpoint) so you
can run this project with zero cost. Get a free key (no card required)
at build.nvidia.com -> API Keys -> Generate.

This is the piece worth explaining in interviews: LLMs don't reliably
return valid JSON every time. This module:
  1. Prompts the model to return ONLY JSON matching our schema
  2. Parses + validates the response with Pydantic
  3. Retries (up to MAX_RETRIES times) if parsing/validation fails
  4. Gives up gracefully and flags the record for manual review,
     instead of crashing the whole pipeline on one bad response
"""

import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from app.models import ExtractedInsight


load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
)

MODEL = "meta/llama-3.1-70b-instruct"
MAX_RETRIES = 3

EXTRACTION_PROMPT = """You are a customer feedback analyst. Given a piece of customer
feedback, extract structured insight from it.

Return ONLY a JSON object with this exact shape, no other text, no markdown fences,
no explanation before or after:
{{
  "sentiment": "positive" | "negative" | "neutral" | "mixed",
  "category": "bug" | "feature_request" | "praise" | "support_experience" | "billing" | "other",
  "issue_summary": "one line summary, max 200 chars",
  "urgency": "low" | "medium" | "high"
}}

Feedback text:
\"\"\"{text}\"\"\"
"""


def extract_insight(text: str) -> ExtractedInsight | None:
    """
    Calls the LLM and returns a validated ExtractedInsight, or None
    if it fails validation after MAX_RETRIES attempts.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=300,
                temperature=0.2,
                messages=[
                    {"role": "user", "content": EXTRACTION_PROMPT.format(text=text)}
                ],
            )
            raw_text = response.choices[0].message.content.strip()

            # Models sometimes wrap JSON in markdown fences despite instructions
            raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            parsed = json.loads(raw_text)
            insight = ExtractedInsight(**parsed)
            return insight

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            print(f"[attempt {attempt}] validation failed: {e}")
            time.sleep(1 * attempt)
            continue
        except Exception as e:
            last_error = e
            print(f"[attempt {attempt}] API call failed: {e}")
            time.sleep(1 * attempt)
            continue

    print(f"Giving up after {MAX_RETRIES} attempts. Last error: {last_error}")
    return None
