import React, { useState, useEffect } from 'react';
import { Cpu, Search, Sparkles, Zap, Shield, Check, ExternalLink, Sliders } from 'lucide-react';
import { getApiUrl } from '../lib/api';

const MODELS = [
  {
    id: 'cohere/north-mini-code:free',
    name: 'North mini code',
    provider: 'Cohere',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'North mini code model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'poolside/laguna-s-2.1:free',
    name: 'Laguna s 2.1',
    provider: 'Poolside',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Laguna s 2.1 model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'google/gemma-4-26b-a4b-it:free',
    name: 'Gemma 4 26b a4b it',
    provider: 'Google',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gemma 4 26b a4b it model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'google/gemma-4-31b-it:free',
    name: 'Gemma 4 31b it',
    provider: 'Google',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gemma 4 31b it model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'openai/gpt-oss-20b:free',
    name: 'Gpt oss 20b',
    provider: 'Openai',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt oss 20b model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'deepseek/deepseek-v4-flash-0731',
    name: 'Deepseek v4 flash 0731',
    provider: 'Deepseek',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Deepseek v4 flash 0731 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'deepseek/deepseek-v4-flash',
    name: 'Deepseek v4 flash',
    provider: 'Deepseek',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Deepseek v4 flash model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'inclusionai/ling-2.6-flash:free',
    name: 'Ling 2.6 flash',
    provider: 'Inclusionai',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Ling 2.6 flash model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'kwaipilot/kat-coder-air-v2.5',
    name: 'Kat coder air v2.5',
    provider: 'Kwaipilot',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Kat coder air v2.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'minimax/minimax-m2.5',
    name: 'Minimax m2.5',
    provider: 'Minimax',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Minimax m2.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'nex-agi/nex-n2-mini',
    name: 'Nex n2 mini',
    provider: 'Nex Agi',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Nex n2 mini model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'xiaomi/mimo-v2.5',
    name: 'Mimo v2.5',
    provider: 'Xiaomi',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Mimo v2.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'deepseek/deepseek-v4-pro',
    name: 'Deepseek v4 pro',
    provider: 'Deepseek',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Deepseek v4 pro model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'inclusionai/ling-2.6-1t',
    name: 'Ling 2.6 1t',
    provider: 'Inclusionai',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Ling 2.6 1t model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'deepseek/deepseek-r1',
    name: 'Deepseek r1',
    provider: 'Deepseek',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Deepseek r1 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'xiaomi/mimo-v2.5-pro',
    name: 'Mimo v2.5 pro',
    provider: 'Xiaomi',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Mimo v2.5 pro model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.6-luna',
    name: 'Gpt 5.6 luna',
    provider: 'Openai',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.6 luna model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.6-luna-pro',
    name: 'Gpt 5.6 luna pro',
    provider: 'Openai',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.6 luna pro model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'qwen/qwen3-next-80b-a3b-instruct',
    name: 'Qwen3 Next 80B',
    provider: 'Qwen',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Qwen3 Next 80B model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'xiaomi/mimo-v2-pro',
    name: 'Mimo v2 pro',
    provider: 'Xiaomi',
    tier: 'hobby',
    category: 'Hobby & Indie',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Mimo v2 pro model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'muses/muse-spark-1.1:free',
    name: 'Muse spark 1.1',
    provider: 'Muses',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Muse spark 1.1 model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'thinkingmachines/inkling-small:free',
    name: 'Inkling',
    provider: 'Thinkingmachines',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Inkling model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'kwaipilot/kat-coder-pro-v2',
    name: 'Kat coder pro v2',
    provider: 'Kwaipilot',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Kat coder pro v2 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'kwaipilot/kat-coder-pro-v2.5',
    name: 'Kat coder pro v2.5',
    provider: 'Kwaipilot',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Kat coder pro v2.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'minimax/minimax-m3',
    name: 'Minimax m3',
    provider: 'Minimax',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Minimax m3 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'moonshot/kimi-k2.5',
    name: 'Kimi k2.5',
    provider: 'Moonshot',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Kimi k2.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.4-mini',
    name: 'Gpt 5.4 mini',
    provider: 'Openai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.4 mini model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'qwen/qwen3.6-plus',
    name: 'Qwen3.6 plus',
    provider: 'Qwen',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Qwen3.6 plus model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'qwen/qwen3.7-plus',
    name: 'Qwen3.7 plus',
    provider: 'Qwen',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Qwen3.7 plus model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'stepfun/step-3.7-flash',
    name: 'Step 3.7 flash',
    provider: 'Stepfun',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Step 3.7 flash model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'z-ai/glm-4.7',
    name: 'Glm 4.7',
    provider: 'Z Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Glm 4.7 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'z-ai/glm-5',
    name: 'Glm 5',
    provider: 'Z Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Glm 5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'z-ai/glm-5.2',
    name: 'Glm 5.2',
    provider: 'Z Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Glm 5.2 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'google/gemini-3.6-flash',
    name: 'Gemini 3.6 flash',
    provider: 'Google',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gemini 3.6 flash model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'minimax/minimax-m2.7',
    name: 'Minimax m2.7',
    provider: 'Minimax',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Minimax m2.7 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'moonshot/kimi-k2.6',
    name: 'Kimi k2.6',
    provider: 'Moonshot',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Kimi k2.6 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'moonshot/kimi-k2.7-code',
    name: 'Kimi k2.7 code',
    provider: 'Moonshot',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Kimi k2.7 code model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'nex-agi/nex-n2-pro:free',
    name: 'Nex n2 pro',
    provider: 'Nex Agi',
    tier: 'free',
    category: 'Free Model',
    cost: '.02 in / .03 out per 1M (.002 in / .003 out Paid)',
    freeCost: '.02 in / .03 out (per 1M tokens)',
    paidCost: '.002 in / .003 out (per 1M tokens)',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Nex n2 pro model for autonomous terminal coding & reasoning.',
    free: true,
  },
  {
    id: 'x-ai/grok-4.20',
    name: 'Grok 4.20',
    provider: 'X Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Grok 4.20 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'x-ai/grok-4.3',
    name: 'Grok 4.3',
    provider: 'X Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Grok 4.3 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'x-ai/grok-build-0.1',
    name: 'Grok build 0.1',
    provider: 'X Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Grok build 0.1 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'z-ai/glm-5-turbo',
    name: 'Glm 5 turbo',
    provider: 'Z Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Glm 5 turbo model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'z-ai/glm-5.1',
    name: 'Glm 5.1',
    provider: 'Z Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Glm 5.1 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'google/gemini-3.5-flash',
    name: 'Gemini 3.5 flash',
    provider: 'Google',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gemini 3.5 flash model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'qwen/qwen3.7-max',
    name: 'Qwen3.7 max',
    provider: 'Qwen',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Qwen3.7 max model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.6-terra',
    name: 'Gpt 5.6 terra',
    provider: 'Openai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.6 terra model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.6-terra-pro',
    name: 'Gpt 5.6 terra pro',
    provider: 'Openai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.6 terra pro model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'qwen/qwen3.8-max',
    name: 'Qwen3.8 max',
    provider: 'Qwen',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Qwen3.8 max model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'x-ai/grok-4.5',
    name: 'Grok 4.5',
    provider: 'X Ai',
    tier: 'pro',
    category: 'Professional Core',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Grok 4.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'moonshot/kimi-k3',
    name: 'Kimi k3',
    provider: 'Moonshot',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Kimi k3 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-sonnet-5',
    name: 'Claude sonnet 5',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude sonnet 5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'google/gemini-3.1-pro-preview',
    name: 'gemini-3.1-pro-preview',
    provider: 'Google',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'gemini-3.1-pro-preview model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-opus-4.5',
    name: 'Claude opus 4.5',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude opus 4.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-opus-4.6',
    name: 'Claude opus 4.6',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude opus 4.6 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-opus-4.7',
    name: 'Claude opus 4.7',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude opus 4.7 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-opus-4.8',
    name: 'Claude opus 4.8',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude opus 4.8 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-sonnet-4.5',
    name: 'Claude sonnet 4.5',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude sonnet 4.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-sonnet-4.6',
    name: 'Claude sonnet 4.6',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude sonnet 4.6 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.4',
    name: 'Gpt 5.4',
    provider: 'Openai',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.4 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-fable-5',
    name: 'Claude fable 5',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude fable 5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.3-codex',
    name: 'Gpt 5.3 codex',
    provider: 'Openai',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.3 codex model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.5',
    name: 'Gpt 5.5',
    provider: 'Openai',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'anthropic/claude-opus-5',
    name: 'Claude opus 5',
    provider: 'Anthropic',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Claude opus 5 model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'google/gemini-3.1-pro-preview-customtools',
    name: 'Gemini 3.1 pro preview',
    provider: 'Google',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gemini 3.1 pro preview model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.6-sol',
    name: 'Gpt 5.6 sol',
    provider: 'Openai',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.6 sol model for autonomous terminal coding & reasoning.',
    free: false,
  },
  {
    id: 'openai/gpt-5.6-sol-pro',
    name: 'Gpt 5.6 sol pro',
    provider: 'Openai',
    tier: 'ultimate',
    category: 'Ultimate Heavy',
    cost: ' in /  out per 1M',
    context: '256,000 tokens',
    maxOutput: '32,768 tokens',
    speed: 'High Throughput',
    recommendedFor: 'Gpt 5.6 sol pro model for autonomous terminal coding & reasoning.',
    free: false,
  },
];


