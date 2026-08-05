import logging
import datetime
import time
import threading
import requests
from utim_cli.server.models import MODEL_REGISTRY

logger = logging.getLogger("utim.pricing_updater")

def fetch_and_update_pricing() -> bool:
    logger.info("Fetching daily model list & pricing from OpenRouter...")
    try:
        # Fetch directly from OpenRouter
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=20)
        if response.status_code != 200:
            logger.error(f"Failed to fetch models from OpenRouter: HTTP {response.status_code}")
            return False
        
        data = response.json()
        models_data = data.get("data", []) if isinstance(data, dict) else data
        if not models_data:
            logger.error("No model data returned from OpenRouter")
            return False
        
        # Create map of OpenRouter models
        openrouter_models = {}
        for m in models_data:
            mid = m.get("id")
            if not mid:
                continue
                
            pricing = m.get("pricing", {})
            ctx = m.get("context_length", 128000)
            arch = m.get("architecture", {})
            in_mods = arch.get("input_modalities", [])
            has_vis = "image" in in_mods
            
            p_in = float(pricing.get("prompt", 0) or 0)
            p_out = float(pricing.get("completion", 0) or 0)
            is_free = mid.endswith(":free") or ":free" in mid or (p_in == 0 and p_out == 0)
            
            openrouter_models[mid] = {
                "pricing": pricing,
                "context_length": ctx,
                "is_free": is_free,
                "has_vision": has_vis,
                "prompt_usd": p_in,
                "completion_usd": p_out,
                "name": m.get("name") or mid.split("/")[-1].replace("-", " ").title(),
                "description": m.get("description", "")
            }
                
        # ── Update Database ModelDB ───────────────────────────────────
        try:
            from utim_cli.server.db import SessionLocal, ModelDB, init_db
            init_db()
            db = SessionLocal()
            try:
                # 1. Auto-add NEW FREE MODELS ONLY to ModelDB (paid models added manually by admin)
                added_count = 0
                for mid, m_info in openrouter_models.items():
                    existing = db.query(ModelDB).filter(ModelDB.model_id == mid).first()
                    caps = ["chat"]
                    if m_info["has_vision"]: caps.append("vision")

                    if not existing:
                        # ONLY auto-add FREE models
                        if m_info["is_free"]:
                            db_m = ModelDB(
                                model_id=mid,
                                name=m_info["name"],
                                provider="openrouter",
                                description=m_info["description"][:500] if m_info["description"] else None,
                                context_window=m_info["context_length"],
                                cost_input_per_1m=0.0,
                                cost_output_per_1m=0.0,
                                capabilities=caps,
                                tags=["free"],
                                is_free=True,
                                is_vision=m_info["has_vision"],
                                is_active=True,
                            )
                            db.add(db_m)
                            added_count += 1
                    else:
                        # Update context window & pricing for existing models in ModelDB
                        existing.is_free = m_info["is_free"]
                        existing.context_window = m_info["context_length"]
                        if not m_info["is_free"]:
                            existing.cost_input_per_1m = m_info["prompt_usd"] * 1_000_000 * 1.05
                            existing.cost_output_per_1m = m_info["completion_usd"] * 1_000_000 * 1.05

                # 2. Deactivate FREE MODELS ONLY in ModelDB that are no longer free or removed from OpenRouter
                deactivated_count = 0
                db_free_models = db.query(ModelDB).filter(ModelDB.is_free == True, ModelDB.is_active == True).all()
                for db_m in db_free_models:
                    # If this model is no longer in OpenRouter or no longer free
                    if db_m.model_id not in openrouter_models or not openrouter_models[db_m.model_id]["is_free"]:
                        db_m.is_active = False
                        db_m.is_free = False
                        deactivated_count += 1

                db.commit()
                logger.info(f"OpenRouter Daily Sync (Free Models Only): Added {added_count} new free models, deactivated {deactivated_count} stale/removed free models.")
            except Exception as dbe:
                db.rollback()
                logger.error(f"Error syncing ModelDB with OpenRouter: {dbe}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Database error during daily pricing update: {e}")

        # Also update in-memory MODEL_REGISTRY
        for model_id, entry in MODEL_REGISTRY.items():
            if model_id in openrouter_models:
                m_info = openrouter_models[model_id]
                entry.context_window = m_info["context_length"]
                if not m_info["is_free"]:
                    entry.cost_input_per_1k = m_info["prompt_usd"] * 1_000_000 * 1.05
                    entry.cost_output_per_1k = m_info["completion_usd"] * 1_000_000 * 1.05

        return True
    except Exception as e:
        logger.error(f"Error updating pricing from OpenRouter: {e}")
        return False

def start_pricing_scheduler():
    def scheduler_loop():
        # Fetch once on startup
        fetch_and_update_pricing()

        last_fetched_date = datetime.date.today()

        while True:
            try:
                now = datetime.datetime.now()
                # Check if it's 1 AM and we haven't fetched today yet
                if now.hour == 1 and now.date() != last_fetched_date:
                    fetch_and_update_pricing()
                    last_fetched_date = now.date()
            except Exception as e:
                logger.error(f"Error in pricing updater scheduler loop: {e}")
            
            # Sleep for 60 seconds before checking again
            time.sleep(60)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
