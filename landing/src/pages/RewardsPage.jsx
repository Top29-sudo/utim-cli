import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Gift, Sparkles, ShieldCheck, Check, X, RefreshCw, Trophy, Lock, Zap, Clock, Search, Filter } from 'lucide-react';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import { useAuth } from '../context/AuthContext';
import './RewardsPage.css';

export function formatCleanModelName(rawName, modelId) {
  let name = rawName || modelId || '';
  if (name.includes('/')) {
    name = name.split('/')[1];
  }
  name = name.replace(/:free$/i, '').trim();
  return name;
}

// Authoritative UTIM Rewards model list — synced from utimmodel.txt & rewards_engine.py
// 66 total models | Free: 14 | VeryLow: 17 | Higher: 23 | Premium: 12
// Authoritative UTIM Rewards model list -- synced from utimmodel.txt & rewards_engine.py
// 66 total models | Free: 5 | VeryLow: 21 | Higher: 31 | Premium: 9
// Authoritative UTIM Rewards model list -- synced from utimmodel.txt & rewards_engine.py
// 66 total models | Free: 5 | VeryLow: 15 | Higher: 29 | Premium: 17
const FULL_MODEL_LIST = [
  {
    "model_id": "cohere/north-mini-code:free",
    "name": "North mini code",
    "provider": "cohere",
    "category": "free",
    "category_name": "Free Models",
    "probability_percent": 16.0,
    "precision_units": 1600000,
    "prompt_cost_per_m": 0.0,
    "completion_cost_per_m": 0.0
  },
  {
    "model_id": "poolside/laguna-s-2.1:free",
    "name": "Laguna s 2.1",
    "provider": "poolside",
    "category": "free",
    "category_name": "Free Models",
    "probability_percent": 16.0,
    "precision_units": 1600000,
    "prompt_cost_per_m": 0.0,
    "completion_cost_per_m": 0.0
  },
  {
    "model_id": "google/gemma-4-26b-a4b-it:free",
    "name": "Gemma 4 26b a4b it",
    "provider": "google",
    "category": "free",
    "category_name": "Free Models",
    "probability_percent": 16.0,
    "precision_units": 1600000,
    "prompt_cost_per_m": 0.0,
    "completion_cost_per_m": 0.0
  },
  {
    "model_id": "google/gemma-4-31b-it:free",
    "name": "Gemma 4 31b it",
    "provider": "google",
    "category": "free",
    "category_name": "Free Models",
    "probability_percent": 16.0,
    "precision_units": 1600000,
    "prompt_cost_per_m": 0.0,
    "completion_cost_per_m": 0.0
  },
  {
    "model_id": "openai/gpt-oss-20b:free",
    "name": "Gpt oss 20b",
    "provider": "openai",
    "category": "free",
    "category_name": "Free Models",
    "probability_percent": 16.0,
    "precision_units": 1600000,
    "prompt_cost_per_m": 0.0,
    "completion_cost_per_m": 0.0
  },
  {
    "model_id": "deepseek/deepseek-v4-flash-0731",
    "name": "Deepseek v4 flash 0731",
    "provider": "deepseek",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.08,
    "completion_cost_per_m": 0.18
  },
  {
    "model_id": "deepseek/deepseek-v4-flash",
    "name": "Deepseek v4 flash",
    "provider": "deepseek",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.08,
    "completion_cost_per_m": 0.18
  },
  {
    "model_id": "inclusionai/ling-2.6-flash:free",
    "name": "Ling 2.6 flash",
    "provider": "inclusionai",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.01,
    "completion_cost_per_m": 0.03
  },
  {
    "model_id": "kwaipilot/kat-coder-air-v2.5",
    "name": "Kat coder air v2.5",
    "provider": "kwaipilot",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.15,
    "completion_cost_per_m": 0.6
  },
  {
    "model_id": "minimax/minimax-m2.5",
    "name": "Minimax m2.5",
    "provider": "minimax",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.22,
    "completion_cost_per_m": 0.9
  },
  {
    "model_id": "nex-agi/nex-n2-mini",
    "name": "Nex n2 mini",
    "provider": "nex-agi",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.025,
    "completion_cost_per_m": 0.1
  },
  {
    "model_id": "xiaomi/mimo-v2.5",
    "name": "Mimo v2.5",
    "provider": "xiaomi",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.14,
    "completion_cost_per_m": 0.28
  },
  {
    "model_id": "deepseek/deepseek-v4-pro",
    "name": "Deepseek v4 pro",
    "provider": "deepseek",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.435,
    "completion_cost_per_m": 0.87
  },
  {
    "model_id": "inclusionai/ling-2.6-1t",
    "name": "Ling 2.6 1t",
    "provider": "inclusionai",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.075,
    "completion_cost_per_m": 0.625
  },
  {
    "model_id": "deepseek/deepseek-r1",
    "name": "Deepseek r1",
    "provider": "deepseek",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.25,
    "completion_cost_per_m": 0.95
  },
  {
    "model_id": "xiaomi/mimo-v2.5-pro",
    "name": "Mimo v2.5 pro",
    "provider": "xiaomi",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.435,
    "completion_cost_per_m": 0.87
  },
  {
    "model_id": "openai/gpt-5.6-luna",
    "name": "Gpt 5.6 luna",
    "provider": "openai",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.1,
    "completion_cost_per_m": 0.6
  },
  {
    "model_id": "openai/gpt-5.6-luna-pro",
    "name": "Gpt 5.6 luna pro",
    "provider": "openai",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.1,
    "completion_cost_per_m": 0.6
  },
  {
    "model_id": "qwen/qwen3-next-80b-a3b-instruct",
    "name": "Qwen3 Next 80B",
    "provider": "qwen",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.117,
    "completion_cost_per_m": 0.455
  },
  {
    "model_id": "xiaomi/mimo-v2-pro",
    "name": "Mimo v2 pro",
    "provider": "xiaomi",
    "category": "very_low",
    "category_name": "Very Low Cost Models",
    "probability_percent": 1.33,
    "precision_units": 133000,
    "prompt_cost_per_m": 0.435,
    "completion_cost_per_m": 0.87
  },
  {
    "model_id": "muses/muse-spark-1.1:free",
    "name": "Muse spark 1.1",
    "provider": "muses",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.25,
    "completion_cost_per_m": 4.25
  },
  {
    "model_id": "thinkingmachines/inkling-small:free",
    "name": "Inkling",
    "provider": "thinkingmachines",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.95,
    "completion_cost_per_m": 4.05
  },
  {
    "model_id": "kwaipilot/kat-coder-pro-v2",
    "name": "Kat coder pro v2",
    "provider": "kwaipilot",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.3,
    "completion_cost_per_m": 1.2
  },
  {
    "model_id": "kwaipilot/kat-coder-pro-v2.5",
    "name": "Kat coder pro v2.5",
    "provider": "kwaipilot",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.74,
    "completion_cost_per_m": 2.96
  },
  {
    "model_id": "minimax/minimax-m3",
    "name": "Minimax m3",
    "provider": "minimax",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.3,
    "completion_cost_per_m": 1.2
  },
  {
    "model_id": "moonshot/kimi-k2.5",
    "name": "Kimi k2.5",
    "provider": "moonshot",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.57,
    "completion_cost_per_m": 2.85
  },
  {
    "model_id": "openai/gpt-5.4-mini",
    "name": "Gpt 5.4 mini",
    "provider": "openai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.75,
    "completion_cost_per_m": 4.5
  },
  {
    "model_id": "qwen/qwen3.6-plus",
    "name": "Qwen3.6 plus",
    "provider": "qwen",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.325,
    "completion_cost_per_m": 1.95
  },
  {
    "model_id": "qwen/qwen3.7-plus",
    "name": "Qwen3.7 plus",
    "provider": "qwen",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.32,
    "completion_cost_per_m": 1.28
  },
  {
    "model_id": "stepfun/step-3.7-flash",
    "name": "Step 3.7 flash",
    "provider": "stepfun",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.2,
    "completion_cost_per_m": 1.15
  },
  {
    "model_id": "z-ai/glm-4.7",
    "name": "Glm 4.7",
    "provider": "z-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.4,
    "completion_cost_per_m": 1.75
  },
  {
    "model_id": "z-ai/glm-5",
    "name": "Glm 5",
    "provider": "z-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.95,
    "completion_cost_per_m": 2.55
  },
  {
    "model_id": "z-ai/glm-5.2",
    "name": "Glm 5.2",
    "provider": "z-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.76,
    "completion_cost_per_m": 2.42
  },
  {
    "model_id": "google/gemini-3.6-flash",
    "name": "Gemini 3.6 flash",
    "provider": "google",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.5,
    "completion_cost_per_m": 7.5
  },
  {
    "model_id": "minimax/minimax-m2.7",
    "name": "Minimax m2.7",
    "provider": "minimax",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.3,
    "completion_cost_per_m": 1.2
  },
  {
    "model_id": "moonshot/kimi-k2.6",
    "name": "Kimi k2.6",
    "provider": "moonshot",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.95,
    "completion_cost_per_m": 4.0
  },
  {
    "model_id": "moonshot/kimi-k2.7-code",
    "name": "Kimi k2.7 code",
    "provider": "moonshot",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.7,
    "completion_cost_per_m": 3.5
  },
  {
    "model_id": "nex-agi/nex-n2-pro:free",
    "name": "Nex n2 pro",
    "provider": "nex-agi",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 0.25,
    "completion_cost_per_m": 1.0
  },
  {
    "model_id": "x-ai/grok-4.20",
    "name": "Grok 4.20",
    "provider": "x-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.25,
    "completion_cost_per_m": 2.5
  },
  {
    "model_id": "x-ai/grok-4.3",
    "name": "Grok 4.3",
    "provider": "x-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.25,
    "completion_cost_per_m": 2.5
  },
  {
    "model_id": "x-ai/grok-build-0.1",
    "name": "Grok build 0.1",
    "provider": "x-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.0,
    "completion_cost_per_m": 2.0
  },
  {
    "model_id": "z-ai/glm-5-turbo",
    "name": "Glm 5 turbo",
    "provider": "z-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.2,
    "completion_cost_per_m": 4.0
  },
  {
    "model_id": "z-ai/glm-5.1",
    "name": "Glm 5.1",
    "provider": "z-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.4,
    "completion_cost_per_m": 4.4
  },
  {
    "model_id": "google/gemini-3.5-flash",
    "name": "Gemini 3.5 flash",
    "provider": "google",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.5,
    "completion_cost_per_m": 9.0
  },
  {
    "model_id": "qwen/qwen3.7-max",
    "name": "Qwen3.7 max",
    "provider": "qwen",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.48,
    "completion_cost_per_m": 4.42
  },
  {
    "model_id": "openai/gpt-5.6-terra",
    "name": "Gpt 5.6 terra",
    "provider": "openai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.0,
    "completion_cost_per_m": 6.0
  },
  {
    "model_id": "openai/gpt-5.6-terra-pro",
    "name": "Gpt 5.6 terra pro",
    "provider": "openai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 1.0,
    "completion_cost_per_m": 6.0
  },
  {
    "model_id": "qwen/qwen3.8-max",
    "name": "Qwen3.8 max",
    "provider": "qwen",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 2.0,
    "completion_cost_per_m": 6.0
  },
  {
    "model_id": "x-ai/grok-4.5",
    "name": "Grok 4.5",
    "provider": "x-ai",
    "category": "higher",
    "category_name": "Higher Cost Models",
    "probability_percent": 0.00138,
    "precision_units": 138,
    "prompt_cost_per_m": 2.0,
    "completion_cost_per_m": 6.0
  },
  {
    "model_id": "moonshot/kimi-k3",
    "name": "Kimi k3",
    "provider": "moonshot",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 3.0,
    "completion_cost_per_m": 15.0
  },
  {
    "model_id": "anthropic/claude-sonnet-5",
    "name": "Claude sonnet 5",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 2.0,
    "completion_cost_per_m": 10.0
  },
  {
    "model_id": "google/gemini-3.1-pro-preview",
    "name": "gemini-3.1-pro-preview",
    "provider": "google",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 2.0,
    "completion_cost_per_m": 12.0
  },
  {
    "model_id": "anthropic/claude-opus-4.5",
    "name": "Claude opus 4.5",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 5.0,
    "completion_cost_per_m": 25.0
  },
  {
    "model_id": "anthropic/claude-opus-4.6",
    "name": "Claude opus 4.6",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 5.0,
    "completion_cost_per_m": 25.0
  },
  {
    "model_id": "anthropic/claude-opus-4.7",
    "name": "Claude opus 4.7",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 30.0,
    "completion_cost_per_m": 150.0
  },
  {
    "model_id": "anthropic/claude-opus-4.8",
    "name": "Claude opus 4.8",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 10.0,
    "completion_cost_per_m": 50.0
  },
  {
    "model_id": "anthropic/claude-sonnet-4.5",
    "name": "Claude sonnet 4.5",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 3.0,
    "completion_cost_per_m": 15.0
  },
  {
    "model_id": "anthropic/claude-sonnet-4.6",
    "name": "Claude sonnet 4.6",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 3.0,
    "completion_cost_per_m": 15.0
  },
  {
    "model_id": "openai/gpt-5.4",
    "name": "Gpt 5.4",
    "provider": "openai",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 2.5,
    "completion_cost_per_m": 15.0
  },
  {
    "model_id": "anthropic/claude-fable-5",
    "name": "Claude fable 5",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 10.0,
    "completion_cost_per_m": 50.0
  },
  {
    "model_id": "openai/gpt-5.3-codex",
    "name": "Gpt 5.3 codex",
    "provider": "openai",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 1.75,
    "completion_cost_per_m": 14.0
  },
  {
    "model_id": "openai/gpt-5.5",
    "name": "Gpt 5.5",
    "provider": "openai",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 5.0,
    "completion_cost_per_m": 30.0
  },
  {
    "model_id": "anthropic/claude-opus-5",
    "name": "Claude opus 5",
    "provider": "anthropic",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 10.0,
    "completion_cost_per_m": 50.0
  },
  {
    "model_id": "google/gemini-3.1-pro-preview-customtools",
    "name": "Gemini 3.1 pro preview",
    "provider": "google",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 2.0,
    "completion_cost_per_m": 12.0
  },
  {
    "model_id": "openai/gpt-5.6-sol",
    "name": "Gpt 5.6 sol",
    "provider": "openai",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 5.0,
    "completion_cost_per_m": 30.0
  },
  {
    "model_id": "openai/gpt-5.6-sol-pro",
    "name": "Gpt 5.6 sol pro",
    "provider": "openai",
    "category": "premium",
    "category_name": "Premium / Jackpot Models",
    "probability_percent": 0.00059,
    "precision_units": 59,
    "prompt_cost_per_m": 5.0,
    "completion_cost_per_m": 30.0
  }
];