export default function ModelRegistryExplorer() {
  const [selectedTier, setSelectedTier] = useState('all'); // 'all' | 'free' | 'hobby' | 'pro' | 'ultimate'
  const [searchQuery, setSearchQuery] = useState('');
  const [modelsList, setModelsList] = useState(MODELS);
  const [isLiveSynced, setIsLiveSynced] = useState(false);

  useEffect(() => {
    async function fetchServerModels() {
      try {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/api/models`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            const formatted = data.map((m) => {
              const isFree = m.is_free || m.model_id.endsWith(':free');
              const tier = isFree 
                ? 'free' 
                : (m.is_reasoning || (m.context_window && m.context_window >= 1000000) 
                  ? (m.model_id.includes('opus') || m.model_id.includes('gpt-5.6') ? 'ultimate' : 'pro') 
                  : 'hobby');
              
              return {
                id: m.model_id,
                name: m.name || m.model_id,
                provider: m.provider || (m.model_id.includes('/') ? m.model_id.split('/')[0].toUpperCase() : 'UTIM DB'),
                tier: tier,
                category: isFree ? 'Free Model' : (tier === 'ultimate' ? 'Ultimate Heavy' : (tier === 'pro' ? 'Professional Core' : 'Hobby & Indie')),
                cost: isFree ? '$0.02 in / $0.03 out per 1M ($0.002 in / $0.003 out Paid)' : 'Priority Model DB Rate',
                freeCost: isFree ? '$0.02 in / $0.03 out (per 1M tokens)' : null,
                paidCost: isFree ? '$0.002 in / $0.003 out (per 1M tokens)' : null,
                context: m.context_window ? `${m.context_window.toLocaleString()} tokens` : '256,000 tokens',
                maxOutput: m.max_output_tokens ? `${m.max_output_tokens.toLocaleString()} tokens` : '32,768 tokens',
                speed: m.is_vision ? 'Multimodal Vision Engine' : (m.is_reasoning ? 'Deep Reasoning Engine' : 'High Throughput'),
                recommendedFor: m.description || (isFree ? 'Default free reasoning & agent execution model.' : 'Premium server DB model for high-depth code synthesis.'),
                free: isFree,
              };
            });
            setModelsList(formatted);
            setIsLiveSynced(true);
          }
        }
      } catch (err) {
        console.warn('Using verified fallback server models:', err);
      }
    }
    fetchServerModels();
  }, []);

  const filteredModels = modelsList.filter((m) => {
    const matchesTier = selectedTier === 'all' || m.tier === selectedTier;
    const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          m.provider.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          m.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          m.recommendedFor.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTier && matchesSearch;
  });

  return (
    <section className="st-model-registry-section" style={{ padding: '80px 24px' }}>
      <div className="st-container">
        
        {/* Section Header */}
        <div className="st-section-header">
          <div className="st-hero-badge">
            {isLiveSynced ? '🟢 SYNCED WITH SERVER MODEL DB' : 'MODEL REGISTRY & COST COMPUTATION (66 MODELS)'}
          </div>
          <h2 className="st-section-title">
            Available Models &amp; Routing Registry
          </h2>
          <p className="st-section-subtitle">
            All models displayed are active on UTIM server database. Select any model directly in your CLI using <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-cream-alt)', padding: '2px 8px', borderRadius: 4 }}>/model &lt;model_id&gt;</code>.
          </p>
        </div>

        {/* Filter Controls Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
          background: '#FFFFFF',
          border: '1px solid var(--border-cream)',
          borderRadius: 12,
          padding: '12px 18px',
          marginBottom: 28,
          boxShadow: 'var(--shadow-xs)'
        }}>
          {/* Tier Tabs */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {[
              { id: 'all', label: 'All Models' },
              { id: 'free', label: 'Free Models ($0.02 / $0.03)' },
              { id: 'hobby', label: 'Hobby & Indie' },
              { id: 'pro', label: 'Pro Cores' },
              { id: 'ultimate', label: 'Ultimate Heavy' },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setSelectedTier(t.id)}
                style={{
                  padding: '7px 14px',
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: 'pointer',
                  border: selectedTier === t.id ? '1px solid var(--accent-black)' : '1px solid transparent',
                  background: selectedTier === t.id ? 'var(--accent-black)' : 'transparent',
                  color: selectedTier === t.id ? '#FFFFFF' : 'var(--text-secondary)',
                  transition: 'all 0.15s ease'
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Search Bar */}
          <div style={{ position: 'relative', minWidth: 240 }}>
            <Search size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search model, provider..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '7px 12px 7px 32px',
                borderRadius: 8,
                border: '1px solid var(--border-cream)',
                fontSize: 13,
                outline: 'none',
                background: 'var(--bg-cream)'
              }}
            />
          </div>
        </div>

        {/* Model Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
          {filteredModels.map((m, idx) => (
            <div
              key={idx}
              className="st-model-card"
              style={{
                background: '#FFFFFF',
                border: '1px solid var(--border-cream)',
                borderRadius: 14,
                padding: '22px',
                boxShadow: 'var(--shadow-xs)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'all 0.2s ease'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                    {m.provider}
                  </span>
                  {m.free ? (
                    <span style={{ fontSize: 11, fontWeight: 800, color: '#059669', background: 'rgba(16,185,129,0.1)', padding: '2px 8px', borderRadius: 4 }}>
                      FREE MODEL
                    </span>
                  ) : (
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', background: 'var(--bg-cream-surface)', padding: '2px 8px', borderRadius: 4 }}>
                      {m.category}
                    </span>
                  )}
                </div>

                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6 }}>
                  {m.name}
                </h3>

                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 14 }}>
                  {m.recommendedFor}
                </p>
              </div>

              <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                  <span>Context Window</span>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{m.context}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                  <span>Speed</span>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{m.speed}</span>
                </div>
                
                {m.free ? (
                  <div style={{ marginTop: 8, padding: '8px 10px', background: 'var(--bg-cream)', borderRadius: 6, border: '1px solid var(--border-cream)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>
                      <span>Free Users Rate</span>
                      <span style={{ fontWeight: 800, color: '#059669' }}>$0.02 in / $0.03 out / 1M</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)' }}>
                      <span>Paid Users (10x Discount)</span>
                      <span style={{ fontWeight: 800, color: 'var(--accent-black)' }}>$0.002 in / $0.003 out / 1M</span>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                    <span>Compute Cost</span>
                    <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{m.cost}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
}
