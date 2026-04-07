"""
Layer 2 – AI Brain
Uses the Claude API to estimate true probabilities for each market question.
Prompt is loaded from prompts/v7_market_analysis.txt.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import anthropic

from bot.logger import setup_logger
from config import config

logger = setup_logger(__name__)

_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "prompts", "v7_market_analysis.txt"
)


@dataclass
class Analysis:
    probability: float
    confidence: str          # "high" | "medium" | "low"
    base_rate: float
    reasoning: str
    edge: float              # abs(ai_prob - market_price)


class MarketAnalyzer:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        with open(_PROMPT_PATH) as f:
            self._prompt_template = f.read()
        logger.info("MarketAnalyzer initialised (model: %s)", config.CLAUDE_MODEL)

    async def analyse(
        self,
        question: str,
        yes_price: float,
        no_price: float,
        volume: float,
    ) -> Optional[Analysis]:
        prompt = self._prompt_template.format(
            question=question,
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
        )
        try:
            response = self._client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            return self._parse(raw, yes_price)
        except anthropic.APIError as exc:
            logger.error("Claude API error for '%s': %s", question[:60], exc)
            return None
        except Exception as exc:
            logger.error("Unexpected error analysing '%s': %s", question[:60], exc)
            return None

    def _parse(self, raw: str, yes_price: float) -> Optional[Analysis]:
        try:
            data = json.loads(raw)
            probability = float(data["probability"])
            # Clamp to valid range
            probability = max(0.01, min(0.99, probability))
            edge = abs(probability - yes_price)
            return Analysis(
                probability=probability,
                confidence=data.get("confidence", "low"),
                base_rate=float(data.get("base_rate", probability)),
                reasoning=data.get("reasoning", ""),
                edge=edge,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Failed to parse Claude response: %s | raw: %s", exc, raw[:200])
            return None