const scatterModels = (models) => {
  const groups = { free: [], very_low: [], higher: [], premium: [] };
  models.forEach(m => {
    const cat = m.category || 'very_low';
    if (groups[cat]) groups[cat].push(m);
    else groups.very_low.push(m);
  });
  
  const result = [];
  const maxLen = Math.max(
    groups.free.length,
    groups.very_low.length,
    groups.higher.length,
    groups.premium.length
  );
  
  for (let i = 0; i < maxLen; i++) {
    if (i < groups.free.length) result.push(groups.free[i]);
    if (i < groups.very_low.length) result.push(groups.very_low[i]);
    if (i < groups.higher.length) result.push(groups.higher[i]);
    if (i < groups.premium.length) result.push(groups.premium[i]);
  }
  return result;
};

export default function RewardsPage() {
  const { user, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [selectedOmissions, setSelectedOmissions] = useState([]);
  const [spinning, setSpinning] = useState(false);
  const [slotOffset, setSlotOffset] = useState(0);
  const [winResult, setWinResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [spinningDone, setSpinningDone] = useState(false);
  const slotTrackRef = useRef(null);

  const defaultStatus = {
    is_paid_plan: true,
    plan_display_name: 'Pro Plan',
    spins_granted: 4,
    spins_used: 1,
    spins_remaining: 3,
    max_omissions_allowed: 5,
    active_reward: {
      model_id: 'claude-3-7-sonnet',
      model_name: 'Claude 3.7 Sonnet',
      time_remaining_seconds: 64200,
      reward_end: '2026-08-11T12:00:00Z'
    },
    current_omissions: ['qwen-3-80b:free', 'gemma-4-31b:free'],
    probabilities: {
      category_probabilities: { free: 80.00, very_low: 19.95, higher: 0.04, premium: 0.01 },
      models: FULL_MODEL_LIST
    },
    all_models: FULL_MODEL_LIST
  };

  useEffect(() => {
    if (authLoading) return;

    const fetchStatus = async () => {
      try {
        const token = user ? await user.getIdToken() : null;
        const res = await fetch('/api/rewards/status', {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          setSelectedOmissions(data.current_omissions || []);
        } else {
          throw new Error();
        }
      } catch (err) {
        setStatus(defaultStatus);
        setSelectedOmissions(defaultStatus.current_omissions);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
  }, [user, authLoading]);

  const handleToggleOmission = async (modelId) => {
    if (!status) return;
    const maxAllowed = status.max_omissions_allowed || 0;
    let updated = [...selectedOmissions];
    if (updated.includes(modelId)) {
      updated = updated.filter(id => id !== modelId);
    } else {
      if (updated.length >= maxAllowed) {
        setErrorMsg(`Your ${status.plan_display_name} allows omitting up to ${maxAllowed} models.`);
        return;
      }
      updated.push(modelId);
    }
    setErrorMsg('');
    setSelectedOmissions(updated);

    if (status.plan_id === 'guest' || !user) {
      return;
    }

    try {
      const token = await user.getIdToken();
      const res = await fetch('/api/rewards/confirm-snapshot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ omitted_models: updated })
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(prev => ({
          ...prev,
          current_omissions: data.probabilities.omitted_models,
          probabilities: data.probabilities
        }));
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Failed to sync omissions with the server.');
      }
    } catch (err) {
      setErrorMsg('Failed to sync omissions with the server.');
    }
  };

  // SLOT MACHINE: card width + gap in px
  const CARD_W = 148;
  const SPIN_DURATION = 6500; // ms

  const doSpin = (winningModel, allModelsList) => {
    const winIdx = allModelsList.findIndex(m => m.model_id === winningModel.model_id);
    const safeWinIdx = winIdx >= 0 ? winIdx : 0;
    // Spin at least 8 full laps then land on winner in center
    const laps = 8;
    const landOffset = -(safeWinIdx * CARD_W + laps * allModelsList.length * CARD_W);
    setSlotOffset(landOffset);
    setSpinningDone(false);

    setTimeout(() => {
      setSpinning(false);
      setSpinningDone(true);
      setWinResult({ winning_model: winningModel });
      setStatus(prev => ({
        ...prev,
        spins_used: prev.spins_used + 1,
        spins_remaining: Math.max(0, prev.spins_remaining - 1),
        active_reward: {
          model_id: winningModel.model_id,
          model_name: winningModel.name,
          time_remaining_seconds: 86400,
        }
      }));
    }, SPIN_DURATION + 200);
  };

  const handleSpinWheel = async () => {
    if (spinning || !status || status.spins_remaining <= 0) return;
    setSpinning(true);
    setSpinningDone(false);
    setErrorMsg('');
    setWinResult(null);
    // Reset position instantly before animating
    setSlotOffset(0);

    try {
      const token = user ? await user.getIdToken() : null;
      const res = await fetch('/api/rewards/spin', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        }
      });
      if (res.ok) {
        const data = await res.json();
        doSpin(data.winning_model, scatteredModelsList);
      } else {
        const e = await res.json();
        throw e;
      }
    } catch (err) {
      // Weighted local fallback
      const models = scatteredModelsList;
      const rand = Math.random() * 100;
      let cum = 0, winner = models[0];
      for (const m of models) {
        cum += m.probability_percent;
        if (rand <= cum) { winner = m; break; }
      }
      doSpin(winner, models);
    }
  };
  const allModels = status?.all_models || FULL_MODEL_LIST;
  const rawModelsList = status?.probabilities?.models || FULL_MODEL_LIST;
  const modelsList = useMemo(() => {
    return rawModelsList.filter(m => !selectedOmissions.includes(m.model_id));
  }, [rawModelsList, selectedOmissions]);

  const scatteredModelsList = useMemo(() => scatterModels(modelsList), [modelsList]);
  const activeReward = status?.active_reward;
  // Build infinite-loop slot strip: repeat 12x so animation never runs out
  const REPEATS = 12;
  const slotStrip = useMemo(() => Array.from({ length: REPEATS }, () => scatteredModelsList).flat(), [scatteredModelsList]);

  if (loading) {
    return (
      <div className="rw-loading-container">
        <RefreshCw className="rw-spinner" size={32} />
        <p>Loading UTIM Rewards Wheel...</p>
      </div>
    );
  }
  // Filter models for Omission selector and probability table
  const filteredModels = allModels.filter(m => {
    const matchesCat = filterCategory === 'all' || m.category === filterCategory;
    const matchesSearch = !searchQuery || m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.model_id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <>
      <ScrollytellingHeaderNav />
      <div className="rw-page-wrapper">
        <div className="st-container">
          {/* Header HUD */}
          <div className="rw-header-hud">
            <div className="rw-badge">
              <Trophy size={14} color="#d97706" /> UTIM REWARDS HUB — 66 MAIN MODELS ACTIVE
            </div>
            <h1 className="rw-title">UTIM Rewards Wheel</h1>
            <p className="rw-subtitle">
              Spin to unlock 24-hour unlimited access to top AI models. All paid plans get 4 spins per 30-day cycle.
            </p>

            {/* Active Reward Banner */}
            {activeReward && (
              <div className="rw-active-reward-card">
                <div className="rw-arc-left">
                  <Zap size={22} color="#059669" />
                  <div>
                    <h3>Active 24-Hour Reward: <span>{formatCleanModelName(activeReward.model_name, activeReward.model_id)}</span></h3>
                    <p>All requests to this model are 100% free and consume zero quota.</p>
                  </div>
                </div>
                <div className="rw-arc-time">
                  <Clock size={16} />
                  <span>{Math.floor(activeReward.time_remaining_seconds / 3600)}h {Math.floor((activeReward.time_remaining_seconds % 3600) / 60)}m remaining</span>
                </div>
              </div>
            )}

            {/* Spin Allowance Stats */}
            <div className="rw-stats-grid">
              <div className="rw-stat-box">
                <span className="rw-sb-label">Subscription Plan</span>
                <span className="rw-sb-val">{status.plan_display_name}</span>
              </div>
              <div className="rw-stat-box">
                <span className="rw-sb-label">Spins Remaining</span>
                <span className="rw-sb-val highlight">{status.spins_remaining} / {status.spins_granted}</span>
              </div>
              <div className="rw-stat-box">
                <span className="rw-sb-label">Total Agent Models</span>
                <span className="rw-sb-val">{allModels.length} Models Active</span>
              </div>
              <div className="rw-stat-box">
                <span className="rw-sb-label">Omission Limit</span>
                <span className="rw-sb-val">Up to {status.max_omissions_allowed} models</span>
              </div>
            </div>
          </div>

          {/* Main Grid: Slot Machine + Omission Manager */}
          <div className="rw-main-grid">
            <div className="rw-wheel-card">
              <div className="rw-wheel-header">
                <div className="rw-wh-title">
                  <Gift size={18} color="#d97706" />
                  <h3>UTIM Rewards Spinner</h3>
                </div>
                <span className="rw-slot-count-badge">{modelsList.length} Models</span>
              </div>

              {/* Horizontal Slot Machine */}
              <div className="rw-slot-machine">
                <div className="rw-slot-fade rw-slot-fade-left" />
                <div className="rw-slot-fade rw-slot-fade-right" />
                <div className="rw-slot-pointer-top" />
                <div className="rw-slot-pointer-bottom" />
                <div className={`rw-slot-window ${spinningDone && winResult ? 'rw-slot-window-win' : ''}`} />
                <div className="rw-slot-track-outer">
                  <div
                    ref={slotTrackRef}
                    className="rw-slot-track"
                    style={{
                      transform: `translateX(${slotOffset}px)`,
                      transition: spinning
                        ? `transform ${SPIN_DURATION}ms cubic-bezier(0.05, 0.9, 0.1, 1.0)`
                        : 'none',
                    }}
                  >
                    {slotStrip.map((m, idx) => {
                      let prov = (m.provider || m.model_id.split('/')[0] || '')
                        .replace(/-/g, ' ')
                        .replace(/\b\w/g, c => c.toUpperCase());

                      if (prov.toLowerCase().includes('openrouter')) {
                        const parts = m.model_id.split('/');
                        if (parts.length > 1 && !parts[0].toLowerCase().includes('openrouter')) {
                          prov = parts[0].replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                        } else {
                          prov = 'UTIM AI';
                        }
                      }

                      const cleanName = formatCleanModelName(m.name, m.model_id);

                      const catClass = m.category || 'very_low';
                      const isWinner = spinningDone && winResult && m.model_id === winResult.winning_model?.model_id;
                      return (
                          <div key={idx} className={`rw-slot-card rw-slot-cat-${catClass} ${isWinner ? 'rw-slot-card-winner' : ''}`}>
                            {prov && prov.toLowerCase() !== 'openrouter' && (
                              <span className="rw-slot-prov">{prov}</span>
                            )}
                            <span className="rw-slot-name">{cleanName}</span>
                          </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Spin CTA */}
              <div className="rw-wheel-cta">
                <button
                  className="rw-spin-button"
                  onClick={handleSpinWheel}
                  disabled={spinning || !!activeReward || status.spins_remaining <= 0}
                >
                  {spinning ? (
                    <><RefreshCw className="rw-spin-anim" size={20} /> Spinning...</>
                  ) : activeReward ? (
                    <><Lock size={20} /> WHEEL LOCKED (24H ACTIVE REWARD)</>
                  ) : status.spins_remaining <= 0 ? (
                    <><Lock size={20} /> WHEEL LOCKED (ALL SPINS USED)</>
                  ) : (
                    <><Gift size={20} /> SPIN TO WIN 24H ACCESS</>
                  )}
                </button>

                {activeReward && (
                  <div style={{ marginTop: 12, fontSize: 13, color: '#94a3b8', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                    <Clock size={14} /> The wheel is locked for 24 hours while your reward is active.
                  </div>
                )}
                {!activeReward && status.spins_remaining <= 0 && (
                  <div style={{ marginTop: 12, fontSize: 13, color: '#94a3b8', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                    <Lock size={14} /> All spins used. Fully locked until your subscription cycle ends on {new Date(status.cycle_end).toLocaleDateString()}.
                  </div>
                )}
              </div>

              {/* Win Banner */}
              {winResult && !spinning && (
                <div className="rw-win-banner">
                  <Trophy size={28} color="#f59e0b" />
                  <div>
                    <h3>🎉 YOU WON 24H ACCESS TO:</h3>
                    <h2>{formatCleanModelName(winResult.winning_model.name, winResult.winning_model.model_id)}</h2>
                    <p>All requests use zero quota for the next 24 hours.</p>
                  </div>
                </div>
              )}
            </div>

            <div className="rw-omission-card">
              <div className="rw-oc-header">
                <ShieldCheck size={20} color="var(--accent-brand)" />
                <div>
                  <h3>Model Omission Manager</h3>
                  <p>Select up to <span>{status.max_omissions_allowed} models</span> to remove from your upcoming wheel.</p>
                </div>
              </div>

              {/* Category Filter & Search Bar */}
              <div className="rw-filter-bar">
                <div className="rw-search-box">
                  <Search size={14} color="var(--text-muted)" />
                  <input
                    type="text"
                    placeholder="Search all models..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                <div className="rw-category-tabs">
                  <button className={filterCategory === 'all' ? 'active' : ''} onClick={() => setFilterCategory('all')}>All ({allModels.length})</button>
                  <button className={filterCategory === 'free' ? 'active' : ''} onClick={() => setFilterCategory('free')}>Free</button>
                  <button className={filterCategory === 'very_low' ? 'active' : ''} onClick={() => setFilterCategory('very_low')}>Very Low</button>
                  <button className={filterCategory === 'higher' ? 'active' : ''} onClick={() => setFilterCategory('higher')}>Higher Cost</button>
                  <button className={filterCategory === 'premium' ? 'active' : ''} onClick={() => setFilterCategory('premium')}>Premium</button>
                </div>
              </div>

              {errorMsg && <div className="rw-error-pill">{errorMsg}</div>}

              <div className="rw-omission-chips-grid">
                {filteredModels.map((m) => {
                  const isSelected = selectedOmissions.includes(m.model_id);
                  return (
                    <button
                      key={m.model_id}
                      className={`rw-omission-chip ${isSelected ? 'omitted' : ''}`}
                      onClick={() => handleToggleOmission(m.model_id)}
                    >
                      {isSelected ? <X size={14} /> : <Check size={14} />}
                      <span>{formatCleanModelName(m.name, m.model_id)}</span>
                    </button>
                  );
                })}
              </div>
              <div className="rw-omission-footer">
                <p>Selected <strong>{selectedOmissions.length} of {status.max_omissions_allowed}</strong> allowed omissions. Removing models triggers automatic probability recalculation.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
