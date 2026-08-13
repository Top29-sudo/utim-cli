"""
UTIM Server Model Registry Maintenance Agent
----------------------------------------------
Dedicated autonomous server agent powered by 'poolside/laguna-s-2.1:free'.
Wakes up every 24 hours to sync live free models from OpenRouter, auto-register newly
released free models, and strip free tags from discontinued ones.
"""

import asyncio
import logging
import datetime
import requests
import json
import os
from typing import Dict, Any, List

from .db import SessionLocal, ModelDB
from .models import MODEL_REGISTRY, ModelEntry, sync_models_to_db

logger = logging.getLogger("utim.model_agent")

MODEL_AGENT_LLM = "poolside/laguna-s-2.1:free"


class ModelRegistryAgent:
    """Dedicated 24-hour server agent for model registry synchronization and maintenance."""

    def __init__(self, interval_hours: float = 24.0):
        self.interval_seconds = interval_hours * 3600.0
        self.agent_model = MODEL_AGENT_LLM
        self._task: asyncio.Task | None = None
        self._running = False

    @staticmethod
    def run_model_registry_maintenance() -> Dict[str, Any]:
        """
        Execute full 24-hour model registry audit:
        1. Fetch live models from OpenRouter.
        2. Detect newly added free models and register them.
        3. Detect discontinued free models, remove `:free` tags, and update cost tiers.
        4. Sync changes to SQLite/Postgres DB and update models.txt.
        """
        logger.info(f"ModelRegistryAgent waking up (powered by {MODEL_AGENT_LLM})...")
        report = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "agent_model": MODEL_AGENT_LLM,
            "new_free_models_added": [],
            "discontinued_free_models_updated": [],
            "total_active_models": 0,
            "total_free_models": 0,
            "status": "success"
        }

        try:
            resp = requests.get("https://openrouter.ai/api/v1/models", timeout=8)
            if resp.status_code != 200:
                report["status"] = f"Failed fetching OpenRouter models HTTP {resp.status_code}"
                return report

            items = resp.json().get("data", []) if isinstance(resp.json(), dict) else resp.json()
            
            # Save models.txt snapshot
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            models_txt_path = os.path.join(root_dir, "models.txt")
            with open(models_txt_path, "w", encoding="utf-8") as f:
                json.dump({"data": items}, f, indent=2)

            live_free_ids = set()
            live_model_dict = {}

            for m in items:
                mid = m.get("id")
                if not mid or mid.startswith("~"):
                    continue

                pricing = m.get("pricing", {}) or {}
                try:
                    p_in = float(pricing.get("prompt", 0)) * 1_000_000
                    p_out = float(pricing.get("completion", 0)) * 1_000_000
                except Exception:
                    p_in, p_out = 1.0, 2.0

                is_free_live = mid.endswith(":free") or (p_in == 0 and p_out == 0)
                live_model_dict[mid] = {
                    "raw": m,
                    "p_in": p_in,
                    "p_out": p_out,
                    "is_free": is_free_live
                }

                if is_free_live:
                    live_free_ids.add(mid)

            from .routes.rewards_routes import AUTHORITATIVE_66_MODEL_IDS
            approved_main_ids = set(AUTHORITATIVE_66_MODEL_IDS)

            db = SessionLocal()
            try:
                # 1. Update existing entries & detect discontinued free models
                for mid, entry in list(MODEL_REGISTRY.items()):
                    # Respect utimmodel.txt pricing & tags for the 66 authoritative models
                    if mid in approved_main_ids:
                        continue

                    if mid in live_model_dict:
                        live_info = live_model_dict[mid]
                        entry.cost_input_per_1k = live_info["p_in"] / 1000.0
                        entry.cost_output_per_1k = live_info["p_out"] / 1000.0

                        if live_info["is_free"]:
                            if "free" not in entry.tags:
                                entry.tags = list(set(entry.tags + ["free"]))
                        else:
                            # Model exists on OpenRouter but is no longer free
                            if "free" in entry.tags:
                                entry.tags = [t for t in entry.tags if t != "free"]
                                if "premium" not in entry.tags:
                                    entry.tags.append("premium")
                                report["discontinued_free_models_updated"].append(mid)
                                logger.info(f"Discontinued free tag stripped (repriced): {mid}")
                    else:
                        # Model has been completely removed from OpenRouter API —
                        # it no longer exists at all, so strip any free tag.
                        if "free" in entry.tags:
                            entry.tags = [t for t in entry.tags if t != "free"]
                            if "premium" not in entry.tags:
                                entry.tags.append("premium")
                            report["discontinued_free_models_updated"].append(mid)
                            logger.info(f"Discontinued free tag stripped (removed from API): {mid}")

                # 2. Detect & Register newly available free models from OpenRouter
                # Only register models that support TEXT output (not image-gen, audio, etc.)
                NON_TEXT_KEYWORDS = ["image", "imagine", "dall-e", "flux", "stable-diffusion",
                                     "midjourney", "audio", "speech", "tts", "whisper", "stt",
                                     "embedding", "moderation", "rerank"]

                for free_mid in live_free_ids:
                    if free_mid not in MODEL_REGISTRY:
                        m_data = live_model_dict[free_mid]["raw"]

                        # Filter out non-text-output models by id keywords
                        mid_lower = free_mid.lower()
                        if any(kw in mid_lower for kw in NON_TEXT_KEYWORDS):
                            logger.debug(f"Skipping non-text model: {free_mid}")
                            continue

                        # Filter out models that declare non-text modalities
                        architecture = m_data.get("architecture", {}) or {}
                        output_modalities = architecture.get("output_modalities", architecture.get("output", []))
                        if isinstance(output_modalities, list) and output_modalities:
                            # Only accept if 'text' is in output modalities
                            if "text" not in [o.lower() for o in output_modalities]:
                                logger.debug(f"Skipping non-text-output modality model: {free_mid} outputs={output_modalities}")
                                continue

                        desc = m_data.get("name") or free_mid
                        ctx = m_data.get("context_length", 128000)

                        new_entry = ModelEntry(
                            model_id=free_mid,
                            provider="openrouter",
                            cost_input_per_1k=0.00002,
                            cost_output_per_1k=0.00003,
                            context_window=ctx,
                            capabilities=["chat"],
                            tags=["free"],
                            description=desc
                        )
                        MODEL_REGISTRY[free_mid] = new_entry
                        report["new_free_models_added"].append(free_mid)
                        logger.info(f"New free model registered: {free_mid}")

                # 3. Sync to ModelDB SQLite/Postgres table
                sync_models_to_db(db)

                report["total_active_models"] = len(MODEL_REGISTRY)
                # Count only models confirmed free by the live OpenRouter API response
                report["total_free_models"] = len([mid for mid in MODEL_REGISTRY if mid in live_free_ids])

            except Exception as e:
                logger.error(f"Error during registry sync: {e}")
                db.rollback()
            finally:
                db.close()

        except Exception as e:
            logger.error(f"ModelRegistryAgent 24h run failed: {e}")
            report["status"] = f"Error: {e}"

        logger.info(f"ModelRegistryAgent 24h cycle finished: {report}")
        return report

    async def _background_loop(self):
        self._running = True
        while self._running:
            try:
                await asyncio.to_thread(ModelRegistryAgent.run_model_registry_maintenance)
            except Exception as e:
                logger.error(f"ModelRegistryAgent background loop error: {e}")
            
            await asyncio.sleep(self.interval_seconds)

    def start(self):
        """Start the 24-hour Model Registry Maintenance Agent."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._background_loop())
            logger.info(f"ModelRegistryAgent (24h loop) started using model {MODEL_AGENT_LLM}.")

    def stop(self):
        """Stop the agent."""
        self._running = False
        if self._task:
            self._task.cancel()
            logger.info("ModelRegistryAgent stopped.")


# Global singleton agent instance
model_agent = ModelRegistryAgent(interval_hours=24.0)
