import json
import os

class CreditManager:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(".utim_tmp", "utim_state.json")
        self.config_path = config_path
        self.costs = {
            "gemini": 1,      # 1 credit per 1000 tokens
            "claude": 15,     # 15 credits per 1000 tokens (more expensive)
            "codex": 10       # 10 credits per 1000 tokens
        }
        self.state = self._load_state()

    def _load_state(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                return json.load(f)
        return {"credits": 0}  # Start with 0 free credits

    def save_state(self):
        dir_name = os.path.dirname(self.config_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.state, f, indent=4)

    def has_credits(self, agent_name, estimate_tokens=1000):
        cost = (estimate_tokens / 1000) * self.costs.get(agent_name, 1)
        return self.state["credits"] >= cost

    def deduct_credits(self, agent_name, actual_tokens):
        cost = (actual_tokens / 1000) * self.costs.get(agent_name, 1)
        self.state["credits"] -= cost
        self.save_state()
        return cost

    def get_balance(self):
        return self.state["credits"]
