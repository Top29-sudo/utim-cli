import os
import logging
import datetime
import time
import threading
import requests

logger = logging.getLogger("utim.exchange_rate")

class ExchangeRateStore:
    # Default fallback rate
    USD_TO_INR = 95.70

    @classmethod
    def fetch_live_rate(cls) -> float:
        # 1. Try ER-API (reliable, free, updated daily)
        try:
            response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
            if response.status_code == 200:
                data = response.json()
                rate = data.get("rates", {}).get("INR")
                if rate:
                    cls.USD_TO_INR = float(rate)
                    logger.info(f"Successfully fetched live exchange rate (er-api): {cls.USD_TO_INR}")
                    return cls.USD_TO_INR
        except Exception as e:
            logger.warning(f"Failed to fetch live exchange rate from ER-API: {e}")

        # 2. Try ExchangeRate-API V4 (reliable, free fallback)
        try:
            response = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
            if response.status_code == 200:
                data = response.json()
                rate = data.get("rates", {}).get("INR")
                if rate:
                    cls.USD_TO_INR = float(rate)
                    logger.info(f"Successfully fetched live exchange rate (exchangerate-api): {cls.USD_TO_INR}")
                    return cls.USD_TO_INR
        except Exception as e:
            logger.warning(f"Failed to fetch live exchange rate from ExchangeRate-API: {e}")

        # 3. Try Frankfurter API
        try:
            response = requests.get("https://api.frankfurter.app/latest?from=USD&to=INR", timeout=5)
            if response.status_code == 200:
                data = response.json()
                rate = data.get("rates", {}).get("INR")
                if rate:
                    cls.USD_TO_INR = float(rate)
                    logger.info(f"Successfully fetched live exchange rate (frankfurter): {cls.USD_TO_INR}")
                    return cls.USD_TO_INR
        except Exception as e:
            logger.warning(f"Failed to fetch live exchange rate from Frankfurter: {e}")

        logger.error(f"All live exchange rate APIs failed. Using fallback rate: {cls.USD_TO_INR}")
        return cls.USD_TO_INR

    @classmethod
    def get_rate(cls) -> float:
        env_rate = os.environ.get("USD_TO_INR_RATE")
        if env_rate:
            try:
                return float(env_rate)
            except ValueError:
                pass
        return cls.USD_TO_INR


def start_exchange_rate_scheduler():
    def scheduler_loop():
        # Fetch once on startup
        ExchangeRateStore.fetch_live_rate()

        last_fetched_date = datetime.date.today()

        while True:
            try:
                now = datetime.datetime.now()
                # Check if it's 12 PM (noon) and we haven't fetched today yet
                if now.hour == 12 and now.date() != last_fetched_date:
                    ExchangeRateStore.fetch_live_rate()
                    last_fetched_date = now.date()
            except Exception as e:
                logger.error(f"Error in exchange rate scheduler loop: {e}")
            
            # Sleep for 60 seconds before checking again
            time.sleep(60)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
