import os
import re
import asyncio
import json
import random
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from pydantic import BaseModel, Field

from overlay.memory import MemoryStore

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Structured Output Schemas
class JudgeResponse(BaseModel):
    verdict: str = Field(description="Must be either 'allow' or 'block'")
    reason: str = Field(description="One concise sentence explaining the verdict")


class PleaResponse(BaseModel):
    grant_minutes: int = Field(description="Number of minutes granted between 0 and 10. 0 means denied.")
    reason: str = Field(description="One concise sentence explaining why the plea was granted or denied")


class GeminiPetAI:
    """
    AI Controller for Tab Pet using the official modern google-genai SDK.
    - Zero key printing or logging.
    - Automatic model discovery (finds current Flash model if MODEL_NAME unset).
    - 2.0 second hard timeout with instant local fallback.
    - Structured output for judging and plea bargaining.
    """

    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store
        self.client = None
        self.model_name = ""
        self.api_key = ""
        self.is_offline = True
        self.local_only = False
        
        # In-memory LRU cache for judge verdicts: (url_path, title, goal) -> (verdict, reason)
        self.judge_cache: Dict[Tuple[str, str, str], Tuple[str, str]] = {}

        self._init_env_and_client()

    def _init_env_and_client(self) -> None:
        """Reads .env safely without logging or printing secrets."""
        if not ENV_PATH.exists():
            try:
                ENV_PATH.write_text(
                    "GOOGLE_API_KEY=\nMODEL_NAME=\n",
                    encoding="utf-8"
                )
            except Exception:
                pass

        api_key = ""
        model_name = ""
        if ENV_PATH.exists():
            try:
                content = ENV_PATH.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("GOOGLE_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                    elif line.startswith("MODEL_NAME="):
                        model_name = line.split("=", 1)[1].strip()
            except Exception:
                pass

        self.api_key = api_key
        self.model_name = model_name

        if not api_key:
            print("[TabPet AI] Notice: No GOOGLE_API_KEY in .env. Running in offline fallback mode.")
            self.is_offline = True
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
            self.is_offline = False

            # Auto-discover Flash model if not configured
            if not self.model_name:
                self._discover_and_save_model()
            else:
                print(f"[TabPet AI] Using configured model: {self.model_name}")
        except Exception as e:
            print(f"[TabPet AI] Warning: Could not initialize Gemini client: {e}. Using offline fallback.")
            self.is_offline = True

    def _discover_and_save_model(self) -> None:
        """Discovers current Flash model using key and updates MODEL_NAME in .env."""
        try:
            models_pager = self.client.models.list()
            candidates = []
            for m in models_pager:
                name = m.name or ""
                # Strip models/ prefix
                clean_name = name.replace("models/", "")
                if "flash" in clean_name.lower() and not "embed" in clean_name.lower():
                    candidates.append(clean_name)

            # Prioritize latest flash models
            selected = "gemini-2.5-flash"
            for prio in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                if prio in candidates:
                    selected = prio
                    break
            else:
                if candidates:
                    selected = candidates[0]

            self.model_name = selected
            print(f"[TabPet AI] Discovered Flash model: {self.model_name}")

            # Write model name back to .env without exposing or altering GOOGLE_API_KEY
            if ENV_PATH.exists():
                lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
                new_lines = []
                model_set = False
                for line in lines:
                    if line.strip().startswith("MODEL_NAME="):
                        new_lines.append(f"MODEL_NAME={selected}")
                        model_set = True
                    else:
                        new_lines.append(line)
                if not model_set:
                    new_lines.append(f"MODEL_NAME={selected}")
                ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        except Exception as e:
            self.model_name = "gemini-2.5-flash"
            print(f"[TabPet AI] Model discovery fallback to {self.model_name}: {e}")

    # -------------------------------------------------------------
    # 1. Smart Judge (Mixed list: YouTube, Reddit, etc.)
    # -------------------------------------------------------------
    async def judge_tab(self, url: str, title: str, goal: str) -> Dict[str, Any]:
        """
        Evaluates whether a page on a mixed domain is helpful for user's focus goal.
        - Privacy: Only url path and title are processed.
        - Max 2.0s execution time with hard timeout.
        - Cache: (url_path, title, goal)
        - Fallback: 'block' with offline indicator.
        """
        # Clean URL to pathname only (zero query params / tokens)
        clean_url = url.split("?")[0].split("#")[0]
        cache_key = (clean_url, title[:80], (goal or "").strip().lower())

        if cache_key in self.judge_cache:
            verdict, reason = self.judge_cache[cache_key]
            return {"verdict": verdict, "reason": reason, "offline": False, "cached": True}

        if self.local_only or self.is_offline or not self.client:
            return {
                "verdict": "block",
                "reason": "Restricted during focus session (offline mode).",
                "offline": True
            }

        # Context from memory
        recent_events = self.memory.get_recent_events(5)
        history_summary = "; ".join(
            [f"{e.get('domain')} ({e.get('verdict')})" for e in recent_events]
        ) or "None"

        prompt = (
            f"You are Mochi, a strict but fair productivity companion pet.\n"
            f"User's Current Goal: '{goal or 'General productive work'}'\n"
            f"Page Visited: URL: '{clean_url}', Title: '{title}'\n"
            f"Recent history: {history_summary}\n\n"
            f"Decide whether this page is directly relevant to their goal, or a distracting rabbit hole.\n"
            f"Rules:\n"
            f"- If the page directly teaches, solves, or aids the goal: verdict='allow'.\n"
            f"- If it is entertainment, clickbait, gaming, or irrelevant: verdict='block'.\n"
            f"- Provide a friendly, concise 1-sentence reason (under 16 words)."
        )

        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=JudgeResponse,
            temperature=0.2,
        )

        async def _call_gemini():
            # Retry once on malformed JSON or transient failure
            for attempt in range(2):
                try:
                    resp = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name or "gemini-2.5-flash",
                        contents=prompt,
                        config=config
                    )
                    text = resp.text.strip()
                    data = json.loads(text)
                    verdict = data.get("verdict", "block").lower()
                    if verdict not in ["allow", "block"]:
                        verdict = "block"
                    reason = data.get("reason", "Pet evaluated this tab.")
                    return verdict, reason
                except Exception:
                    if attempt == 1:
                        raise

        try:
            # Hard 2.0-second timeout guarantee
            verdict, reason = await asyncio.wait_for(_call_gemini(), timeout=2.0)
            self.judge_cache[cache_key] = (verdict, reason)
            return {"verdict": verdict, "reason": reason, "offline": False}
        except asyncio.TimeoutError:
            print("[TabPet AI] Judge call timed out (> 2.0s). Using offline fallback.")
            return {
                "verdict": "block",
                "reason": "AI timeout: blocked by rules-based fallback.",
                "offline": True
            }
        except Exception as e:
            print(f"[TabPet AI] Judge call failed: {e}. Using offline fallback.")
            return {
                "verdict": "block",
                "reason": "AI error: blocked by rules-based fallback.",
                "offline": True
            }

    # -------------------------------------------------------------
    # 2. Roast Speech Bubble
    # -------------------------------------------------------------
    async def generate_roast(
        self,
        tab_title: str,
        blocks_today: int,
        streak_days: int,
        goal: str
    ) -> str:
        """
        Generates a playful line (max 15 words) while pet walks to stomp tab.
        Strict Safety: No jokes about bodies, appearance, identity, or slurs.
        Fallback: Canned playful lines.
        """
        canned_roasts = [
            f"Back to work! That tab wasn't helping with your goal.",
            f"Caught red-pawed! Time to get back on track.",
            f"Mochi says: no distractions allowed today!",
            f"Block #{blocks_today}! Protect that {streak_days}-day streak.",
            f"Nice try, but your goal needs your full attention!",
            f"Nope! Stay focused on {goal or 'your tasks'}.",
            f"Distraction stomped! Your future self will thank you."
        ]

        if self.local_only or self.is_offline or not self.client:
            return random.choice(canned_roasts)

        prompt = (
            f"You are Mochi the tab pet. You just stomped and closed a distracting tab.\n"
            f"Tab Title: '{tab_title}'\n"
            f"User Goal: '{goal or 'Focus'}'\n"
            f"Blocks today: {blocks_today}, Streak: {streak_days} days.\n\n"
            f"Write a single playful, sassy roast line (MAXIMUM 14 WORDS).\n"
            f"STRICT SAFETY RULES: Lighthearted productivity banter only. "
            f"NEVER make jokes about bodies, appearance, race, gender, identity, or use any insults/slurs."
        )

        async def _call_gemini():
            resp = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name or "gemini-2.5-flash",
                contents=prompt
            )
            raw = resp.text.strip().replace('"', '').replace('\n', ' ')
            words = raw.split()
            if len(words) > 15:
                raw = " ".join(words[:14]) + "!"
            return raw

        try:
            # 2.0-second timeout guarantee
            roast = await asyncio.wait_for(_call_gemini(), timeout=2.0)
            return roast if roast else random.choice(canned_roasts)
        except Exception:
            return random.choice(canned_roasts)

    # -------------------------------------------------------------
    # 3. Plea Bargain & Trust Scoring
    # -------------------------------------------------------------
    async def judge_plea(
        self,
        plea_text: str,
        url: str,
        title: str,
        goal: str
    ) -> Dict[str, Any]:
        """
        Weighs user plea against title, goal, and past history.
        Returns {grant_minutes: 0-10, reason: str, trust_score: int, offline: bool}.
        """
        clean_url = url.split("?")[0].split("#")[0]
        current_trust = self.memory.get_trust_score()

        if self.local_only or self.is_offline or not self.client:
            # Offline fallback plea judgment: simple keyword heuristic
            if "quick" in plea_text.lower() or "reference" in plea_text.lower() or "need" in plea_text.lower():
                minutes = 3
                new_trust = self.memory.update_trust(1)
                reason = "Offline pass: granted 3 quick minutes."
            else:
                minutes = 0
                new_trust = self.memory.update_trust(-2)
                reason = "Plea denied (offline mode)."

            self.memory.record_event(
                domain=clean_url.split("/")[2] if "//" in clean_url else clean_url,
                title=title,
                verdict="plea_granted" if minutes > 0 else "plea_denied",
                plea=plea_text,
                grant_minutes=minutes,
                reason=reason
            )
            return {
                "grant_minutes": minutes,
                "reason": reason,
                "trust_score": new_trust,
                "offline": True
            }

        past_events = self.memory.get_recent_events(5)
        past_pleas = [
            f"Plea: '{e.get('plea')}' -> Granted: {e.get('grant_minutes')}m"
            for e in past_events if e.get('plea')
        ]
        plea_history = "; ".join(past_pleas) or "No previous pleas."

        prompt = (
            f"You are Mochi, arbitrating a plea bargain for a blocked tab.\n"
            f"User Focus Goal: '{goal or 'General study/work'}'\n"
            f"Page Visited: URL: '{clean_url}', Title: '{title}'\n"
            f"User's Plea: '{plea_text}'\n"
            f"Current User Trust Score: {current_trust}/100\n"
            f"Plea History: {plea_history}\n\n"
            f"Decide whether to grant a temporary grace pass (1 to 10 minutes) or deny it (0 minutes).\n"
            f"Rules:\n"
            f"- If the plea gives a genuine, honest academic/work reason related to their goal: grant 3-7 minutes.\n"
            f"- If it's a weak excuse, pure entertainment, or dishonest: grant 0 minutes.\n"
            f"- Higher trust scores get more leniency; lower trust scores require stricter proof.\n"
            f"- Keep reason concise (under 16 words)."
        )

        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PleaResponse,
            temperature=0.3,
        )

        async def _call_gemini():
            for attempt in range(2):
                try:
                    resp = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name or "gemini-2.5-flash",
                        contents=prompt,
                        config=config
                    )
                    text = resp.text.strip()
                    data = json.loads(text)
                    minutes = max(0, min(10, int(data.get("grant_minutes", 0))))
                    reason = data.get("reason", "Pet evaluated your plea.")
                    return minutes, reason
                except Exception:
                    if attempt == 1:
                        raise

        try:
            minutes, reason = await asyncio.wait_for(_call_gemini(), timeout=2.0)
            # Update trust score based on plea result
            if minutes > 0:
                new_trust = self.memory.update_trust(2)
                verdict = "plea_granted"
            else:
                new_trust = self.memory.update_trust(-3)
                verdict = "plea_denied"

            domain = clean_url.split("/")[2] if "//" in clean_url else clean_url
            self.memory.record_event(
                domain=domain,
                title=title,
                verdict=verdict,
                plea=plea_text,
                grant_minutes=minutes,
                reason=reason
            )

            return {
                "grant_minutes": minutes,
                "reason": reason,
                "trust_score": new_trust,
                "offline": False
            }
        except Exception as e:
            print(f"[TabPet AI] Plea judgment error or timeout: {e}. Using offline fallback.")
            new_trust = self.memory.update_trust(-1)
            return {
                "grant_minutes": 0,
                "reason": "Plea evaluation timed out: denied by offline fallback.",
                "trust_score": new_trust,
                "offline": True
            }
