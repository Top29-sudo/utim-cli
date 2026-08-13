"""
Model registry, routing logic, and cost estimation for the UTIM server.

Capability flags on each ModelEntry:
  capabilities list may include any of:
    "chat"             - general text chat / reasoning
    "code"             - coding-optimised
    "tool_use"         - supports function/tool calling
    "vision"           - image input (Image->Text)
    "image_generation" - image output (Text->Image, Image->Image, etc.)
    "reasoning"        - native reasoning / chain-of-thought

  For the /models/catalog endpoint:
    text_chat  -> "chat" in capabilities  (main agent + plan_project)
    vision     -> "vision" in capabilities (analyze_image)
    image_gen  -> "image_generation" in capabilities (image_gen tool)
"""
from __future__ import annotations
from typing import Optional

MODEL_ID = str

class ModelEntry:
    def __init__(
        self,
        model_id: MODEL_ID,
        provider: str,
        cost_input_per_1k: float,
        cost_output_per_1k: float,
        context_window: int,
        capabilities: list[str] | None = None,
        tags: list[str] | None = None,
        max_output_tokens: Optional[int] = None,
        description: str = "",
    ):
        self.model_id = model_id
        self.provider = provider
        self.cost_input_per_1k = cost_input_per_1k
        self.cost_output_per_1k = cost_output_per_1k
        self.context_window = context_window
        self.capabilities = capabilities or []
        self.tags = tags or []
        # Real max completion tokens as reported by the provider.
        # None means "unknown" - caller should use a safe default.
        self.max_output_tokens: Optional[int] = max_output_tokens
        self.description: str = description

    @property
    def text_chat(self) -> bool:
        """True if the model supports text->text (main agent / plan_project)."""
        return "chat" in self.capabilities

    @property
    def vision(self) -> bool:
        """True if the model supports image input (analyze_image)."""
        return "vision" in self.capabilities

    @property
    def image_gen(self) -> bool:
        """True if the model can output images (image_gen tool)."""
        return "image_generation" in self.capabilities

    def __repr__(self) -> str:
        return (
            f"ModelEntry({self.model_id}, provider={self.provider}, "
            f"cost_in={self.cost_input_per_1k}/1k, context={self.context_window}, "
            f"max_output={self.max_output_tokens})"
        )


# ─── Registered Models ────────────────────────────────────────────────────────
# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_max_output_tokens(model_id: MODEL_ID, fallback: int = 128_000) -> int:
    """Return the real max completion tokens for *model_id* from the registry.

    Falls back to *fallback* (default 128 000) when the model is not listed or
    its ``max_output_tokens`` was not set (i.e. is ``None``).
    """
    entry = MODEL_REGISTRY.get(model_id)
    if entry is not None and entry.max_output_tokens is not None and entry.max_output_tokens > 0:
        return entry.max_output_tokens
    if entry is not None and entry.context_window:
        return min(entry.context_window, 128_000)
    return fallback


