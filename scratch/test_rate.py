import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from utim_cli.server.exchange_rate import ExchangeRateStore

rate = ExchangeRateStore.get_rate()
print(f"EXCHANGE RATE: {rate}")
print(f"TYPE: {type(rate)}")
