import sys
import traceback
from utim_cli.utim import _dialog_model_main
from utim_cli.config import config

class DummyOrchestrator:
    def __init__(self):
        self.model_id = "cohere/north-mini-code:free"
        
    def _update_model_threshold(self, m):
        pass

if __name__ == "__main__":
    config.set("user_plan", "pro") # Test as paid plan
    orchestrator = DummyOrchestrator()
    try:
        _dialog_model_main(orchestrator, "main")
        print("Successfully ran dialog.")
    except Exception as e:
        print("EXCEPTION CAUGHT:")
        traceback.print_exc()