MODEL_REGISTRY: dict[MODEL_ID, ModelEntry] = {
    "inclusionai/ling-3.0-flash:free": ModelEntry(

        model_id="inclusionai/ling-3.0-flash:free",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.000000,
        context_window=128_000,
        capabilities=["chat", "code", "tool_use"],
        tags=["free", "miniagent"],
        max_output_tokens=32_768,
        description="InclusionAI Ling 3.0 Flash — ultra-fast free model for lightweight miniagents (<100KB).",
    ),

    "nvidia/nemotron-3-ultra-550b-a55b:free": ModelEntry(
        model_id="nvidia/nemotron-3-ultra-550b-a55b:free",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.000000,
        context_window=262_144,
        capabilities=["chat", "code", "tool_use"],
        tags=["free", "miniagent"],
        max_output_tokens=65_536,
        description="Nvidia Nemotron 3 Ultra 550B — powerful free model for medium miniagents (100KB–150KB).",
    ),
    "deepseek/deepseek-v4-flash-0731": ModelEntry(
        model_id="deepseek/deepseek-v4-flash-0731",
        provider="openrouter",
        cost_input_per_1k=0.140,
        cost_output_per_1k=0.280,
        context_window=262_144,
        capabilities=["chat", "code", "tool_use", "reasoning"],
        tags=["miniagent", "premium"],
        max_output_tokens=65_536,
        description="DeepSeek V4 Flash — high-capacity reasoning model for miniagents (150KB–300KB).",
    ),
    "openai/gpt-5.6-luna-pro": ModelEntry(
        model_id="openai/gpt-5.6-luna-pro",
        provider="openrouter",
        cost_input_per_1k=2.500,
        cost_output_per_1k=10.000,
        context_window=1_000_000,
        capabilities=["chat", "code", "tool_use", "reasoning"],
        tags=["flagship", "miniagent", "premium"],
        max_output_tokens=128_000,
        description="OpenAI GPT-5.6 Luna Pro — top-tier flagship model for large miniagents (300KB+).",
    ),
    "nex-agi/nex-n2-pro:free": ModelEntry(
        model_id="nex-agi/nex-n2-pro:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=128_000,
        capabilities=["code", "chat", "tool_use"],
        tags=["free", "default"],
        max_output_tokens=262_144,
    ),
    "poolside/laguna-m.1:free": ModelEntry(
        model_id="poolside/laguna-m.1:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=100_000,
        capabilities=["code", "chat", "tool_use"],
        tags=["free"],
    ),
    "cohere/north-mini-code:free": ModelEntry(
        model_id="cohere/north-mini-code:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=128_000,
        capabilities=["code", "chat", "tool_use"],
        tags=["free"],
    ),
    "openrouter/free": ModelEntry(
        model_id="openrouter/free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=128_000,
        capabilities=["chat"],
        tags=["free"],
    ),
    "google/gemma-4-31b-it:free": ModelEntry(
        model_id="google/gemma-4-31b-it:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=128_000,
        capabilities=["chat"],
        tags=["free"],
    ),
    "google/gemma-4-26b-a4b-it:free": ModelEntry(
        model_id="google/gemma-4-26b-a4b-it:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=128_000,
        capabilities=["chat"],
        tags=["free"],
    ),
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": ModelEntry(
        model_id="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=128_000,
        capabilities=["chat"],
        tags=["free"],
    ),
    "nvidia/nemotron-nano-12b-v2-vl:free": ModelEntry(
        model_id="nvidia/nemotron-nano-12b-v2-vl:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=128_000,
        capabilities=["chat", "vision"],
        tags=["free"],
    ),
    "openai/gpt-oss-20b:free": ModelEntry(
        model_id="openai/gpt-oss-20b:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=128_000,
        capabilities=["chat"],
        tags=["free"],
    ),
    "poolside/laguna-xs.2:free": ModelEntry(
        model_id="poolside/laguna-xs.2:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=32_000,
        capabilities=["chat", "vision"],
        tags=["free"],
    ),
    "qwen/qwen3-next-80b-a3b-instruct": ModelEntry(
        model_id="qwen/qwen3-next-80b-a3b-instruct",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=80_000,
        capabilities=["chat"],
        tags=["free"],
    ),
    "xiaomi/mimo-v2-pro": ModelEntry(
        model_id="xiaomi/mimo-v2-pro",
        provider="openrouter",
        cost_input_per_1k=1.0,
        cost_output_per_1k=2.0,
        context_window=1_048_576,
        capabilities=["chat"],
        tags=["new"],
    ),
    "kwaipilot/kat-coder-air-v2.5": ModelEntry(
        model_id="kwaipilot/kat-coder-air-v2.5",
        provider="openrouter",
        cost_input_per_1k=0.00015,
        cost_output_per_1k=0.0006,
        context_window=256_000,
        capabilities=["code", "chat", "tool_use"],
        tags=["new"],
        max_output_tokens=80_000,
    ),
    "kwaipilot/kat-coder-pro-v2.5": ModelEntry(
        model_id="kwaipilot/kat-coder-pro-v2.5",
        provider="openrouter",
        cost_input_per_1k=0.00074,
        cost_output_per_1k=0.00296,
        context_window=256_000,
        capabilities=["code", "chat", "tool_use"],
        tags=["new"],
        max_output_tokens=80_000,
    ),
    "nex-agi/nex-n2-mini": ModelEntry(
        model_id="nex-agi/nex-n2-mini",
        provider="openrouter",
        cost_input_per_1k=0.000025,
        cost_output_per_1k=0.0001,
        context_window=262_144,
        capabilities=["code", "chat", "tool_use"],
        tags=["new"],
        max_output_tokens=262_144,
    ),
    "minimax/minimax-m2.7": ModelEntry(
        model_id="minimax/minimax-m2.7",
        provider="openrouter",
        cost_input_per_1k=1.02,
        cost_output_per_1k=2.04,
        context_window=204_800,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=131_072,
    ),
    "z-ai/glm-5.1": ModelEntry(
        model_id="z-ai/glm-5.1",
        provider="openrouter",
        cost_input_per_1k=1.02,
        cost_output_per_1k=2.04,
        context_window=202_752,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "anthropic/claude-sonnet-4.6": ModelEntry(
        model_id="anthropic/claude-sonnet-4.6",
        provider="openrouter",
        cost_input_per_1k=3.0,
        cost_output_per_1k=15.0,
        context_window=1_000_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "google/gemini-3.1-pro-preview": ModelEntry(
        model_id="google/gemini-3.1-pro-preview",
        provider="openrouter",
        cost_input_per_1k=1.25,
        cost_output_per_1k=5.0,
        context_window=1_000_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=65_536,
    ),
    "anthropic/claude-opus-4.6": ModelEntry(
        model_id="anthropic/claude-opus-4.6",
        provider="openrouter",
        cost_input_per_1k=15.0,
        cost_output_per_1k=75.0,
        context_window=1_000_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "openai/gpt-5.3-codex": ModelEntry(
        model_id="openai/gpt-5.3-codex",
        provider="openrouter",
        cost_input_per_1k=10.2,
        cost_output_per_1k=30.6,
        context_window=400_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "inclusionai/ling-2.6-flash": ModelEntry(
        model_id="inclusionai/ling-2.6-flash",
        provider="openrouter",
        cost_input_per_1k=0.0102,
        cost_output_per_1k=0.0306,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=32_768,
    ),
    "xiaomi/mimo-v2.5": ModelEntry(
        model_id="xiaomi/mimo-v2.5",
        provider="openrouter",
        cost_input_per_1k=0.1428,
        cost_output_per_1k=0.2856,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=131_072,
    ),
    "xiaomi/mimo-v2.5-pro": ModelEntry(
        model_id="xiaomi/mimo-v2.5-pro",
        provider="openrouter",
        cost_input_per_1k=1.02,
        cost_output_per_1k=3.06,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=131_072,
    ),
    "deepseek/deepseek-v4-flash": ModelEntry(
        model_id="deepseek/deepseek-v4-flash",
        provider="openrouter",
        cost_input_per_1k=0.0918,
        cost_output_per_1k=0.1836,
        context_window=64_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=384_000,
    ),
    "deepseek/deepseek-v4-pro": ModelEntry(
        model_id="deepseek/deepseek-v4-pro",
        provider="openrouter",
        cost_input_per_1k=0.4437,
        cost_output_per_1k=0.8874,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=384_000,
    ),
    "openai/gpt-5.5": ModelEntry(
        model_id="openai/gpt-5.5",
        provider="openrouter",
        cost_input_per_1k=5.1,
        cost_output_per_1k=30.6,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "inclusionai/ling-2.6-1t": ModelEntry(
        model_id="inclusionai/ling-2.6-1t",
        provider="openrouter",
        cost_input_per_1k=0.306,
        cost_output_per_1k=2.55,
        context_window=262_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=32_768,
    ),
    "moonshotai/kimi-k2.6": ModelEntry(
        model_id="moonshotai/kimi-k2.6",
        provider="openrouter",
        cost_input_per_1k=0.969,
        cost_output_per_1k=4.08,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=262_144,
    ),
    "google/gemini-3.1-pro-preview-customtools": ModelEntry(
        model_id="google/gemini-3.1-pro-preview-customtools",
        provider="openrouter",
        cost_input_per_1k=1.275,
        cost_output_per_1k=5.1,
        context_window=1_000_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=65_536,
    ),
    "openai/gpt-5.4": ModelEntry(
        model_id="openai/gpt-5.4",
        provider="openrouter",
        cost_input_per_1k=2.55,
        cost_output_per_1k=15.3,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "kwaipilot/kat-coder-pro-v2": ModelEntry(
        model_id="kwaipilot/kat-coder-pro-v2",
        provider="openrouter",
        cost_input_per_1k=0.306,
        cost_output_per_1k=1.224,
        context_window=256_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=80_000,
    ),
    "anthropic/claude-fable-5": ModelEntry(
        model_id="anthropic/claude-fable-5",
        provider="openrouter",
        cost_input_per_1k=10.2,
        cost_output_per_1k=51.0,
        context_window=200_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "nex-agi/nex-n2-pro": ModelEntry(
        model_id="nex-agi/nex-n2-pro",
        provider="openrouter",
        cost_input_per_1k=1.02,
        cost_output_per_1k=2.04,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=262_144,
    ),
    "minimax/minimax-m3": ModelEntry(
        model_id="minimax/minimax-m3",
        provider="openrouter",
        cost_input_per_1k=0.306,
        cost_output_per_1k=1.224,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=512_000,
    ),
    "moonshotai/kimi-k2.7-code": ModelEntry(
        model_id="moonshotai/kimi-k2.7-code",
        provider="openrouter",
        cost_input_per_1k=0.969,
        cost_output_per_1k=4.08,
        context_window=262_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=262_144,
    ),
    "deepseek/deepseek-r1": ModelEntry(
        model_id="deepseek/deepseek-r1",
        provider="openrouter",
        cost_input_per_1k=0.714,
        cost_output_per_1k=2.55,
        context_window=163_840,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=16_000,
    ),
    "x-ai/grok-4.3": ModelEntry(
        model_id="x-ai/grok-4.3",
        provider="openrouter",
        cost_input_per_1k=1.275,
        cost_output_per_1k=2.55,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=32_768,  # OpenRouter reports None; use safe default
    ),
    "google/gemini-3.5-flash": ModelEntry(
        model_id="google/gemini-3.5-flash",
        provider="openrouter",
        cost_input_per_1k=1.53,
        cost_output_per_1k=9.18,
        context_window=1_000_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=65_536,
    ),
    "google/gemini-3.6-flash": ModelEntry(
        model_id="google/gemini-3.6-flash",
        provider="openrouter",
        cost_input_per_1k=1.53,
        cost_output_per_1k=7.65,
        context_window=1_048_576,
        capabilities=["chat", "code", "tool_use"],
        tags=["premium"],
        max_output_tokens=65_536,
    ),
    "poolside/laguna-s-2.1:free": ModelEntry(
        model_id="poolside/laguna-s-2.1:free",
        provider="openrouter",
        cost_input_per_1k=0.0002,
        cost_output_per_1k=0.0003,
        context_window=1_048_576,
        capabilities=["code", "chat", "tool_use"],
        tags=["free"],
    ),
    "krea/krea-2-medium-turbo": ModelEntry(
        model_id="krea/krea-2-medium-turbo",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.015750,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "krea/krea-2-medium": ModelEntry(
        model_id="krea/krea-2-medium",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.031500,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "krea/krea-2-large": ModelEntry(
        model_id="krea/krea-2-large",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.063000,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "krea/krea-2": ModelEntry(
        model_id="krea/krea-2",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.031500,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "qwen/qwen3.8-max": ModelEntry(
        model_id="qwen/qwen3.8-max",
        provider="openrouter",
        cost_input_per_1k=1.475,
        cost_output_per_1k=4.425,
        context_window=1_000_000,
        capabilities=["chat", "code", "tool_use", "reasoning"],
        tags=["premium", "default"],
        max_output_tokens=65_536,
        description="Flagship Qwen3.8 Max — next-generation reasoning and agentic model with 1M context.",
    ),
    "qwen/qwen3.7-max": ModelEntry(
        model_id="qwen/qwen3.7-max",
        provider="openrouter",
        cost_input_per_1k=1.275,
        cost_output_per_1k=3.825,
        context_window=1_000_000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=65_536,
    ),
    "stepfun/step-3.7-flash": ModelEntry(
        model_id="stepfun/step-3.7-flash",
        provider="openrouter",
        cost_input_per_1k=0.204,
        cost_output_per_1k=1.173,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"],
        max_output_tokens=256_000,
    ),
    "black-forest-labs/flux.2-flex": ModelEntry(
        model_id="black-forest-labs/flux.2-flex",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.030600,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "black-forest-labs/flux.2-max": ModelEntry(
        model_id="black-forest-labs/flux.2-max",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.051000,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "black-forest-labs/flux.2-klein-4b": ModelEntry(
        model_id="black-forest-labs/flux.2-klein-4b",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.010200,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "sourceful/riverflow-v2-fast": ModelEntry(
        model_id="sourceful/riverflow-v2-fast",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.010200,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "sourceful/riverflow-v2-pro": ModelEntry(
        model_id="sourceful/riverflow-v2-pro",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.035700,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "sourceful/riverflow-v2.5-fast": ModelEntry(
        model_id="sourceful/riverflow-v2.5-fast",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.015300,
        context_window=1000,
        capabilities=["image"],
        tags=["premium"],
    ),
    "google/gemini-3-pro-image-preview": ModelEntry(
        model_id="google/gemini-3-pro-image-preview",
        provider="openrouter",
        cost_input_per_1k=0.002040,
        cost_output_per_1k=0.012240,
        context_window=128_000,
        capabilities=["chat", "image"],
        tags=["premium"],
    ),
    "google/gemini-3.1-flash-image-preview": ModelEntry(
        model_id="google/gemini-3.1-flash-image-preview",
        provider="openrouter",
        cost_input_per_1k=0.51,
        cost_output_per_1k=3.06,
        context_window=128_000,
        capabilities=["chat", "image"],
        tags=["premium"],
    ),
    "google/gemini-3.1-flash-image": ModelEntry(
        model_id="google/gemini-3.1-flash-image",
        provider="openrouter",
        cost_input_per_1k=0.000510,
        cost_output_per_1k=0.003060,
        context_window=128_000,
        capabilities=["chat", "image"],
        tags=["premium"],
    ),
    "openai/gpt-5-image-mini": ModelEntry(
        model_id="openai/gpt-5-image-mini",
        provider="openrouter",
        cost_input_per_1k=0.002550,
        cost_output_per_1k=0.002040,
        context_window=400_000,
        capabilities=["chat", "image"],
        tags=["premium"],
    ),
    "openai/gpt-image-2": ModelEntry(
        model_id="openai/gpt-image-2",
        provider="openrouter",
        cost_input_per_1k=0.020400,
        cost_output_per_1k=0.020400,
        context_window=128_000,
        capabilities=["chat", "image"],
        tags=["premium"],
    ),
    "anthropic/claude-sonnet-4.5": ModelEntry(
        model_id="anthropic/claude-sonnet-4.5",
        provider="openrouter",
        cost_input_per_1k=3.06,
        cost_output_per_1k=15.3,
        context_window=1000000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=64_000,
    ),
    "anthropic/claude-opus-4.5": ModelEntry(
        model_id="anthropic/claude-opus-4.5",
        provider="openrouter",
        cost_input_per_1k=5.1,
        cost_output_per_1k=25.5,
        context_window=200000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=64_000,
    ),
    "anthropic/claude-opus-4.7": ModelEntry(
        model_id="anthropic/claude-opus-4.7",
        provider="openrouter",
        cost_input_per_1k=5.1,
        cost_output_per_1k=25.5,
        context_window=1000000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "anthropic/claude-opus-4.8": ModelEntry(
        model_id="anthropic/claude-opus-4.8",
        provider="openrouter",
        cost_input_per_1k=5.1,
        cost_output_per_1k=25.5,
        context_window=1000000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "anthropic/claude-sonnet-5": ModelEntry(
        model_id="anthropic/claude-sonnet-5",
        provider="openrouter",
        cost_input_per_1k=2.04,
        cost_output_per_1k=10.2,
        context_window=1000000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "z-ai/glm-5-turbo": ModelEntry(
        model_id="z-ai/glm-5-turbo",
        provider="openrouter",
        cost_input_per_1k=1.224,
        cost_output_per_1k=4.08,
        context_window=262144,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=131_072,
    ),
    "z-ai/glm-4.7": ModelEntry(
        model_id="z-ai/glm-4.7",
        provider="openrouter",
        cost_input_per_1k=0.408,
        cost_output_per_1k=1.785,
        context_window=202752,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=131_072,
    ),
    "z-ai/glm-5": ModelEntry(
        model_id="z-ai/glm-5",
        provider="openrouter",
        cost_input_per_1k=0.612,
        cost_output_per_1k=1.9584,
        context_window=202752,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=202_752,
    ),
    "z-ai/glm-5.2": ModelEntry(
        model_id="z-ai/glm-5.2",
        provider="openrouter",
        cost_input_per_1k=0.9486,
        cost_output_per_1k=3.06,
        context_window=1048576,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=131_072,
    ),
    "qwen/qwen3.7-plus": ModelEntry(
        model_id="qwen/qwen3.7-plus",
        provider="openrouter",
        cost_input_per_1k=0.3264,
        cost_output_per_1k=1.3056,
        context_window=1000000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=65_536,
    ),
    "qwen/qwen3.6-plus": ModelEntry(
        model_id="qwen/qwen3.6-plus",
        provider="openrouter",
        cost_input_per_1k=0.3315,
        cost_output_per_1k=1.989,
        context_window=1000000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=65_536,
    ),
    "openai/gpt-5.4-mini": ModelEntry(
        model_id="openai/gpt-5.4-mini",
        provider="openrouter",
        cost_input_per_1k=0.765,
        cost_output_per_1k=4.59,
        context_window=400000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=128_000,
    ),
    "minimax/minimax-m2.5": ModelEntry(
        model_id="minimax/minimax-m2.5",
        provider="openrouter",
        cost_input_per_1k=0.1224,
        cost_output_per_1k=0.4896,
        context_window=204800,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=196_608,
    ),
    "x-ai/grok-4.20": ModelEntry(
        model_id="x-ai/grok-4.20",
        provider="openrouter",
        cost_input_per_1k=1.275,
        cost_output_per_1k=2.55,
        context_window=2000000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=32_768,  # OpenRouter reports None; use safe default
    ),
    "x-ai/grok-build-0.1": ModelEntry(
        model_id="x-ai/grok-build-0.1",
        provider="openrouter",
        cost_input_per_1k=1.02,
        cost_output_per_1k=2.04,
        context_window=256000,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=32_768,  # OpenRouter reports None; use safe default
    ),
    "moonshotai/kimi-k2.5": ModelEntry(
        model_id="moonshotai/kimi-k2.5",
        provider="openrouter",
        cost_input_per_1k=0.3825,
        cost_output_per_1k=2.0655,
        context_window=262144,
        capabilities=["chat", "code"],
        tags=["premium"],
        max_output_tokens=262_144,
    ),
    "recraft/recraft-v4.1": ModelEntry(
        model_id="recraft/recraft-v4.1",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.035700,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1-pro": ModelEntry(
        model_id="recraft/recraft-v4.1-pro",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.306000,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1-utility": ModelEntry(
        model_id="recraft/recraft-v4.1-utility",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.035700,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1-utility-pro": ModelEntry(
        model_id="recraft/recraft-v4.1-utility-pro",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.306000,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1-vector": ModelEntry(
        model_id="recraft/recraft-v4.1-vector",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.051000,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1-pro-vector": ModelEntry(
        model_id="recraft/recraft-v4.1-pro-vector",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.306000,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "x-ai/grok-imagine-image-quality": ModelEntry(
        model_id="x-ai/grok-imagine-image-quality",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.040800,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "microsoft/mai-image-2.5": ModelEntry(
        model_id="microsoft/mai-image-2.5",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.020400,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "sourceful/riverflow-v2.5-fast": ModelEntry(
        model_id="sourceful/riverflow-v2.5-fast",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.015300,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "sourceful/riverflow-v2.5-pro": ModelEntry(
        model_id="sourceful/riverflow-v2.5-pro",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.040800,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "sourceful/riverflow-v2.5-fast": ModelEntry(
        model_id="sourceful/riverflow-v2.5-fast",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.010200,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "sourceful/riverflow-v2-pro": ModelEntry(
        model_id="sourceful/riverflow-v2-pro",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.035700,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "sourceful/riverflow-v2-fast": ModelEntry(
        model_id="sourceful/riverflow-v2-fast",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.010200,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "black-forest-labs/flux.2-pro": ModelEntry(
        model_id="black-forest-labs/flux.2-pro",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.030600,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "black-forest-labs/flux.2-flex": ModelEntry(
        model_id="black-forest-labs/flux.2-flex",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.030600,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "black-forest-labs/flux.2-max": ModelEntry(
        model_id="black-forest-labs/flux.2-max",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.051000,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "black-forest-labs/flux.2-klein-4b": ModelEntry(
        model_id="black-forest-labs/flux.2-klein-4b",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.010200,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "bytedance-seed/seedream-4.5": ModelEntry(
        model_id="bytedance-seed/seedream-4.5",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.040800,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v3": ModelEntry(
        model_id="recraft/recraft-v3",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.040800,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4": ModelEntry(
        model_id="recraft/recraft-v4",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.040800,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4-pro": ModelEntry(
        model_id="recraft/recraft-v4-pro",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.255000,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4-vector": ModelEntry(
        model_id="recraft/recraft-v4-vector",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.081600,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4-pro-vector": ModelEntry(
        model_id="recraft/recraft-v4-pro-vector",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.306000,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1": ModelEntry(
        model_id="recraft/recraft-v4.1",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.035700,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1-pro": ModelEntry(
        model_id="recraft/recraft-v4.1-pro",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.214200,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1-vector": ModelEntry(
        model_id="recraft/recraft-v4.1-vector",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.081600,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "recraft/recraft-v4.1-pro-vector": ModelEntry(
        model_id="recraft/recraft-v4.1-pro-vector",
        provider="openrouter",
        cost_input_per_1k=0.000000,
        cost_output_per_1k=0.306000,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "google/gemini-3-pro-image": ModelEntry(
        model_id="google/gemini-3-pro-image",
        provider="openrouter",
        cost_input_per_1k=0.002040,
        cost_output_per_1k=0.012240,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "google/gemini-3.1-flash-image": ModelEntry(
        model_id="google/gemini-3.1-flash-image",
        provider="openrouter",
        cost_input_per_1k=0.000510,
        cost_output_per_1k=0.003060,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "openai/gpt-image-1": ModelEntry(
        model_id="openai/gpt-image-1",
        provider="openrouter",
        cost_input_per_1k=0.002040,
        cost_output_per_1k=0.002040,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "openai/gpt-image-1-mini": ModelEntry(
        model_id="openai/gpt-image-1-mini",
        provider="openrouter",
        cost_input_per_1k=0.000510,
        cost_output_per_1k=0.000510,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "openai/gpt-image-2": ModelEntry(
        model_id="openai/gpt-image-2",
        provider="openrouter",
        cost_input_per_1k=0.020400,
        cost_output_per_1k=0.020400,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "google/gemini-2.5-flash-image": ModelEntry(
        model_id="google/gemini-2.5-flash-image",
        provider="openrouter",
        cost_input_per_1k=0.000306,
        cost_output_per_1k=0.002550,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "openai/gpt-5-image": ModelEntry(
        model_id="openai/gpt-5-image",
        provider="openrouter",
        cost_input_per_1k=0.010200,
        cost_output_per_1k=0.010200,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "openai/gpt-5-image-mini": ModelEntry(
        model_id="openai/gpt-5-image-mini",
        provider="openrouter",
        cost_input_per_1k=0.002550,
        cost_output_per_1k=0.002040,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "google/gemini-3-pro-image-preview": ModelEntry(
        model_id="google/gemini-3-pro-image-preview",
        provider="openrouter",
        cost_input_per_1k=0.002040,
        cost_output_per_1k=0.012240,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
    "aion-labs/aion-3.0": ModelEntry(
        model_id="aion-labs/aion-3.0",
        provider="openrouter",
        cost_input_per_1k=1.0,
        cost_output_per_1k=2.0,
        context_window=200_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "aion-labs/aion-3.0-mini": ModelEntry(
        model_id="aion-labs/aion-3.0-mini",
        provider="openrouter",
        cost_input_per_1k=0.1,
        cost_output_per_1k=0.2,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "x-ai/grok-4.5": ModelEntry(
        model_id="x-ai/grok-4.5",
        provider="openrouter",
        cost_input_per_1k=2.0,
        cost_output_per_1k=10.0,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "openai/gpt-5.6-luna-pro": ModelEntry(
        model_id="openai/gpt-5.6-luna-pro",
        provider="openrouter",
        cost_input_per_1k=5.0,
        cost_output_per_1k=15.0,
        context_window=200_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "openai/gpt-5.6-luna": ModelEntry(
        model_id="openai/gpt-5.6-luna",
        provider="openrouter",
        cost_input_per_1k=2.5,
        cost_output_per_1k=7.5,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "openai/gpt-5.6-terra-pro": ModelEntry(
        model_id="openai/gpt-5.6-terra-pro",
        provider="openrouter",
        cost_input_per_1k=4.0,
        cost_output_per_1k=12.0,
        context_window=200_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "openai/gpt-5.6-terra": ModelEntry(
        model_id="openai/gpt-5.6-terra",
        provider="openrouter",
        cost_input_per_1k=2.0,
        cost_output_per_1k=6.0,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "openai/gpt-5.6-sol-pro": ModelEntry(
        model_id="openai/gpt-5.6-sol-pro",
        provider="openrouter",
        cost_input_per_1k=3.0,
        cost_output_per_1k=9.0,
        context_window=200_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "openai/gpt-5.6-sol": ModelEntry(
        model_id="openai/gpt-5.6-sol",
        provider="openrouter",
        cost_input_per_1k=1.5,
        cost_output_per_1k=4.5,
        context_window=128_000,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "thinkingmachines/inkling": ModelEntry(
        model_id="thinkingmachines/inkling",
        provider="openrouter",
        cost_input_per_1k=0.00105,
        cost_output_per_1k=0.0042525,
        context_window=1_048_576,
        capabilities=["chat", "code"],
        tags=["premium"],
    ),
    "moonshotai/kimi-k3": ModelEntry(
        model_id="moonshotai/kimi-k3",
        provider="openrouter",
        cost_input_per_1k=0.00315,
        cost_output_per_1k=0.01575,
        context_window=1_000_000,
        capabilities=["chat", "reasoning"],
        tags=["premium", "reasoning"],
    ),
    "meta/muse-spark-1.1": ModelEntry(
        model_id="meta/muse-spark-1.1",
        provider="openrouter",
        cost_input_per_1k=0.0013125,
        cost_output_per_1k=0.0044625,
        context_window=1_048_576,
        capabilities=["chat", "code", "multimodal"],
        tags=["premium", "multimodal"],
    ),
    "anthropic/claude-opus-5": ModelEntry(
        model_id="anthropic/claude-opus-5",
        provider="openrouter",
        cost_input_per_1k=0.00525,
        cost_output_per_1k=0.02625,
        context_window=1_000_000,
        capabilities=["chat", "code", "tool_use", "reasoning", "vision"],
        tags=["anthropic", "opus", "flagship", "premium"],
        max_output_tokens=128_000,
        description="Claude Opus 5 - Next-generation flagship reasoning & coding model by Anthropic",
    ),
    "thinkingmachines/inkling-small": ModelEntry(
        model_id="thinkingmachines/inkling-small",
        provider="openrouter",
        cost_input_per_1k=0.000525,
        cost_output_per_1k=0.00126,
        context_window=128_000,
        capabilities=["chat", "code", "tool_use"],
        tags=["fast", "lightweight", "premium"],
        max_output_tokens=16_384,
        description="Inkling Small - Efficient small-footprint model by Thinking Machines",
    ),
    "deepseek/deepseek-v4-flash-0731": ModelEntry(
        model_id="deepseek/deepseek-v4-flash-0731",
        provider="openrouter",
        cost_input_per_1k=0.0000945,
        cost_output_per_1k=0.000189,
        context_window=128_000,
        capabilities=["chat", "code", "tool_use", "reasoning"],
        tags=["deepseek", "fast", "coding", "premium"],
        max_output_tokens=16_384,
        description="DeepSeek V4 Flash 0731 - Ultra-fast MoE coding and reasoning model by DeepSeek",
    ),
}

def _load_all_openrouter_models():
    import json, os
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    models_txt_path = os.path.join(root_dir, "models.txt")
    if not os.path.exists(models_txt_path):
        models_txt_path = "models.txt"
        
    if os.path.exists(models_txt_path):
        try:
            with open(models_txt_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("data", []) if isinstance(data, dict) else data
            for m in items:
                mid = m.get("id")
                if not mid:
                    continue
                if mid.startswith("~"):
                    continue  # skip OpenRouter alias models
                
                arch = m.get("architecture", {}) or {}
                in_mods = arch.get("input_modalities", []) or []
                out_mods = arch.get("output_modalities", []) or []
                has_text_in = "text" in in_mods
                has_text_out = "text" in out_mods
                has_image_in = "image" in in_mods
                has_image_out = "image" in out_mods

                # Determine capabilities based on OpenRouter modality data
                caps = []
                if has_text_in and has_text_out:
                    caps.append("chat")
                if has_image_in and has_text_out:
                    caps.append("vision")
                if has_image_out:
                    caps.append("image_generation")

                # Detect reasoning support from supported_parameters
                supp = m.get("supported_parameters", []) or []
                if any(x in supp for x in ["reasoning", "reasoning_effort", "include_reasoning"]):
                    caps.append("reasoning")

                # If no text output at all and no image output, skip (e.g. audio-only)
                if not caps:
                    continue
                
                desc = m.get("name", "") or mid

                pricing = m.get("pricing", {}) or {}
                try:
                    p_in = float(pricing.get("prompt", 0)) * 1_000_000 * 1.02
                except Exception:
                    p_in = 1.0
                try:
                    p_out = float(pricing.get("completion", 0)) * 1_000_000 * 1.02
                except Exception:
                    p_out = 2.0
                ctx = m.get("context_length", 128_000)
                top_prov = m.get("top_provider") or {}
                limits = m.get("per_request_limits") or {}
                max_out = top_prov.get("max_completion_tokens") or limits.get("prompt_tokens")
                
                is_free = mid.endswith(":free") or ":free" in mid or (p_in == 0 and p_out == 0)
                tags = ["free"] if is_free else ["premium"]
                if has_image_out and not (has_text_in and has_text_out):
                    tags.append("image")
                if "reasoning" in caps:
                    tags.append("reasoning")
                if has_image_in:
                    if "vision" not in tags:
                        tags.append("vision")
                
                if mid in MODEL_REGISTRY:
                    # Update existing entry capabilities & max_output_tokens from live OpenRouter metadata
                    existing = MODEL_REGISTRY[mid]
                    existing.capabilities = caps
                    if not existing.description and desc:
                        existing.description = desc
                    if ctx and ctx > (existing.context_window or 0):
                        existing.context_window = ctx
                    if max_out and (existing.max_output_tokens is None or max_out > existing.max_output_tokens):
                        existing.max_output_tokens = max_out
                    # Merge tags
                    for t in tags:
                        if t not in existing.tags:
                            existing.tags = existing.tags + [t]
                else:
                    MODEL_REGISTRY[mid] = ModelEntry(
                        model_id=mid,
                        provider="openrouter",
                        cost_input_per_1k=p_in if not is_free else 0.0002,
                        cost_output_per_1k=p_out if not is_free else 0.0003,
                        context_window=ctx,
                        capabilities=caps,
                        tags=tags,
                        max_output_tokens=max_out,
                        description=desc,
                    )
        except Exception:
            pass

_load_all_openrouter_models()


def _load_utimmodel_txt():
    import os, re
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    utim_txt_path = os.path.join(root_dir, "utimmodel.txt")
    if not os.path.exists(utim_txt_path):
        utim_txt_path = "utimmodel.txt"
        
    if not os.path.exists(utim_txt_path):
        return

    try:
        with open(utim_txt_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        explicit_map = {
            'deepseek v4 flash 0731': 'deepseek/deepseek-v4-flash-0731',
            'north mini code': 'cohere/north-mini-code:free',
            'deepseek v4 flash': 'deepseek/deepseek-v4-flash',
            'ling 2.6 flash': 'inclusionai/ling-2.6-flash:free',
            'kat coder air v2.5': 'kwaipilot/kat-coder-air-v2.5',
            'muse spark 1.1': 'muses/muse-spark-1.1:free',
            'minimax m2.5': 'minimax/minimax-m2.5',
            'nex n2 mini': 'nex-agi/nex-n2-mini',
            'laguna s 2.1': 'poolside/laguna-s-2.1:free',
            'inkling': 'thinkingmachines/inkling-small:free',
            'mimo v2.5': 'xiaomi/mimo-v2.5',
            'deepseek v4 pro': 'deepseek/deepseek-v4-pro',
            'ling 2.6 1t': 'inclusionai/ling-2.6-1t',
            'kat coder pro v2': 'kwaipilot/kat-coder-pro-v2',
            'kat coder pro v2.5': 'kwaipilot/kat-coder-pro-v2.5',
            'minimax m3': 'minimax/minimax-m3',
            'kimi k2.5': 'moonshot/kimi-k2.5',
            'kimi k3': 'moonshot/kimi-k3',
            'gpt 5.4 mini': 'openai/gpt-5.4-mini',
            'qwen3.6 plus': 'qwen/qwen3.6-plus',
            'qwen3.7 plus': 'qwen/qwen3.7-plus',
            'step 3.7 flash': 'stepfun/step-3.7-flash',
            'glm 4.7': 'z-ai/glm-4.7',
            'glm 5': 'z-ai/glm-5',
            'glm 5.2': 'z-ai/glm-5.2',
            'claude sonnet 5': 'anthropic/claude-sonnet-5',
            'deepseek r1': 'deepseek/deepseek-r1',
            'gemini-3.1-pro-preview': 'google/gemini-3.1-pro-preview',
            'gemini 3.6 flash': 'google/gemini-3.6-flash',
            'minimax m2.7': 'minimax/minimax-m2.7',
            'kimi k2.6': 'moonshot/kimi-k2.6',
            'kimi k2.7 code': 'moonshot/kimi-k2.7-code',
            'nex n2 pro': 'nex-agi/nex-n2-pro:free',
            'grok 4.20': 'x-ai/grok-4.20',
            'grok 4.3': 'x-ai/grok-4.3',
            'grok build 0.1': 'x-ai/grok-build-0.1',
            'mimo v2.5 pro': 'xiaomi/mimo-v2.5-pro',
            'glm 5 turbo': 'z-ai/glm-5-turbo',
            'glm 5.1': 'z-ai/glm-5.1',
            'claude opus 4.5': 'anthropic/claude-opus-4.5',
            'claude opus 4.6': 'anthropic/claude-opus-4.6',
            'claude opus 4.7': 'anthropic/claude-opus-4.7',
            'claude opus 4.8': 'anthropic/claude-opus-4.8',
            'claude sonnet 4.5': 'anthropic/claude-sonnet-4.5',
            'claude sonnet 4.6': 'anthropic/claude-sonnet-4.6',
            'gemini 3.5 flash': 'google/gemini-3.5-flash',
            'gpt 5.4': 'openai/gpt-5.4',
            'qwen3.7 max': 'qwen/qwen3.7-max',
            'claude fable 5': 'anthropic/claude-fable-5',
            'gpt 5.3 codex': 'openai/gpt-5.3-codex',
            'gpt 5.5': 'openai/gpt-5.5',
            'claude opus 5': 'anthropic/claude-opus-5',
            'gemini 3.1 pro preview': 'google/gemini-3.1-pro-preview-customtools',
            'gemma 4 26b a4b it': 'google/gemma-4-26b-a4b-it:free',
            'gemma 4 31b it': 'google/gemma-4-31b-it:free',
            'gpt 5.6 luna': 'openai/gpt-5.6-luna',
            'gpt 5.6 luna pro': 'openai/gpt-5.6-luna-pro',
            'gpt 5.6 sol': 'openai/gpt-5.6-sol',
            'gpt 5.6 sol pro': 'openai/gpt-5.6-sol-pro',
            'gpt 5.6 terra': 'openai/gpt-5.6-terra',
            'gpt 5.6 terra pro': 'openai/gpt-5.6-terra-pro',
            'gpt oss 20b': 'openai/gpt-oss-20b:free',
            'qwen3 next 80b': 'qwen/qwen3-next-80b-a3b-instruct',
            'qwen3.8 max': 'qwen/qwen3.8-max',
            'grok 4.5': 'x-ai/grok-4.5',
            'mimo v2 pro': 'xiaomi/mimo-v2-pro'
        }
        
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                raw_name = parts[0]
                prompt_str = parts[1]
                completion_str = parts[2]
                
                matched_id = explicit_map.get(raw_name.lower())
                if not matched_id:
                    matched_id = f"utim/{raw_name.lower().replace(' ', '-')}"
                
                p_in = 0.0
                p_out = 0.0
                p_m = re.search(r'\$([0-9\.]+)', prompt_str)
                if p_m:
                    p_in = float(p_m.group(1)) / 1000.0
                c_m = re.search(r'\$([0-9\.]+)', completion_str)
                if c_m:
                    p_out = float(c_m.group(1)) / 1000.0
                    
                is_free = "free" in prompt_str.lower() or "free" in completion_str.lower() or (p_in == 0 and p_out == 0)
                
                if matched_id in MODEL_REGISTRY:
                    m_entry = MODEL_REGISTRY[matched_id]
                    m_entry.cost_input_per_1k = p_in
                    m_entry.cost_output_per_1k = p_out
                    if is_free and "free" not in m_entry.tags:
                        m_entry.tags = list(set(m_entry.tags + ["free"]))
                    elif not is_free and "free" in m_entry.tags:
                        m_entry.tags = [t for t in m_entry.tags if t != "free"]
                else:
                    MODEL_REGISTRY[matched_id] = ModelEntry(
                        model_id=matched_id,
                        provider="utim",
                        cost_input_per_1k=p_in,
                        cost_output_per_1k=p_out,
                        context_window=128_000,
                        capabilities=["chat", "coding"],
                        tags=["free"] if is_free else ["premium"],
                        description=f"{raw_name} - Main Agent Model on UTIM",
                    )
    except Exception:
        pass


_load_utimmodel_txt()



def sync_models_to_db(db_session=None):
    """Sync all in-memory MODEL_REGISTRY entries into the ModelDB database table."""
    try:
        from .db import SessionLocal, ModelDB
        db = db_session if db_session is not None else SessionLocal()
        close_after = db_session is None
        try:
            for mid, entry in MODEL_REGISTRY.items():
                existing = db.query(ModelDB).filter(ModelDB.model_id == mid).first()
                is_free = "free" in entry.tags or mid.endswith(":free")
                is_vision = "vision" in entry.capabilities or "vision" in entry.tags
                is_reasoning = "reasoning" in entry.capabilities or "reasoning" in entry.tags
                
                if not existing:
                    db_model = ModelDB(
                        model_id=mid,
                        name=mid.split('/')[-1].replace('-', ' ').title(),
                        provider=entry.provider,
                        context_window=entry.context_window,
                        max_output_tokens=entry.max_output_tokens,
                        cost_input_per_1m=entry.cost_input_per_1k * 1000,
                        cost_output_per_1m=entry.cost_output_per_1k * 1000,
                        capabilities=entry.capabilities,
                        tags=entry.tags,
                        is_free=is_free,
                        is_vision=is_vision,
                        is_reasoning=is_reasoning,
                        is_active=True,
                    )
                    db.add(db_model)
                else:
                    existing.capabilities = entry.capabilities
                    existing.tags = entry.tags
                    existing.is_vision = is_vision
                    existing.is_free = is_free
                    existing.context_window = entry.context_window
            db.commit()
        except Exception:
            db.rollback()
        finally:
            if close_after:
                db.close()
    except Exception:
        pass


def sync_live_openrouter_models():
    """Fetch live model pricing and free model availability directly from OpenRouter API.
    Dynamically updates MODEL_REGISTRY, strips outdated :free tags when OpenRouter stops providing a model for free,
    and updates models.txt locally.
    """
    import requests, json, os
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", []) if isinstance(data, dict) else data
            
            # Save fresh snapshot to models.txt
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            models_txt_path = os.path.join(root_dir, "models.txt")
            with open(models_txt_path, "w", encoding="utf-8") as f:
                json.dump({"data": items}, f, indent=2)

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

                if mid in MODEL_REGISTRY:
                    entry = MODEL_REGISTRY[mid]
                    entry.cost_input_per_1k = p_in / 1000.0
                    entry.cost_output_per_1k = p_out / 1000.0
                    if is_free_live:
                        if "free" not in entry.tags:
                            entry.tags = list(set(entry.tags + ["free"]))
                    else:
                        if "free" in entry.tags:
                            entry.tags = [t for t in entry.tags if t != "free"]

            sync_models_to_db()
            return True
    except Exception:
        pass
    return False


sync_models_to_db()

# Default model used when the user does not specify one
DEFAULT_MODEL: MODEL_ID = "cohere/north-mini-code:free"


# ─── Routing helpers ──────────────────────────────────────────────────────────

def get_model(model_id: MODEL_ID | None = None) -> ModelEntry:
    """Return a ModelEntry. Falls back to DEFAULT_MODEL if not found."""
    if model_id and model_id in MODEL_REGISTRY:
        return MODEL_REGISTRY[model_id]
    return MODEL_REGISTRY[DEFAULT_MODEL]


def list_models() -> list[ModelEntry]:
    """Return all registered models."""
    return list(MODEL_REGISTRY.values())


def estimate_cost(
    model_id: MODEL_ID,
    input_tokens: int,
    output_tokens: int,
    is_upgraded: bool = False,
) -> float:
    """Return estimated cost in credits for a request.
    UTIM Pricing Rules:
    - Free models: $0.02 / 1M input, $0.03 / 1M output (0.02 credits/1K in, 0.03 credits/1K out).
    - Paid users (is_upgraded=True): Receive a 10x discount across models.
    """
    # Check if this is a free model (ends with :free, openrouter/free, or tagged free in registry)
    is_free = model_id.endswith(":free") or model_id == "openrouter/free"
    if not is_free:
        m = MODEL_REGISTRY.get(model_id)
        if m and "free" in m.tags:
            is_free = True
            
    discount_multiplier = 0.10 if is_upgraded else 1.0

    if is_free:
        cost_in_per_1k = 0.02 * discount_multiplier
        cost_out_per_1k = 0.03 * discount_multiplier
        return (input_tokens / 1000.0) * cost_in_per_1k + (output_tokens / 1000.0) * cost_out_per_1k

    m = get_model(model_id)
    usd_cost = (input_tokens / 1_000.0) * m.cost_input_per_1k + (
        output_tokens / 1_000.0
    ) * m.cost_output_per_1k
    # 1 USD Dollar = 1,000 UTIM Credits (apply 10x discount for paid plan members)
    credits_cost = (usd_cost * 1000.0) * discount_multiplier
    return credits_cost




def route_model(task_description: str) -> MODEL_ID:
    """
    Simple heuristic router — can be swapped out for model-based routing later.

    Currently falls back to the DEFAULT_MODEL.
    """
    _ = task_description  # reserved for future LLM-based routing
    return DEFAULT_MODEL


# ─── Provider whitelist for catalog ──────────────────────────────────────────
# Only premium models from these providers are included in the catalog.
_CATALOG_PROVIDERS = frozenset([
    "anthropic", "google", "x-ai", "deepseek", "qwen",
    "moonshotai", "minimax", "kwaipilot", "openai",
    "z-ai", "stepfun", "xiaomi",
])

# Curated human-readable descriptions for well-known models
_MODEL_DESCRIPTIONS: dict[str, str] = {
    # Anthropic
    "anthropic/claude-opus-5":              "Anthropic's most capable frontier model.",
    "anthropic/claude-sonnet-5":            "High-performance Claude reasoning model.",
    "anthropic/claude-fable-5":             "Ultra-premium reasoning & creative writer by Anthropic.",
    "anthropic/claude-opus-4.8":            "Anthropic Claude Opus 4.8 — flagship intelligence.",
    "anthropic/claude-opus-4.7":            "Anthropic Claude Opus 4.7 — advanced reasoning.",
    "anthropic/claude-opus-4.6":            "Anthropic Claude Opus 4.6.",
    "anthropic/claude-opus-4.5":            "Anthropic Claude Opus 4.5.",
    "anthropic/claude-sonnet-4.6":          "Primary premium model for main agent and reasoning tasks.",
    "anthropic/claude-sonnet-4.5":          "Anthropic Claude Sonnet 4.5 — balanced speed & quality.",
    "anthropic/claude-haiku-4.5":           "Anthropic Claude Haiku 4.5 — fast and efficient.",
    # Google
    "google/gemini-3.6-flash":              "Google next-gen high-speed multimodal and reasoning model.",
    "google/gemini-3.5-flash":              "Fast, multimodal and agentic model by Google.",
    "google/gemini-3.1-pro-preview-customtools": "Gemini model optimised for complex tool calling.",
    "google/gemini-3.1-pro-preview":        "Google Gemini 3.1 Pro — 1M context multimodal.",
    "google/gemini-3.1-flash-image-preview": "Google cost-effective multimodal and image model.",
    "google/gemini-3.1-flash-image":        "Google stable image and multimodal vision model.",
    "google/gemini-3.1-flash-lite":         "Google Gemini 3.1 Flash Lite — ultra-fast.",
    "google/gemini-3-pro-image-preview":    "Google frontier multimodal and image generation model.",
    "google/gemini-3-pro-image":            "Google Gemini 3 Pro Image.",
    "google/gemini-2.5-pro":               "Google Gemini 2.5 Pro — advanced reasoning.",
    "google/gemini-2.5-flash":             "Google Gemini 2.5 Flash — high speed multimodal.",
    "google/gemini-2.5-flash-image":       "Google Gemini 2.5 Flash with image generation.",
    "google/gemini-2.5-flash-lite":        "Google Gemini 2.5 Flash Lite — ultra-fast.",
    "google/gemma-4-31b-it":              "Google Gemma 4 31B instruction-tuned.",
    "google/gemma-4-26b-a4b-it":          "Google Gemma 4 26B MoE instruction-tuned.",
    "google/gemma-3-27b-it":             "Google Gemma 3 27B instruction-tuned.",
    # xAI
    "x-ai/grok-4.5":                       "Latest xAI Grok 4.5 frontier reasoning model.",
    "x-ai/grok-4.3":                       "Frontier reasoning model with real-time knowledge by xAI.",
    "x-ai/grok-4.20":                      "xAI Grok 4.20 with 2M context.",
    "x-ai/grok-4.20-multi-agent":          "xAI Grok 4.20 optimised for multi-agent workflows.",
    "x-ai/grok-build-0.1":                 "xAI Grok Build — coding-focused agent.",
    "x-ai/grok-imagine-image-quality":     "xAI Grok image generation model.",
    # DeepSeek
    "deepseek/deepseek-v4-pro":            "DeepSeek flagship MoE and reasoning model.",
    "deepseek/deepseek-v4-flash":          "Ultra-fast, cost-effective model by DeepSeek.",
    "deepseek/deepseek-v3.2":             "DeepSeek V3.2 — latest generation.",
    "deepseek/deepseek-v3.2-exp":         "DeepSeek V3.2 Experimental.",
    "deepseek/deepseek-v3.1-terminus":    "DeepSeek V3.1 Terminus — advanced reasoning.",
    "deepseek/deepseek-chat-v3.1":        "DeepSeek Chat V3.1.",
    "deepseek/deepseek-chat-v3-0324":     "DeepSeek Chat V3 (March 2024).",
    "deepseek/deepseek-r1":               "DeepSeek R1 reasoning model with advanced chain-of-thought.",
    "deepseek/deepseek-r1-0528":          "DeepSeek R1 May 2028 update.",
    # Qwen
    "qwen/qwen3.8-max":                    "Qwen3.8 Max — next-generation flagship agentic & reasoning model with 1M context.",
    "qwen/qwen3.7-max":                    "Flagship agentic and reasoning model by Qwen.",
    "qwen/qwen3.7-plus":                   "Qwen3.7 Plus — fast agentic model.",
    "qwen/qwen3.6-max-preview":            "Qwen3.6 Max Preview — latest generation.",
    "qwen/qwen3.6-plus":                   "Qwen3.6 Plus — strong multimodal model.",
    "qwen/qwen3.6-flash":                  "Qwen3.6 Flash — high-speed model.",
    "qwen/qwen3.6-35b-a3b":               "Qwen3.6 35B MoE model.",
    "qwen/qwen3.6-27b":                    "Qwen3.6 27B dense model.",
    "qwen/qwen3.5-plus-20260420":         "Qwen3.5 Plus (April 2026).",
    "qwen/qwen3.5-397b-a17b":            "Qwen3.5 397B MoE model — massive scale.",
    "qwen/qwen3.5-122b-a10b":            "Qwen3.5 122B MoE model.",
    "qwen/qwen3.5-35b-a3b":              "Qwen3.5 35B MoE model.",
    "qwen/qwen3.5-27b":                   "Qwen3.5 27B dense model.",
    "qwen/qwen3.5-9b":                    "Qwen3.5 9B — lightweight and fast.",
    "qwen/qwen3-max":                      "Qwen3 Max — flagship MoE model.",
    "qwen/qwen3-coder":                    "Qwen3 Coder — specialised coding model.",
    "qwen/qwen3-coder-plus":               "Qwen3 Coder Plus — advanced coding.",
    "qwen/qwen3-vl-235b-a22b-instruct":  "Qwen3 VL 235B — multimodal vision-language.",
    "qwen/qwen3-vl-32b-instruct":        "Qwen3 VL 32B — vision-language model.",
    "qwen/qwen3-vl-8b-instruct":         "Qwen3 VL 8B — compact vision-language.",
    "qwen/qwen3-235b-a22b":             "Qwen3 235B MoE — top-tier model.",
    "qwen/qwen3-32b":                    "Qwen3 32B dense model.",
    "qwen/qwen2.5-vl-72b-instruct":     "Qwen2.5 VL 72B — vision-language.",
    # MoonshotAI
    "moonshotai/kimi-k3":                  "Frontier-class reasoning MoE model by Moonshot AI.",
    "moonshotai/kimi-k2.7-code":           "Open-weights coder model by Moonshot AI.",
    "moonshotai/kimi-k2.6":                "High-capability multimodal model by Moonshot AI.",
    "moonshotai/kimi-k2.5":                "MoonshotAI Kimi K2.5 — strong reasoning.",
    "moonshotai/kimi-k2":                  "MoonshotAI Kimi K2 — flagship model.",
    "moonshotai/kimi-k2-thinking":         "Kimi K2 with native thinking/reasoning.",
    "moonshotai/kimi-k2-0905":            "Kimi K2 September 2025 update.",
    # MiniMax
    "minimax/minimax-m2.7":                "High-performance chat and coding model by MiniMax.",
    "minimax/minimax-m2.5":                "MiniMax M2.5 — balanced performance.",
    "minimax/minimax-m2.1":                "MiniMax M2.1.",
    "minimax/minimax-m2":                  "MiniMax M2.",
    "minimax/minimax-m2-her":              "MiniMax M2 Her.",
    "minimax/minimax-m1":                  "MiniMax M1.",
    "minimax/minimax-01":                  "MiniMax 01 — vision capable.",
    # KwaiPilot
    "kwaipilot/kat-coder-pro-v2.5":       "Flagship advanced coding and reasoning model by KwaiPilot.",
    "kwaipilot/kat-coder-air-v2.5":       "Fast, high-efficiency coding model by KwaiPilot.",
    "kwaipilot/kat-coder-pro-v2":          "Coding-focused assistant by KwaiPilot.",
    # OpenAI
    "openai/gpt-5.5":                      "Next-gen frontier reasoning model by OpenAI.",
    "openai/gpt-5.5-pro":                  "GPT-5.5 Pro — premium frontier model.",
    "openai/gpt-5.4":                      "Advanced reasoning and analysis model by OpenAI.",
    "openai/gpt-5.4-pro":                  "GPT-5.4 Pro — high-capability model.",
    "openai/gpt-5.4-mini":                 "GPT-5.4 Mini — efficient and capable.",
    "openai/gpt-5.4-nano":                 "GPT-5.4 Nano — ultra-fast.",
    "openai/gpt-5.4-image-2":             "GPT-5.4 with image generation capabilities.",
    "openai/gpt-5.3-codex":               "Premium OpenAI model optimised for deep coding tasks.",
    "openai/gpt-5.3-chat":                "GPT-5.3 Chat — conversational AI.",
    "openai/gpt-5.2":                      "OpenAI GPT-5.2 — powerful reasoning.",
    "openai/gpt-5.2-pro":                  "GPT-5.2 Pro.",
    "openai/gpt-5.2-codex":               "GPT-5.2 Codex — coding model.",
    "openai/gpt-5.2-chat":                "GPT-5.2 Chat.",
    "openai/gpt-5.1":                      "OpenAI GPT-5.1.",
    "openai/gpt-5.1-codex":               "GPT-5.1 Codex — coding model.",
    "openai/gpt-5.1-codex-mini":          "GPT-5.1 Codex Mini.",
    "openai/gpt-5.1-codex-max":           "GPT-5.1 Codex Max — premium coding.",
    "openai/gpt-5":                        "OpenAI GPT-5 — frontier language model.",
    "openai/gpt-5-pro":                    "GPT-5 Pro — highest capability.",
    "openai/gpt-5-mini":                   "GPT-5 Mini — efficient version.",
    "openai/gpt-5-nano":                   "GPT-5 Nano — ultra-lightweight.",
    "openai/gpt-5-image":                  "GPT-5 with image generation.",
    "openai/gpt-5-image-mini":             "GPT-5 image mini — fast image generation.",
    "openai/gpt-5-codex":                  "GPT-5 Codex — advanced coding.",
    "openai/o4-mini":                      "OpenAI o4-mini — fast reasoning model.",
    "openai/o4-mini-high":                 "OpenAI o4-mini High — enhanced reasoning.",
    "openai/o3":                           "OpenAI o3 — advanced reasoning.",
    "openai/o3-pro":                       "OpenAI o3 Pro — top reasoning model.",
    "openai/o3-mini":                      "OpenAI o3-mini.",
    "openai/o3-mini-high":                 "OpenAI o3-mini High.",
    "openai/o1":                           "OpenAI o1 — pioneering reasoning model.",
    "openai/o1-pro":                       "OpenAI o1 Pro.",
    "openai/gpt-image-2":                  "OpenAI advanced image synthesis and editing model.",
    "openai/gpt-image-1":                  "OpenAI GPT Image 1.",
    "openai/gpt-image-1-mini":             "OpenAI GPT Image 1 Mini.",
    "openai/gpt-4.1":                      "OpenAI GPT-4.1.",
    "openai/gpt-4.1-mini":                 "OpenAI GPT-4.1 Mini.",
    "openai/gpt-4.1-nano":                 "OpenAI GPT-4.1 Nano.",
    "openai/gpt-4o":                       "OpenAI GPT-4o — multimodal.",
    "openai/gpt-4o-mini":                  "OpenAI GPT-4o Mini.",
    "openai/gpt-oss-120b":                "OpenAI OSS 120B — open-source model.",
    "openai/gpt-oss-20b":                 "OpenAI OSS 20B — open-source model.",
    # Z.ai
    "z-ai/glm-5.1":                        "Highly intelligent model by Z-AI.",
    "z-ai/glm-5.2":                        "Z.ai GLM 5.2 — advanced intelligence.",
    "z-ai/glm-5-turbo":                    "Z.ai GLM 5 Turbo — fast & capable.",
    "z-ai/glm-5":                          "Z.ai GLM 5.",
    "z-ai/glm-4.7":                        "Z.ai GLM 4.7.",
    "z-ai/glm-4.7-flash":                  "Z.ai GLM 4.7 Flash — ultra-fast.",
    "z-ai/glm-4.6":                        "Z.ai GLM 4.6.",
    "z-ai/glm-4.6v":                       "Z.ai GLM 4.6V — vision model.",
    "z-ai/glm-4.5":                        "Z.ai GLM 4.5.",
    "z-ai/glm-4.5v":                       "Z.ai GLM 4.5V — vision model.",
    "z-ai/glm-4.5-air":                    "Z.ai GLM 4.5 Air — lightweight.",
    # StepFun
    "stepfun/step-3.5-flash":             "Cost-effective multimodal assistant by StepFun.",
    "stepfun/step-3.7-flash":             "StepFun Step 3.7 Flash — advanced capabilities.",
    # Xiaomi
    "xiaomi/mimo-v2.5-pro":               "Xiaomi flagship multimodal and reasoning model.",
    "xiaomi/mimo-v2.5":                   "Highly capable multimodal model by Xiaomi.",
    "xiaomi/mimo-v2-pro":                  "Xiaomi MiMo V2 Pro.",
}


# ─── Catalog API ──────────────────────────────────────────────────────────────

def _is_target_provider(model_id: str) -> bool:
    """True if the model belongs to one of the 12 whitelisted providers."""
    provider = model_id.split("/")[0].lower() if "/" in model_id else ""
    return provider in _CATALOG_PROVIDERS


def get_model_catalog() -> dict:
    """Return a structured model catalog grouped by tool capability.

    The catalog is consumed by the UTIM CLI /models/catalog endpoint.
    Only models from the 12 whitelisted providers are included (no aliases).

    Returns a dict:
    {
        "main_agent":    [...],  # text_chat models
        "plan_project":  [...],  # text_chat models (same as main_agent)
        "analyze_image": [...],  # vision models (image input)
        "image_gen":     [...],  # image_generation models (image output)
        "all_text":      [...],  # all text_chat models (includes non-whitelisted free)
    }
    Each item is:
    {
        "model_id": str,
        "name": str,
        "provider": str,
        "description": str,
        "context_window": int,
        "max_output_tokens": int | None,
        "cost_input_per_1k": float,
        "cost_output_per_1k": float,
        "capabilities": list[str],
        "tags": list[str],
        "is_free": bool,
        "is_vision": bool,
        "is_image_gen": bool,
        "is_reasoning": bool,
    }
    """
    main_agent = []
    plan_project = []
    subagent_text = []
    analyze_image = []
    image_gen = []
    all_text = []

    seen_main: set[str] = set()
    seen_plan: set[str] = set()
    seen_subtext: set[str] = set()
    seen_vision: set[str] = set()
    seen_imggen: set[str] = set()
    seen_alltext: set[str] = set()

    from .routes.rewards_routes import AUTHORITATIVE_66_MODEL_IDS
    approved_main_ids = set(AUTHORITATIVE_66_MODEL_IDS)

    for mid, entry in MODEL_REGISTRY.items():
        # Skip OpenRouter alias models (start with ~)
        if mid.startswith("~"):
            continue

        is_free = "free" in entry.tags or mid.endswith(":free")
        is_vision = entry.vision
        is_img_gen = entry.image_gen
        is_reasoning = "reasoning" in entry.capabilities or "reasoning" in entry.tags
        is_target = _is_target_provider(mid)

        provider = mid.split("/")[0] if "/" in mid else "unknown"
        desc = _MODEL_DESCRIPTIONS.get(mid) or entry.description or mid.split("/")[-1].replace("-", " ").title()
        max_out = entry.max_output_tokens
        
        item = {
            "model_id": mid,
            "name": desc,
            "provider": provider,
            "description": desc,
            "context_window": entry.context_window or 128_000,
            "max_output_tokens": max_out,
            "cost_input_per_1k": entry.cost_input_per_1k,
            "cost_output_per_1k": entry.cost_output_per_1k,
            "capabilities": entry.capabilities,
            "tags": entry.tags,
            "is_free": is_free,
            "is_vision": is_vision,
            "is_image_gen": is_img_gen,
            "is_reasoning": is_reasoning,
        }

        # 1. main_agent: strictly the official UTIM main agent models (utimmodel.txt list) + any free models in the registry
        # Must support text chat AND (be in approved list OR be free) AND not be image gen
        is_main_agent_approved = (mid in approved_main_ids) or is_free
        if is_main_agent_approved and entry.text_chat and not is_img_gen and mid not in seen_main:
            seen_main.add(mid)
            main_agent.append(item)

        # 2. plan_project: planner subagent models (text_chat & reasoning models)
        if entry.text_chat and is_target and mid not in seen_plan:
            seen_plan.add(mid)
            plan_project.append(item)

        # 3. subagent_text: all text/code/search subagent models
        if entry.text_chat and mid not in seen_subtext:
            seen_subtext.add(mid)
            subagent_text.append(item)

        # 4. analyze_image: vision models (image input)
        if is_vision and is_target and mid not in seen_vision:
            seen_vision.add(mid)
            analyze_image.append(item)

        # 5. image_gen: image generation models (image output)
        if is_img_gen and is_target and mid not in seen_imggen:
            seen_imggen.add(mid)
            image_gen.append(item)

        # 6. all_text: complete text chat model catalog
        if entry.text_chat and mid not in seen_alltext:
            seen_alltext.add(mid)
            all_text.append(item)

    # Sort each register deterministically by free status, cost, then model_id
    def _sort_key(x):
        free_first = 0 if x["is_free"] else 1
        return (free_first, x["cost_input_per_1k"], x["model_id"])

    main_agent.sort(key=_sort_key)
    plan_project.sort(key=_sort_key)
    subagent_text.sort(key=_sort_key)
    analyze_image.sort(key=_sort_key)
    image_gen.sort(key=lambda x: (x["cost_input_per_1k"] + x["cost_output_per_1k"], x["model_id"]))
    all_text.sort(key=_sort_key)

    return {
        "main_agent": main_agent,
        "plan_project": plan_project,
        "subagent_text": subagent_text,
        "analyze_image": analyze_image,
        "image_gen": image_gen,
        "all_text": all_text,
    }
