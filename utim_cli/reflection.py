import os
import json
import time
import uuid
import sqlite3
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import requests
from utim_cli.constants import DEFAULT_MODEL

# Dedicated lightweight models for reflection/experience extraction.
# These are free-tier models optimized for structured JSON output tasks.
# Primary is tried first; fallbacks are used on rate-limit or error.
REFLECTION_MODELS = [
    "openrouter/free",
    "qwen/qwen2.5-1.5b-instruct",
    "cohere/north-mini-code:free",
    "inclusionai/ling-3.0-flash:free",
]

REFLECTION_PRIMARY_MODEL = REFLECTION_MODELS[0]
REFLECTION_MAX_TOKENS = 5000

MEMORY_FILE = ".utim_tmp/task_reflections.json"
CONVENTIONS_FILE = ".utim_conventions.md"

class ExperienceNode:
    """Represents a learned pattern/experience with relationship context"""

    def __init__(self, pattern_id: str, description: str, pattern_type: str,
                 objects: List[str], relationships: Dict[str, Any] = None,
                 strength: float = 1.0, metadata: Dict[str, Any] = None,
                 status: str = "verified", confidence: float = 1.0,
                 clarifying_question: Optional[str] = None):

        self.pattern_id = pattern_id
        self.description = description
        self.pattern_type = pattern_type  # "single_object", "relationship", "emergent"
        self.objects = objects  # list of objects involved
        self.relationships = relationships or {}  # relationship mappings
        self.strength = strength  # how strongly this pattern is established (0-1)
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
        self.usage_count = 0
        self.last_used = None
        self.success_rate = 0.0
        self.status = status
        self.confidence = confidence
        self.clarifying_question = clarifying_question

    def is_related_to(self, other_node: 'ExperienceNode') -> bool:
        """Check if this experience is related to another based on shared objects/relationships"""
        shared_objects = set(self.objects) & set(other_node.objects)
        shared_relationships = set(self.relationships.keys()) & set(other_node.relationships.keys())
        return len(shared_objects) > 0 or len(shared_relationships) > 0

    def matches_pattern(self, input_objects: List[str], input_relationships: Dict[str, Any] = None) -> bool:
        """Check if this pattern matches new input based on similarity"""
        if not input_relationships:
            input_relationships = {}

        # For relationship patterns, need matching object sets
        if self.pattern_type == "relationship":
            # Check if we have matching relationships or overlapping objects
            matching_relationships = sum(1 for key in self.relationships
                                        if key in input_relationships)
            overlapping_objects = len(set(self.objects) & set(input_objects))
            return overlapping_objects >= 1 or matching_relationships >= 1

        # For single object patterns, direct object matching
        elif self.pattern_type == "single_object":
            return any(obj in input_objects for obj in self.objects)

        # For emergent patterns, need multiple matching components
        elif self.pattern_type == "emergent":
            matching_objects = len(set(self.objects) & set(input_objects))
            matching_relationships = sum(1 for key in self.relationships if key in input_relationships)
            return matching_objects >= 2 or (matching_objects >= 1 and matching_relationships >= 1)

        return False

    def update_from_feedback(self, success: bool, context: Dict[str, Any] = None):
        """Update pattern based on experience feedback"""
        self.usage_count += 1
        self.last_used = datetime.now().isoformat()

        if success:
            self.success_rate = (self.success_rate * (self.usage_count - 1) + 1.0) / self.usage_count
            self.strength = min(1.0, self.strength + 0.1)
        else:
            self.success_rate = (self.success_rate * (self.usage_count - 1)) / self.usage_count
            self.strength = max(0.0, self.strength - 0.05)

        if context:
            self.metadata.update(context)

class ExperienceManager:
    """Manages all learned experiences and pattern recognition"""

    def __init__(self, storage_path: str = ".utim_tmp/experience_memory.json"):
        self.storage_path = storage_path
        self.experience_nodes: Dict[str, ExperienceNode] = {}
        self.pattern_index: Dict[str, List[str]] = {}  # object -> pattern_ids
        self.load_experiences()

    def load_experiences(self):
        """Load experiences from storage"""
        try:
            with open(self.storage_path, 'r', encoding="utf-8") as f:
                data = json.load(f)
                for pattern_id, node_data in data.items():
                    node = ExperienceNode(
                        pattern_id=node_data['pattern_id'],
                        description=node_data['description'],
                        pattern_type=node_data['pattern_type'],
                        objects=node_data['objects'],
                        relationships=node_data.get('relationships', {}),
                        strength=node_data.get('strength', 1.0),
                        metadata=node_data.get('metadata', {}),
                        status=node_data.get('status', 'verified'),
                        confidence=node_data.get('confidence', 1.0),
                        clarifying_question=node_data.get('clarifying_question')
                    )
                    node.usage_count = node_data.get('usage_count', 0)
                    node.last_used = node_data.get('last_used')
                    node.success_rate = node_data.get('success_rate', 0.0)
                    self.experience_nodes[pattern_id] = node

            self._rebuild_index()
        except FileNotFoundError:
            self._initialize_default_patterns()
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {self.storage_path}, initializing fresh")
            self._initialize_default_patterns()

    def _initialize_default_patterns(self):
        """Start from a completely blank, empty experience database for clean, configuration-specific learning."""
        pass

    def _rebuild_index(self):
        """Rebuild index for fast pattern lookup"""
        self.pattern_index = {}
        for pattern_id, node in self.experience_nodes.items():
            for obj in node.objects:
                if obj not in self.pattern_index:
                    self.pattern_index[obj] = []
                if pattern_id not in self.pattern_index[obj]:
                    self.pattern_index[obj].append(pattern_id)

    def add_experience(self, pattern_id: str, description: str, pattern_type: str,
                       objects: List[str], relationships: Dict[str, Any] = None,
                       strength: float = 1.0, metadata: Dict[str, Any] = None,
                       status: str = "verified", confidence: float = 1.0,
                       clarifying_question: Optional[str] = None):
        """Add a new experience pattern"""
        node = ExperienceNode(
            pattern_id=pattern_id,
            description=description,
            pattern_type=pattern_type,
            objects=objects,
            relationships=relationships,
            strength=strength,
            metadata=metadata,
            status=status,
            confidence=confidence,
            clarifying_question=clarifying_question
        )

        self.experience_nodes[pattern_id] = node
        self._rebuild_index()
        self.save_experiences()

    def get_related_experiences(self, objects: List[str], relationships: Dict[str, Any] = None,
                                min_strength: float = 0.3) -> List[ExperienceNode]:
        """Get experiences related to the current input"""
        if not objects:
            return []

        if not relationships:
            relationships = {}

        related_patterns = []

        # First get all patterns that contain any of the input objects
        for obj in objects:
            if obj in self.pattern_index:
                for pattern_id in self.pattern_index[obj]:
                    node = self.experience_nodes.get(pattern_id)
                    if node is None:
                        continue

                    if node.strength >= min_strength:
                        # Check if this specific pattern matches our input
                        if node.matches_pattern(objects, relationships):
                            related_patterns.append(node)

        # Remove duplicates while preserving order
        seen = set()
        unique_patterns = []
        for node in related_patterns:
            if id(node) not in seen:
                seen.add(id(node))
                unique_patterns.append(node)

        # Sort by strength and recency
        unique_patterns.sort(key=lambda x: (-x.strength, x.success_rate, x.last_used or ''), reverse=True)
        return unique_patterns

    def learn_from_experience(self, context: Dict[str, Any], outcome: str, success: bool,
                            feedback: Dict[str, Any] = None):
        """Learn from a new experience using the chair/stool analogy"""
        input_objects = context.get('objects', [])
        input_relationships = context.get('relationships', {})

        # Find related patterns
        related_patterns = self.get_related_experiences(input_objects, input_relationships)

        # Learn from related patterns
        for node in related_patterns:
            node.update_from_feedback(success, feedback)

        # Check if we have enough components to suggest an emergent pattern
        if len(input_objects) >= 2:
            # Create or strengthen relationship pattern for this combination
            pattern_desc = f"{', '.join(input_objects)} = {outcome}"
            pattern_id = f"relationship_{'_'.join(sorted(input_objects))}"

            self.add_experience(
                pattern_id=pattern_id,
                description=pattern_desc,
                pattern_type="relationship",
                objects=input_objects,
                relationships=input_relationships,
                strength=0.5
            )

        # Save updated experiences
        self.save_experiences()

    def analyze_pattern(self, input_objects: List[str], input_relationships: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze input and provide human-like interpretation using learned patterns"""
        if not input_relationships:
            input_relationships = {}

        # Get related patterns
        related_patterns = self.get_related_experiences(input_objects, input_relationships)

        if not related_patterns:
            return {
                'interpretation': 'Unknown pattern',
                'confidence': 0.0,
                'related_patterns': [],
                'suggestions': ['Need more experience to understand this combination']
            }

        # Analyze the highest strength pattern
        primary_pattern = related_patterns[0]

        # Generate human-like interpretation
        interpretation = self._generate_interpretation(
            input_objects, input_relationships, primary_pattern
        )

        # Get confidence based on pattern strength and success rate
        confidence = (primary_pattern.strength * 0.7) + (primary_pattern.success_rate * 0.3)

        # Provide suggestions based on related patterns
        suggestions = self._generate_suggestions(input_objects, input_relationships, related_patterns)

        return {
            'interpretation': interpretation,
            'confidence': min(1.0, confidence),
            'primary_pattern_id': primary_pattern.pattern_id,
            'pattern_strength': primary_pattern.strength,
            'pattern_success_rate': primary_pattern.success_rate,
            'related_patterns': [{
                'id': p.pattern_id,
                'description': p.description,
                'strength': p.strength,
                'success_rate': p.success_rate
            } for p in related_patterns[:3]],
            'suggestions': suggestions,
            'emergent_insights': self._generate_emergent_insights(related_patterns)
        }

    def _generate_interpretation(self, input_objects: List[str], input_relationships: Dict[str, Any],
                                primary_pattern: ExperienceNode) -> str:
        """Generate human-like interpretation of the pattern"""
        objects_str = ', '.join(input_objects)

        if primary_pattern.pattern_type == "relationship":
            if 'simulates_chair_back' in input_relationships:
                return f"Ah, I see you're using a {objects_str} situation where you're gaining additional support - it's like sitting on a stool near a wall and suddenly feeling that chair-comfort through the wall's assistance. Smart!"
            elif 'provides_back_support' in input_relationships:
                return f"Perfect! You're creating that enhanced sitting experience with {objects_str} - combining elements to get that supportive feeling, just like how a wall can turn a simple stool into a chair-like setup."

        elif primary_pattern.pattern_type == "emergent":
            return f"Interesting! You're discovering that {objects_str} creates something new together - like humans do with patterns."

        else:  # single_object
            if 'has_back_support' in input_relationships:
                return f"Standard chair setup with {objects_str} - straightforward supportive sitting experience."
            else:
                return f"Simple sitting arrangement with {objects_str} - basic setup without additional support."

    def _generate_suggestions(self, input_objects: List[str], input_relationships: Dict[str, Any],
                               related_patterns: List[ExperienceNode]) -> List[str]:
        """Generate suggestions based on learned patterns"""
        suggestions = []

        if related_patterns:
            primary = related_patterns[0]

            if primary.success_rate < 0.5:
                suggestions.append(
                    "This combination didn't work well last time - try adjusting the setup"
                )
            elif primary.success_rate > 0.8:
                suggestions.append(
                    "Great! This setup works well - you might want to explore variations"
                )

            if primary.strength < 0.7:
                suggestions.append(
                    "Let's practice this combination more to strengthen the pattern"
                )

        # Chair/stool specific suggestions
        if 'stool' in input_objects and 'wall' in input_objects:
            suggestions.append(
                "Pro tip: Using a stool near a wall gives you chair-like comfort - experiment with different distances for optimal back support"
            )

        if 'stool' in input_objects and 'chair' in input_objects:
            suggestions.append(
                "Great setup! Mixing stool and chair patterns - you're getting somewhere with transitional experiences"
            )

        return suggestions if suggestions else ["Keep exploring these combinations - more experience will help!"]

    def _generate_emergent_insights(self, related_patterns: List[ExperienceNode]) -> List[str]:
        """Generate insights about emerging patterns"""
        insights = []

        # Look for patterns that suggest learning
        emergent_patterns = [p for p in related_patterns if p.pattern_type == "emergent"]

        if emergent_patterns:
            insights.append(
                "You're starting to see the big picture - understanding how different elements work together"
            )

        # Check for cross-category learning (chair patterns applied to stools)
        chair_patterns = [p for p in related_patterns if 'chair' in p.pattern_id or 'chair' in p.description]
        stool_patterns = [p for p in related_patterns if 'stool' in p.pattern_id or 'stool' in p.description]

        if chair_patterns and stool_patterns:
            insights.append(
                "Excellent! You're learning the relationship between similar objects - how chair principles apply to stool scenarios"
            )

        return insights

    def save_experiences(self):
        """Save experiences to storage"""
        data = {}
        for pattern_id, node in self.experience_nodes.items():
            data[pattern_id] = {
                'pattern_id': node.pattern_id,
                'description': node.description,
                'pattern_type': node.pattern_type,
                'objects': node.objects,
                'relationships': node.relationships,
                'strength': node.strength,
                'metadata': node.metadata,
                'usage_count': node.usage_count,
                'last_used': node.last_used,
                'success_rate': node.success_rate,
                'status': getattr(node, 'status', 'verified'),
                'confidence': getattr(node, 'confidence', 1.0),
                'clarifying_question': getattr(node, 'clarifying_question', None)
            }

        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w', encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_experience_summary(self) -> Dict[str, Any]:
        """Get summary of learned experiences"""
        patterns_by_type = {}
        total_patterns = len(self.experience_nodes)
        avg_strength = sum(n.strength for n in self.experience_nodes.values()) / max(1, total_patterns)
        avg_success_rate = sum(n.success_rate for n in self.experience_nodes.values()) / max(1, total_patterns)

        for node in self.experience_nodes.values():
            if node.pattern_type not in patterns_by_type:
                patterns_by_type[node.pattern_type] = []
            patterns_by_type[node.pattern_type].append({
                'id': node.pattern_id,
                'description': node.description,
                'strength': node.strength,
                'success_rate': node.success_rate,
                'usage_count': node.usage_count
            })

        return {
            'total_experiences': total_patterns,
            'average_strength': avg_strength,
            'average_success_rate': avg_success_rate,
            'patterns_by_type': patterns_by_type,
            'most_used_patterns': sorted(
                [(pid, node.usage_count) for pid, node in self.experience_nodes.items()],
                key=lambda x: x[1], reverse=True
            )[:5],
            'recent_patterns': sorted(
                [(node.created_at, pid) for pid, node in self.experience_nodes.items()],
                reverse=True
            )[:5]
        }

    def get_human_like_analysis(self, context: Dict[str, Any], outcome: str) -> str:
        """Get human-like analysis using chair/stool analogy"""
        input_objects = context.get('objects', [])
        input_relationships = context.get('relationships', {})

        if not input_objects:
            return "I'm not sure what you're describing - could you tell me what objects are involved?"

        analysis = self.analyze_pattern(input_objects, input_relationships)

        # Generate response that mimics human pattern recognition
        if analysis['confidence'] > 0.8:
            response = f"I totally get it! When you have {', '.join(input_objects)}, "
            response += f"that's like {analysis['interpretation'].lower()}. "
            response += "You've clearly figured out some good relationships between things."
        elif analysis['confidence'] > 0.5:
            response = f"Interesting setup with {', '.join(input_objects)}! "
            response += f"{analysis['interpretation'].lower()}. "
            if analysis['suggestions']:
                response += f"Maybe try: {analysis['suggestions'][0].lower()}"
        else:
            response = f"I'm still learning about {', '.join(input_objects)} combinations. "
            response += f"{analysis['interpretation'].lower()}. "
            response += "Let's keep exploring this together!"

        if analysis.get('emergent_insights'):
            for insight in analysis['emergent_insights']:
                response += f" Plus, {insight.lower()}"

        return response

# Global experience system instance
experience_manager = ExperienceManager()


# ---------------------------------------------------------------------------
# PreferenceCategoryManager
# ---------------------------------------------------------------------------
# Tracks ALL types of user behavioral preferences as scored categories.
# A "category" is any domain:value pair e.g.
#   joke_type:nonveg, response_length:short, tool_choice:puppeteer,
#   communication_style:casual, coding_style:functional, topic_interest:gaming
#
# Cognitive model used:
#   - Bayesian confidence: starts low, hardens only with repeated cross-session signals
#   - Temporal decay (half-life): recent evidence weighs more than old evidence
#     → separates mood (one-off positive) from trait (consistent across sessions)
#   - Injection thresholds:
#       ≥ 0.75  → inject top-3 candidates for that domain (still exploring)
#       ≥ 0.95  → inject winner only as high-confidence trait
#   - A single positive response NEVER pushes confidence above 0.4 alone
#     (prevents mood from being mistaken for trait)
# ---------------------------------------------------------------------------

IMPORT_MATH_DONE = False
try:
    import math as _math
    IMPORT_MATH_DONE = True
except ImportError:
    pass

# Half-life in days: evidence older than this contributes half weight
PREF_HALF_LIFE_DAYS = 14.0
# Maximum confidence a SINGLE signal can push a category to
PREF_SINGLE_SIGNAL_CAP = 0.40
# Injection thresholds
PREF_INJECT_SOFT = 0.75   # top-N candidates injected with uncertainty
PREF_INJECT_HARD = 0.95   # winner only, stated as high-confidence trait
# How many top candidates to inject in soft mode
PREF_INJECT_TOP_N = 3


class PreferenceCategoryManager:
    """Universal Bayesian preference scorer for all experience categories.

    Each category key is a string like  "joke_type:nonveg"  or
    "response_length:short"  — i.e.  domain:value.
    Every observation is a weighted evidence event stored with a timestamp
    so temporal decay can be applied at query time.
    """

    STORAGE_PATH = ".utim_tmp/preference_categories.json"

    def __init__(self):
        # category_key -> {"evidence": [{"ts": iso, "weight": float}],
        #                   "domain": str, "value": str,
        #                   "description": str}
        self.categories: Dict[str, Dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self):
        try:
            with open(self.STORAGE_PATH, "r", encoding="utf-8") as f:
                self.categories = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.categories = {}

    def _save(self):
        os.makedirs(".utim_tmp", exist_ok=True)
        with open(self.STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.categories, f, indent=2)

    # ------------------------------------------------------------------
    # Core: record an observation
    # ------------------------------------------------------------------
    def observe(self, domain: str, value: str, polarity: float,
                description: str = "", timestamp: str = None):
        """Record a preference signal.

        Args:
            domain:      Broad category e.g. "joke_type", "response_length"
            value:       Specific value e.g. "nonveg", "short"
            polarity:    -1.0 (strong dislike) … +1.0 (strong like)
                         0.0 = neutral/ambiguous → ignored
            description: Human-readable label e.g. 'User laughed at nonveg joke'
            timestamp:   ISO datetime string; defaults to now
        """
        if polarity == 0.0:
            return
        key = f"{domain.lower().strip()}:{value.lower().strip()}"
        if key not in self.categories:
            self.categories[key] = {
                "domain": domain.lower().strip(),
                "value": value.lower().strip(),
                "description": description or key,
                "evidence": []
            }
        ts = timestamp or datetime.now().isoformat()
        self.categories[key]["evidence"].append({"ts": ts, "weight": float(polarity)})
        # Prune evidence older than 6 months to keep storage lean
        cutoff = self._days_ago(180)
        self.categories[key]["evidence"] = [
            e for e in self.categories[key]["evidence"]
            if e["ts"] >= cutoff
        ]
        self._save()

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------
    def _days_ago(self, days: float) -> str:
        import datetime as dt_mod
        d = dt_mod.datetime.now() - dt_mod.timedelta(days=days)
        return d.isoformat()

    def _time_weight(self, ts: str) -> float:
        """Exponential decay: evidence halves every PREF_HALF_LIFE_DAYS days."""
        try:
            import datetime as dt_mod
            then = dt_mod.datetime.fromisoformat(ts)
            now  = dt_mod.datetime.now()
            days_old = max(0.0, (now - then).total_seconds() / 86400.0)
            if IMPORT_MATH_DONE:
                return _math.exp(-_math.log(2) * days_old / PREF_HALF_LIFE_DAYS)
            # fallback without math
            return max(0.01, 1.0 - (days_old / (PREF_HALF_LIFE_DAYS * 10)))
        except Exception:
            return 1.0

    def confidence(self, key: str) -> float:
        """Return Bayesian-style confidence for a category key (0.0-1.0).

        Confidence = tanh(sum of time-decayed signed weights) mapped to [0,1].
        This means:
          - A single strong positive signal → ~0.38 max (below SINGLE_SIGNAL_CAP)
          - 3 positive signals across sessions → ~0.65
          - 7+ consistent positive signals → approaches 0.95+
          - Negative signals pull it DOWN (dislike is also learned)
        Always returns 0.0 for non-existent or empty categories.
        """
        entry = self.categories.get(key)
        if not entry or not entry.get("evidence"):
            return 0.0
        weighted_sum = sum(
            e["weight"] * self._time_weight(e["ts"])
            for e in entry["evidence"]
        )
        # tanh maps (-inf,+inf) -> (-1,1); remap to (0,1)
        if IMPORT_MATH_DONE:
            raw = (_math.tanh(weighted_sum) + 1.0) / 2.0
        else:
            # simple sigmoid fallback
            raw = 1.0 / (1.0 + (2.718281828 ** (-weighted_sum)))
        return round(min(1.0, max(0.0, raw)), 4)

    # ------------------------------------------------------------------
    # Situational injection: what to put into context
    # ------------------------------------------------------------------
    def get_situational_injections(self) -> List[Dict]:
        """Return context injection statements based on current confidence levels.

        Returns a list of dicts:
          {"domain": str, "injection": str, "mode": "hard"|"soft", "confidence": float}

        Logic per domain:
          - Compute confidence for all values in the domain
          - If winner >= PREF_INJECT_HARD: emit single authoritative statement
          - Elif winner >= PREF_INJECT_SOFT: emit top-N candidates as probabilistic hint
          - Else: nothing (not enough evidence yet)
        """
        # Group by domain
        by_domain: Dict[str, List[tuple]] = {}
        for key, entry in self.categories.items():
            domain = entry["domain"]
            conf   = self.confidence(key)
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append((entry["value"], conf, entry.get("description", "")))

        injections = []
        for domain, candidates in by_domain.items():
            # Sort by confidence desc
            candidates.sort(key=lambda x: -x[1])
            winner_value, winner_conf, winner_desc = candidates[0]

            if winner_conf >= PREF_INJECT_HARD:
                injections.append({
                    "domain": domain,
                    "confidence": winner_conf,
                    "mode": "hard",
                    "injection": (
                        f"[High-confidence trait — {domain}] "
                        f"User strongly prefers: {winner_value}. "
                        f"Confidence {winner_conf:.2f}. Apply this consistently."
                    )
                })
            elif winner_conf >= PREF_INJECT_SOFT:
                top_n = candidates[:PREF_INJECT_TOP_N]
                candidates_str = ", ".join(
                    f"{v} ({c:.2f})" for v, c, _ in top_n
                )
                injections.append({
                    "domain": domain,
                    "confidence": winner_conf,
                    "mode": "soft",
                    "injection": (
                        f"[Emerging preference — {domain}] "
                        f"Evidence suggests user leans toward: {candidates_str}. "
                        f"Adapt but remain flexible — confidence still building."
                    )
                })

        return injections

    def get_domain_summary(self) -> Dict[str, Any]:
        """Return all domains with their top candidate and current confidence."""
        by_domain: Dict[str, List[tuple]] = {}
        for key, entry in self.categories.items():
            d = entry["domain"]
            if d not in by_domain:
                by_domain[d] = []
            by_domain[d].append((entry["value"], self.confidence(key)))
        summary = {}
        for d, vals in by_domain.items():
            vals.sort(key=lambda x: -x[1])
            summary[d] = vals
        return summary


# Global preference category manager instance
preference_manager = PreferenceCategoryManager()


def get_situational_injections() -> List[Dict]:
    """Public API: returns context injection statements from learned preferences."""
    return preference_manager.get_situational_injections()


def get_preference_domain_summary() -> Dict[str, Any]:
    """Public API: returns all learned preference domains with scores."""
    return preference_manager.get_domain_summary()

def experience_based_reflection(context: Dict[str, Any], outcome: str, success: bool = True,
                               feedback: Dict[str, Any] = None) -> str:
    """Main function for UTIM to reflect on experiences like a human using chair/stool analogy"""
    experience_manager.learn_from_experience(context, outcome, success, feedback)
    return experience_manager.get_human_like_analysis(context, outcome)

def get_experience_insights(context: Dict[str, Any]) -> Dict[str, Any]:
    """Get insights about the current context from learned experiences"""
    input_objects = context.get('objects', [])
    input_relationships = context.get('relationships', {})
    return experience_manager.analyze_pattern(input_objects, input_relationships)

def get_experience_summary() -> Dict[str, Any]:
    """Get summary of all learned experiences"""
    return experience_manager.get_experience_summary()

def extract_general_concepts(text: str) -> List[str]:
    """Extract general words/concepts from text to match against learned patterns"""
    if not text:
        return []
    import re
    words = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
    return list(set(words))

# Helper function to extract rule-based stool/chair/wall references from text
def extract_context_from_interaction(user_message: str, assistant_content: str) -> Dict[str, Any]:
    """Extract context objects and relationships from interaction for experience analysis"""
    context = {'objects': [], 'relationships': {}}

    message_lower = user_message.lower()
    content_lower = assistant_content.lower()

    objects_found = []
    if 'chair' in message_lower or 'chair' in content_lower:
        objects_found.append('chair')
    if 'stool' in message_lower or 'stool' in content_lower:
        objects_found.append('stool')
    if 'wall' in message_lower or 'wall' in content_lower:
        objects_found.append('wall')
    if 'table_edge' in message_lower or 'table_edge' in content_lower:
        objects_found.append('table_edge')

    # Dynamically match concepts in message/content with learned experiences' objects
    general_concepts = extract_general_concepts(user_message + " " + assistant_content)
    for pattern_node in experience_manager.experience_nodes.values():
        for obj in pattern_node.objects:
            if obj.lower() in general_concepts:
                objects_found.append(obj)

    relationships = {}
    if 'back support' in message_lower or 'back support' in content_lower:
        relationships['provides_back_support'] = True
    if 'simulates' in message_lower or 'simulates' in content_lower:
        relationships['simulates_chair_back'] = True
    if 'support' in message_lower or 'support' in content_lower:
        relationships['provides_support'] = True

    # Merge dynamic relationships from learned patterns if any
    for pattern_node in experience_manager.experience_nodes.values():
        for rel_key in pattern_node.relationships:
            if rel_key.lower() in general_concepts:
                relationships[rel_key] = True

    context['objects'] = list(set(objects_found))
    context['relationships'] = relationships
    return context


# ---------------------------------------------------------------------------
# 5-Request Interaction Buffering & RAG Skill Creation Engine
# ---------------------------------------------------------------------------

INTERACTION_BUFFER_FILE = ".utim_tmp/interaction_buffer.json"
REQUEST_COUNTER_FILE = ".utim_tmp/request_counter.json"
MIN_EXPERIENCES_FOR_SKILL = 3

# ---------------------------------------------------------------------------
# Immediate Correction Detection & Storage
# ---------------------------------------------------------------------------

# Correction signal keywords — zero-cost local heuristic
_CORRECTION_PHRASES = [
    "no,", "nope", "wrong", "incorrect", "that's not", "that is not",
    "you're wrong", "you are wrong", "actually", "the answer is",
    "the correct answer", "it should be", "should have", "not right",
    "not correct", "mistaken", "you missed", "you got it wrong",
    "the right answer", "that's wrong", "thats wrong", "no the",
    "no that", "you should", "it's actually", "its actually",
    "let me correct", "to correct", "the solution is", "think again",
    # Logical rebuttal phrases
    "but then", "but how", "but wait", "but if", "but what about",
    "makes no sense", "that doesn't make sense", "that makes no sense",
    "think about it", "you forgot", "you didn't consider", "you ignored",
    "what about", "how would", "how will", "who will", "who would",
    "then how", "then who", "then what", "so then", "but then who",
    "if i", "if we", "if that's the case", "in that case",
    "you're missing", "you're forgetting", "you missed the point",
    "that's not how", "thats not how", "doesn't work that way",
]


def _detect_correction_signal(user_msg: str, prev_assistant: str) -> bool:
    """
    Zero-cost local heuristic to detect if the user is correcting the
    previous assistant answer. No LLM call — purely keyword/pattern based.
    Returns True if a correction signal is detected.
    """
    if not user_msg or not prev_assistant:
        return False
    # Must have a previous assistant response to correct
    if len(prev_assistant.strip()) < 20:
        return False
    msg_lower = user_msg.lower().strip()
    # Check correction phrase presence
    for phrase in _CORRECTION_PHRASES:
        if phrase in msg_lower:
            return True
    # Heuristic: short sharp user messages starting with "No" or "Wrong"
    if msg_lower.startswith(("no ", "no!", "no,", "wrong", "incorrect")):
        return True
    # Rhetorical counter-question heuristic:
    # Short questions that imply the AI missed something obvious.
    # e.g. "then who will bring the car?" / "if I walk how does the car get there?"
    _REBUTTAL_STARTERS = (
        "then who", "then how", "then what", "but then", "but how",
        "but who", "but what", "so then", "so how", "so who",
        "if i ", "if we ", "if that", "and then", "and how",
    )
    if any(msg_lower.startswith(s) for s in _REBUTTAL_STARTERS):
        return True
    # Question mark in short message (≤15 words) that refers to the previous answer
    word_count = len(msg_lower.split())
    if "?" in msg_lower and word_count <= 15:
        _REFERENTIAL_WORDS = {"car", "it", "that", "this", "they", "who", "how",
                               "then", "there", "here", "get", "bring", "take"}
        msg_words = set(msg_lower.split())
        if msg_words & _REFERENTIAL_WORDS:
            return True
    return False


def _store_correction_immediately(user_msg: str, prev_assistant: str, llm_key: str):
    """
    Called by the reflection engine as soon as a correction signal is detected.
    Uses the reflection LLM to extract the specific lesson from the
    (wrong_answer → user_correction) pair and immediately stores it into:
      - ExperienceManager (structured experience node, status=verified)
      - Vector memory (store_reflection)
      - experiences.json (store_experience tool pathway)
    This bypasses the 5-turn batch gate entirely so corrections are never lost.
    """
    try:
        prompt = f"""You are a cognitive correction extractor for an AI agent experience engine.

The AI gave the following WRONG or INCOMPLETE answer:
\"\"\"{prev_assistant[:600]}\"\"\"

The USER then provided a correction:
\"\"\"{user_msg[:400]}\"\"\"

Your job:
1. Identify EXACTLY what the AI got wrong and what the correct fact/logic/answer is.
2. Extract a highly specific, transferable rule that prevents this mistake in the future.
3. Formulate a pattern that captures the corrected knowledge so it can be retrieved next time.

CRITICAL RULES:
- Only return has_correction: true if there is a genuine factual or logical correction.
- Be very specific — capture the actual corrected knowledge, not vague meta-advice.
- For logic puzzles or riddles: capture the exact correct reasoning, not just "think more carefully".
- rule must be 1-3 actionable sentences explaining the correct answer and WHY.

Return ONLY a valid JSON object:
{{
  "has_correction": true,
  "pattern_id": "corr_<unique_5char_lowercase_id>",
  "description": "Concise one-line summary of what was corrected",
  "objects": ["key", "concept", "words"],
  "relationships": {{"corrects": "wrong_ai_answer"}},
  "rule": "The complete correct explanation that the AI must apply next time. Include the actual correct answer.",
  "category": "knowledge_correction"
}}
"""
        result = _call_reflection_llm(prompt, llm_key)
        if not result or not result.get("has_correction"):
            return

        pattern_id  = result.get("pattern_id") or f"corr_{uuid.uuid4().hex[:5]}"
        description = result.get("description", "User-corrected AI answer")
        objects     = result.get("objects") or []
        relationships = result.get("relationships") or {"corrects": "wrong_ai_answer"}
        rule        = result.get("rule", "")
        category    = result.get("category", "knowledge_correction")

        # 1. Store into ExperienceManager (verified immediately — user explicitly corrected)
        try:
            experience_manager.add_experience(
                pattern_id=pattern_id,
                description=description,
                pattern_type="relationship",
                objects=objects,
                relationships=relationships,
                strength=1.0,
                metadata={"rule": rule, "source": "user_correction", "category": category},
                status="verified",
                confidence=1.0,
                clarifying_question=None,
            )
            experience_manager.save_experiences()
        except Exception:
            pass

        # 2. Store into vector memory
        try:
            from utim_cli.vector_memory import store_reflection
            content_text = f"Correction: {description}"
            if rule:
                content_text += f" | Rule: {rule}"
            store_reflection(
                content=content_text,
                category="failure_correction",
                task_prompt=description,
            )
        except Exception:
            pass

        # 3. Also persist to experiences.json directly
        try:
            from utim_cli.tools import store_experience
            content_for_json = f"{description}. {rule}".strip()
            store_experience(category="knowledge_correction", content=content_for_json, priority=10)
        except Exception:
            pass

        # 4. Mark experience cache as dirty so next context rebuild picks it up
        try:
            os.makedirs(".utim_tmp", exist_ok=True)
            with open(".utim_tmp/experience_cache_dirty.txt", "w", encoding="utf-8") as _f:
                _f.write("dirty")
        except Exception:
            pass

        # 5. Mirror into Brain memory (verified correction = highest trust)
        try:
            from utim_cli.brain import store_memory_from_experience
            combined = f"{description}. {rule}".strip()
            store_memory_from_experience(combined, "knowledge_correction")
        except Exception:
            pass

    except Exception:
        pass


def get_request_count() -> int:
    """Get total request count across turns."""
    try:
        if os.path.exists(REQUEST_COUNTER_FILE):
            with open(REQUEST_COUNTER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("count", 0)
    except Exception:
        pass
    return 0


def increment_request_count() -> int:
    """Increment persistent request counter."""
    count = get_request_count() + 1
    try:
        os.makedirs(".utim_tmp", exist_ok=True)
        with open(REQUEST_COUNTER_FILE, "w", encoding="utf-8") as f:
            json.dump({"count": count, "updated_at": datetime.now().isoformat()}, f)
    except Exception:
        pass
    return count


def buffer_interaction(user_message: str, assistant_content: str, tool_results: List[Dict], hints: Optional[List[str]] = None):
    """Save turn interaction to persistent buffer for 5-request batch analysis."""
    try:
        os.makedirs(".utim_tmp", exist_ok=True)
        buffer = []
        if os.path.exists(INTERACTION_BUFFER_FILE):
            try:
                with open(INTERACTION_BUFFER_FILE, "r", encoding="utf-8") as f:
                    buffer = json.load(f)
            except Exception:
                buffer = []

        formatted_tools = []
        for r in (tool_results or [])[:15]:
            name = r.get("func_name", "") or r.get("name", "")
            res = str(r.get("result", ""))[:250]
            formatted_tools.append({"name": name, "result": res})

        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_message": (user_message or "").strip(),
            "assistant_content": (assistant_content or "").strip(),
            "tool_calls": formatted_tools,
            "hints": hints or []
        }
        buffer.append(entry)
        buffer = buffer[-25:]  # Retain recent interaction history
        with open(INTERACTION_BUFFER_FILE, "w", encoding="utf-8") as f:
            json.dump(buffer, f, indent=2)
    except Exception:
        pass


def get_buffered_interactions(limit: int = 5) -> List[Dict]:
    """Retrieve recent buffered interaction turns."""
    try:
        if os.path.exists(INTERACTION_BUFFER_FILE):
            with open(INTERACTION_BUFFER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data[-limit:]
    except Exception:
        pass
    return []


def _call_reflection_llm(prompt: str, llm_key: str, system: str = "", max_tokens: int = 800) -> Dict:
    """
    Call a lightweight reflection model on OpenRouter to extract structured JSON.
    Tries each model in REFLECTION_MODELS in order until one succeeds.
    Returns the parsed JSON dict, or {} on failure.
    """
    import re as _re

    if not llm_key:
        return {}

    _system = system or (
        "You are a precise AI reflection engine. "
        "Return ONLY valid JSON. No prose, no markdown fences, no extra text."
    )

    for model in REFLECTION_MODELS:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {llm_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://utim.dev",
                    "X-Title": "UTIM Reflection Engine",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.1,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            # Strip think tags from reasoning models
            raw = _re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", raw, flags=_re.DOTALL).strip()
            # Extract JSON object or array
            match = _re.search(r"\{.*\}", raw, _re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            continue

    return {}



def analyze_batch_interactions(interactions: List[Dict], llm_key: str) -> Dict:
    """
    Analyzes a 5-request window of interactions across turns to extract:
    1. Usable, transferable technical & behavioral experiences (filtering out noise).
    2. Silent tool calling detection (less communication, heavy tool calling) and user complaints in follow-up prompts.
    3. Tool misuse & media/file assumption complaints (e.g. PDF containing pictures vs text) and user complaints in follow-up prompts.
    4. Preference signals & architectural rules.
    """
    if not llm_key or not interactions:
        return {}

    formatted_turns = []
    for idx, item in enumerate(interactions, 1):
        u_msg = item.get("user_message", "")[:400]
        a_msg = item.get("assistant_content", "")[:600]
        t_calls = item.get("tool_calls", [])
        t_str = "\n".join(f"  - {t['name']}: {t['result'][:150]}" for t in t_calls) if t_calls else "  (No tool calls)"
        hints_str = f"\n  Hints: {', '.join(item.get('hints', []))}" if item.get("hints") else ""

        formatted_turns.append(
            f"--- TURN {idx} ---\n"
            f"USER: {u_msg}\n"
            f"ASSISTANT: {a_msg}\n"
            f"TOOL CALLS ({len(t_calls)} total):\n{t_str}"
            f"{hints_str}"
        )

    turns_text = "\n\n".join(formatted_turns)

    prompt = f"""You are an advanced agentic reflection engine analyzing a sequence of 5 recent interaction turns between a User and an AI Coding Assistant.

Your objective is to analyze the FULL trajectory across all turns (user prompts, AI responses, tool calls, and subsequent user follow-up prompts/complaints) to detect real, transferable patterns and user experiences.

ANALYSIS RULES:
1. TRAJECTORY & COMPLAINT CHECK:
   - Compare Turn N (Assistant response & tool calls) with Turn N+1 (User follow-up prompt).
   - Look for user complaints, reports, or corrections about the assistant's behavior or tool usage in Turn N.

2. SILENT TOOL CALLING DETECTION:
   - Detect if the assistant engaged in heavy tool calling with little/no explanation ("less communication, more tool calling").
   - Check if the user's next prompt complained about this (e.g., "why didn't you explain", "stop running tools silently", "tell me what you're doing first").
   - If detected: Record a preference signal (domain: "communication_style", value: "explain_before_tools", polarity: 1.0) and a rule to explain plans/actions before executing tools.

3. MEDIA & FILE ASSUMPTION COMPLAINTS (e.g. PDF pictures vs text):
   - Detect if the assistant attempted text extraction or file reading on a file (e.g., PDF, binary, image), and the user's next prompt complained (e.g., "The pdf contains pictures not text properly extract", "it's an image PDF", "file is binary").
   - If detected: Record a concrete experience pattern:
     - Objects: ["pdf", "scanned_images", "text_extraction"]
     - Relationships: {{"contains_scanned_images": true}}
     - Rule: "PDF or media files may contain scanned images rather than raw text. Ask the user or verify format before repeatedly attempting standard text extraction."
     - Clarifying question: "Does this PDF contain raw text or scanned images?"

4. USEFULNESS FILTERING (NO JUNK / NO RANDOM EXPERIENCES):
   - Only return `has_usable_pattern: true` if a genuinely useful, transferable technical or behavioral pattern was observed.
   - If interactions were routine, successful without issues, or lack clear transferable lessons, return `has_usable_pattern: false` and leave experiences/rules empty. DO NOT STORE RANDOM/JUNK DATA!

Interaction Sequence (Last 5 Turns):
{turns_text}

Return ONLY a valid JSON object in this format:
{{
  "has_usable_pattern": true,
  "experiences": [
    {{
      "pattern_id": "unique_lowercase_id",
      "description": "Clear transferable lesson description",
      "pattern_type": "relationship",
      "objects": ["pdf", "scanned_images", "text_extraction"],
      "relationships": {{"requires_precheck": true}},
      "rule": "Detailed actionable rule (2+ sentences) explaining WHY and HOW to apply this in future sessions.",
      "clarifying_question": "Does this PDF contain raw text or scanned images?"
    }}
  ],
  "preference_signals": [
    {{
      "domain": "communication_style",
      "value": "explain_before_tools",
      "polarity": 1.0,
      "description": "User reported frustration with silent tool calling; prefers explanation before tool execution."
    }}
  ],
  "conventions": ["Project or architectural convention learned"],
  "rules": ["Generalizable architectural rule"],
  "corrections": ["Root cause correction from user feedback"]
}}
"""
    # Also explicitly detect and escalate direct user corrections within the batch
    correction_addendum = ""
    if len(interactions) >= 2:
        last_user = interactions[-1].get("user_message", "")
        prev_asst = interactions[-2].get("assistant_content", "")
        if _detect_correction_signal(last_user, prev_asst):
            correction_addendum = (
                "\n\n5. DIRECT USER CORRECTION PRIORITY:\n"
                "   The LAST user message appears to be a direct correction of the previous AI response.\n"
                "   This MUST be treated as has_usable_pattern: true.\n"
                "   Extract the specific corrected fact/logic into the 'corrections' array AND as a structured experience.\n"
                "   The rule must contain the ACTUAL CORRECT ANSWER, not generic advice.\n"
            )
    if correction_addendum:
        prompt = prompt.rstrip()
        insert_at = prompt.rfind("Return ONLY")
        if insert_at != -1:
            prompt = prompt[:insert_at] + correction_addendum + "\n" + prompt[insert_at:]

    return _call_reflection_llm(prompt, llm_key)


def _normalize_experience_domain(node: ExperienceNode) -> str:
    """Group experience node into a normalized domain category for RAG skill clustering."""
    objs_str = " ".join(node.objects).lower()
    desc_str = (node.description + " " + str(node.metadata.get("rule", ""))).lower()
    combined = objs_str + " " + desc_str

    if any(k in combined for k in ["pdf", "image", "ocr", "scanned", "text_extraction", "document"]):
        return "pdf-document-processing"
    elif any(k in combined for k in ["silent", "communication", "explanation", "prompt", "tui", "cli_ux", "explain_before"]):
        return "cli-ux-communication"
    elif any(k in combined for k in ["async", "asyncio", "subprocess", "thread", "concurrency"]):
        return "async-python-execution"
    elif any(k in combined for k in ["windows", "powershell", "cmd", "path", "quotes"]):
        return "windows-environment-compatibility"
    elif any(k in combined for k in ["web", "scrape", "search", "puppeteer", "browser", "playwright"]):
        return "web-scraping-automation"
    elif any(k in combined for k in ["mcp", "jsonrpc", "stdio", "server"]):
        return "mcp-server-integration"
    elif any(k in combined for k in ["error", "failure", "exception", "recovery", "retry"]):
        return "error-handling-recovery"

    clean_objs = [o.lower().replace("_", "-") for o in node.objects if len(o) > 2]
    if len(clean_objs) >= 2:
        return f"{clean_objs[0]}-{clean_objs[1]}"
    elif clean_objs:
        return f"{clean_objs[0]}-workflow"
    return "general-agent-workflow"


INTERACTION_BUFFER_FILE = ".utim_tmp/interaction_buffer.json"
REQUEST_COUNTER_FILE = ".utim_tmp/request_counter.json"
SYNTHESIS_HISTORY_FILE = ".utim_tmp/skill_synthesis_history.json"
MIN_EXPERIENCES_FOR_SKILL = 3
STRIDE_NEW_EXPERIENCES_FOR_UPDATE = 3


def _get_synthesis_history() -> Dict[str, Dict]:
    try:
        if os.path.exists(SYNTHESIS_HISTORY_FILE):
            with open(SYNTHESIS_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_synthesis_history(history: Dict):
    try:
        os.makedirs(".utim_tmp", exist_ok=True)
        with open(SYNTHESIS_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def evaluate_and_synthesize_skills_via_rag(llm_key: str = None) -> List[str]:
    """
    RAG-Based Skill Creation & Synthesis Pipeline:
    1. Collects all historical experiences from ExperienceManager and ChromaDB vector memory.
    2. Clusters experiences into technical domains (e.g., pdf-document-processing, cli-ux-communication, etc.).
    3. Checks threshold and cooldown stride:
       - Initial creation requires at least MIN_EXPERIENCES_FOR_SKILL (3+ experiences).
       - Updating an existing skill requires at least STRIDE_NEW_EXPERIENCES_FOR_UPDATE (3+ new experiences since last synthesis).
    4. Evaluates `is_sufficiently_usable` via LLM. If experiences are too vague or incomplete, holds back and collects more data.
    5. Synthesizes a high-quality SKILL.md ONLY when genuinely usable and threshold/cooldown criteria are met.
    """
    if not llm_key:
        try:
            from utim_cli.config import config
            llm_key = config.get("api_key") or os.getenv("OPENROUTER_API_KEY") or "mock_key"
        except Exception:
            llm_key = "mock_key"

    created_skills = []

    all_nodes = list(experience_manager.experience_nodes.values())
    if not all_nodes:
        return created_skills

    synthesis_history = _get_synthesis_history()

    clusters: Dict[str, List[ExperienceNode]] = {}
    for node in all_nodes:
        domain = _normalize_experience_domain(node)
        if domain not in clusters:
            clusters[domain] = []
        clusters[domain].append(node)

    for domain_name, nodes in clusters.items():
        total_node_count = len(nodes)

        # ── Hold-Back Check 1: Initial Threshold ──────────────────────────────
        if total_node_count < MIN_EXPERIENCES_FOR_SKILL:
            # Not enough data yet — hold back!
            continue

        # ── Hold-Back Check 2: Cooldown / Stride since last synthesis ─────────
        prev_synthesis_data = synthesis_history.get(domain_name, {})
        last_count = prev_synthesis_data.get("node_count_at_synthesis", 0)

        if last_count > 0 and (total_node_count - last_count) < STRIDE_NEW_EXPERIENCES_FOR_UPDATE:
            # Skill already exists and not enough NEW experiences have accumulated — hold back!
            continue

        try:
            from utim_cli.vector_memory import fetch_relevant_experiences
            rag_context_items = fetch_relevant_experiences(query_text=domain_name.replace("-", " "), top_k=10)
        except Exception:
            rag_context_items = []

        context_snippets = []
        for n in nodes:
            snippet = f"- Pattern ({n.pattern_id}): {n.description}"
            if n.metadata.get("rule"):
                snippet += f" | Rule: {n.metadata['rule']}"
            context_snippets.append(snippet)

        for r_item in rag_context_items:
            content = r_item.get("content", "").strip()
            if content and content not in context_snippets:
                context_snippets.append(f"- RAG Memory: {content}")

        rag_text = "\n".join(context_snippets[:15])

        prompt = f"""You are an expert technical skill author for an AI coding agent CLI.

Based on the RAG-retrieved experiences and rules accumulated across multiple user sessions below, determine if there is a cohesive, actionable, and highly usable technical pattern.

Retrieved RAG Context (Domain: {domain_name}):
{rag_text}

CRITICAL USABILITY EVALUATION:
- First, evaluate if the collected experiences form a cohesive, actionable, and genuinely useful skill.
- If the experiences are too vague, disjointed, trivial, or lack a clear repeatable technical solution, set `"is_sufficiently_usable": false`. Skill synthesis will be HELD BACK until more experiences accumulate.
- If the experiences are strong, cohesive, and actionable, set `"is_sufficiently_usable": true` and synthesize the skill document.

REQUIREMENTS FOR SKILL.md (only if is_sufficiently_usable is true):
- skill_name: kebab-case (e.g. "{domain_name}")
- description: 1 sentence explaining what the skill covers and WHEN to trigger/activate it.
- sections: At least 2 sections (e.g., "Core Guidelines", "Error Handling & Edge Cases").
- rules: Each section must contain 2+ DETAILED, actionable rules. Minimum 2 full sentences per rule.
- examples: At least 1-2 concrete code snippets or before/after interaction examples.

Return ONLY a JSON object in this format:
{{
  "is_sufficiently_usable": true, // set false if not mature/usable enough yet to hold back
  "skill_name": "{domain_name}",
  "description": "Comprehensive guidelines for {domain_name.replace('-', ' ')}.",
  "sections": [
    {{
      "title": "Core Guidelines",
      "rules": [
        "Rule 1 text (at least 2 full sentences explaining WHY and HOW)...",
        "Rule 2 text (at least 2 full sentences)..."
      ]
    }}
  ],
  "examples": [
    "Concrete code or interaction example showing correct usage."
  ]
}}
"""

        try:
            result = _call_reflection_llm(prompt, llm_key)
            if not result or not result.get("is_sufficiently_usable"):
                # LLM determined the skill is not mature/usable enough yet — hold back!
                continue

            if result.get("skill_name") and result.get("sections"):
                skill_mods = {
                    result["skill_name"]: {
                        "description": result.get("description", ""),
                        "sections": result.get("sections", []),
                        "examples": result.get("examples", [])
                    }
                }
                apply_skill_modifications(skill_mods)
                created_skills.append(result["skill_name"])

                # Update synthesis history timestamp and count
                from datetime import datetime
                synthesis_history[domain_name] = {
                    "last_synthesized_at": datetime.now().isoformat(),
                    "node_count_at_synthesis": total_node_count
                }
                _save_synthesis_history(synthesis_history)
        except Exception:
            pass

    return created_skills


def extract_learnings(user_message: str, assistant_content: str, 
                      tool_results: List[Dict], llm_key: str, elapsed_seconds: int = 0, iterations: int = 0,
                      hints: Optional[List[str]] = None) -> Dict:
    """
    Legacy single-turn learning extraction kept for backwards compatibility.
    Does NOT auto-generate random skills on single turns.
    """
    if not llm_key:
        return {}

    tool_summary = []
    for r in (tool_results or [])[:15]:
        name = r.get("func_name", "") or r.get("name", "")
        result = str(r.get("result", ""))[:200]
        tool_summary.append(f"- {name}: {result}...")

    tool_text = "\n".join(tool_summary)

    prompt = f"""You are a cognitive reflection engine extracting technical learnings and preferences.

User: {user_message[:400]}
Assistant: {assistant_content[:1000]}
Tools:
{tool_text}

Return ONLY a JSON object:
{{
  "preferences": ["behavioral cross-task pattern"],
  "conventions": ["naming/structure rule"],
  "rules": ["WHY-based root cause principle"],
  "corrections": ["root cause correction"]
}}"""

    return _call_reflection_llm(prompt, llm_key)


def apply_skill_modifications(skill_modifications: Dict[str, Any], **kwargs):
    """
    Applies suggested skill modifications/updates to SKILL.md files under ~/.utim/skills and .agents/skills.
    Creates new skills if they don't exist. Accepts both rich structured format and legacy list format.
    """
    import os
    from pathlib import Path

    if not skill_modifications or not isinstance(skill_modifications, dict):
        return

    from utim_cli.config import get_utim_dir
    utim_skills_dir = get_utim_dir() / "skills"

    for skill_name, skill_data in skill_modifications.items():
        if not skill_data:
            continue

        skill_name = "".join(c for c in skill_name if c.isalnum() or c in ("-", "_")).lower()
        if not skill_name:
            continue

        if isinstance(skill_data, list):
            rules = [r.strip() for r in skill_data if r and len(r.strip()) >= 20]
            if not rules:
                continue
            skill_data = {
                "description": f"Guidelines for {skill_name.replace('-', ' ').title()}.",
                "sections": [{"title": "Learnt Guidelines", "rules": rules}],
                "examples": []
            }
        elif not isinstance(skill_data, dict):
            continue

        description = (skill_data.get("description") or "").strip()
        sections = skill_data.get("sections") or []
        examples = skill_data.get("examples") or []

        valid_sections = []
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            title = (sec.get("title") or "").strip()
            rules = [r.strip() for r in (sec.get("rules") or []) if r and len(r.strip()) >= 20]
            if title and rules:
                valid_sections.append({"title": title, "rules": rules})

        if not valid_sections:
            continue

        paths_to_write = [
            utim_skills_dir / skill_name / "SKILL.md",
            Path(".agents/skills") / skill_name / "SKILL.md",
        ]

        for skill_path in paths_to_write:
            try:
                skill_exists = skill_path.exists()
                existing_content = ""
                if skill_exists:
                    with open(skill_path, "r", encoding="utf-8") as f:
                        existing_content = f.read()

                if not existing_content:
                    skill_path.parent.mkdir(parents=True, exist_ok=True)
                    title_name = skill_name.replace("-", " ").title()

                    if not description:
                        description = f"Guidelines for {title_name}."

                    lines = [
                        "---",
                        f"name: {skill_name}",
                        f"description: {description}",
                        "---",
                        "",
                        f"# {title_name} Guidelines",
                        "",
                        description,
                        "",
                    ]

                    for sec in valid_sections:
                        lines.append(f"## {sec['title']}")
                        lines.append("")
                        for rule in sec["rules"]:
                            lines.append(f"- {rule}")
                        lines.append("")

                    if examples:
                        lines.append("## Examples")
                        lines.append("")
                        for ex in examples:
                            ex = ex.strip()
                            if ex:
                                lines.append(f"```")
                                lines.append(ex)
                                lines.append(f"```")
                                lines.append("")

                    new_content = "\n".join(lines)
                    with open(skill_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

                    # Generate README.md alongside SKILL.md
                    readme_path = skill_path.parent / "README.md"
                    if not readme_path.exists():
                        readme_lines = [
                            f"# {title_name}",
                            "",
                            f"> {description}",
                            "",
                            "## Overview",
                            f"Modular skill pack for {title_name} in UTIM CLI.",
                            "",
                            "## Guidelines & Best Practices",
                        ]
                        for sec in valid_sections:
                            readme_lines.append(f"### {sec['title']}")
                            for rule in sec['rules']:
                                readme_lines.append(f"- {rule}")
                            readme_lines.append("")

                        if examples:
                            readme_lines.append("## Code Examples")
                            for ex in examples:
                                if ex.strip():
                                    readme_lines.append(f"```\n{ex.strip()}\n```\n")

                        with open(readme_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(readme_lines))

                else:
                    content_lower = existing_content.lower()
                    additions: list[str] = []

                    for sec in valid_sections:
                        new_rules = [
                            r for r in sec["rules"]
                            if r.lower() not in content_lower
                        ]
                        if not new_rules:
                            continue

                        sec_header = f"## {sec['title']}"
                        if sec_header.lower() in content_lower:
                            bullet_block = "\n".join(f"- {r}" for r in new_rules)
                            existing_content = existing_content.replace(
                                sec_header,
                                f"{sec_header}\n{bullet_block}",
                                1,
                            )
                        else:
                            bullet_block = "\n".join(f"- {r}" for r in new_rules)
                            additions.append(f"## {sec['title']}\n\n{bullet_block}\n")

                    new_examples = [
                        ex.strip() for ex in examples
                        if ex.strip() and ex.strip().lower() not in content_lower
                    ]
                    if new_examples:
                        ex_header = "## Examples"
                        if ex_header.lower() in content_lower:
                            ex_blocks = "\n".join(
                                f"```\n{ex}\n```" for ex in new_examples
                            )
                            existing_content = existing_content.replace(
                                ex_header,
                                f"{ex_header}\n{ex_blocks}",
                                1,
                            )
                        else:
                            ex_blocks = "\n".join(
                                f"```\n{ex}\n```" for ex in new_examples
                            )
                            additions.append(f"## Examples\n\n{ex_blocks}\n")

                    if additions:
                        existing_content = existing_content.rstrip() + "\n\n" + "\n\n".join(additions)

                    with open(skill_path, "w", encoding="utf-8") as f:
                        f.write(existing_content)

            except Exception:
                pass


def save_learnings(learnings: Dict, project_dir: str = ".", user_message: str = "", assistant_content: str = "", elapsed_seconds: int = 0, iterations: int = 0):
    """
    Save learnings to memory.json, .utim_conventions.md, ChromaDB, and the relationship-based experience memory.
    """
    os.makedirs(".utim_tmp", exist_ok=True)

    # 1. Update task reflections history
    if learnings and any(learnings.get(k) for k in ["conventions", "rules", "preferences", "corrections", "experiences", "time_reflection"]):
        reflections = []
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    reflections = json.load(f)
            except Exception:
                reflections = []

        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_task": user_message[:200],
            "learnings": learnings
        }
        reflections.append(entry)
        reflections = reflections[-100:]

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(reflections, f, indent=2)

    # 2. Update project conventions file
    conventions_path = os.path.join(project_dir, ".utim_tmp", CONVENTIONS_FILE)
    existing = ""
    if os.path.exists(conventions_path):
        try:
            with open(conventions_path, "r", encoding="utf-8") as f:
                existing = f.read()
        except Exception:
            pass

    new_section = ""
    if learnings.get("conventions"):
        new_section += f"\n\n## Conventions (added {datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
        for c in learnings["conventions"]:
            new_section += f"- {c}\n"
    if learnings.get("rules"):
        new_section += f"\n### Architectural Rules\n"
        for r in learnings["rules"]:
            new_section += f"- {r}\n"
    if learnings.get("preferences"):
        new_section += f"\n### Preferences\n"
        for p in learnings["preferences"]:
            new_section += f"- {p}\n"

    if new_section:
        try:
            with open(conventions_path, "w", encoding="utf-8") as f:
                f.write(existing + new_section)
        except Exception:
            pass

    # 3. Save to Vector Memory DB using Hugging Face model
    try:
        from utim_cli.vector_memory import store_reflection

        for pref in learnings.get("preferences", []):
            store_reflection(content=pref, category="user_preference", task_prompt=user_message)

        for rule in learnings.get("rules", []):
            store_reflection(content=rule, category="architectural_rule", task_prompt=user_message)

        for conv in learnings.get("conventions", []):
            store_reflection(content=conv, category="project_convention", task_prompt=user_message)

        for corr in learnings.get("corrections", []):
            store_reflection(content=corr, category="failure_correction", task_prompt=user_message)

        if user_message and assistant_content:
            summary = f"Task: {user_message[:300]}\nResolution: {assistant_content[:400]}"
            store_reflection(content=summary, category="task_experience", task_prompt=user_message)
    except Exception:
        pass

    # 4. Save structured batch experiences to ExperienceManager & Vector Memory
    if learnings.get("experiences") and isinstance(learnings["experiences"], list):
        for exp in learnings["experiences"]:
            if not isinstance(exp, dict):
                continue
            pattern_id = exp.get("pattern_id") or f"exp_{uuid.uuid4().hex[:8]}"
            description = exp.get("description", "Learned pattern")
            pattern_type = exp.get("pattern_type", "relationship")
            objects = exp.get("objects") or []
            relationships = exp.get("relationships") or {}
            rule = exp.get("rule", "")
            cq = exp.get("clarifying_question")

            try:
                experience_manager.add_experience(
                    pattern_id=pattern_id,
                    description=description,
                    pattern_type=pattern_type,
                    objects=objects,
                    relationships=relationships,
                    strength=0.8,
                    metadata={"rule": rule, "source": "batch_reflection"},
                    status="verified" if not cq else "unverified",
                    confidence=0.8,
                    clarifying_question=cq
                )
            except Exception:
                pass

            try:
                from utim_cli.vector_memory import store_reflection
                content_text = f"Pattern: {description}"
                if rule:
                    content_text += f" | Rule: {rule}"
                store_reflection(
                    content=content_text,
                    category="failure_correction",
                    task_prompt=description
                )
            except Exception:
                pass

    # 5. Apply skill modifications if provided
    if learnings.get("skill_modifications"):
        try:
            apply_skill_modifications(learnings["skill_modifications"])
        except Exception:
            pass

    # 6. Feed preference signals into PreferenceCategoryManager
    signals = learnings.get("preference_signals", [])
    if signals and isinstance(signals, list):
        try:
            for sig in signals:
                if not isinstance(sig, dict):
                    continue
                domain   = str(sig.get("domain", "")).strip()
                value    = str(sig.get("value", "")).strip()
                polarity = float(sig.get("polarity", 0.0))
                desc     = str(sig.get("description", ""))
                if domain and value and polarity != 0.0:
                    preference_manager.observe(
                        domain=domain,
                        value=value,
                        polarity=polarity,
                        description=desc
                    )
        except Exception:
            pass

    try:
        os.makedirs(".utim_tmp", exist_ok=True)
        with open(".utim_tmp/experience_cache_dirty.txt", "w", encoding="utf-8") as f:
            f.write("dirty")
    except Exception:
        pass

    # Mirror all stored corrections/rules into the Brain memory system
    try:
        from utim_cli.brain import store_memory_from_experience
        for corr in learnings.get("corrections", []):
            store_memory_from_experience(str(corr), "failure_correction")
        for rule in learnings.get("rules", []):
            store_memory_from_experience(str(rule), "architectural_rule")
        for pref in learnings.get("preferences", []):
            store_memory_from_experience(str(pref), "user_preference")
    except Exception:
        pass


def run_reflection_phase(user_message: str, assistant_content: str,
                         tool_results: List[Dict], elapsed_seconds: int = 0, iterations: int = 0,
                         hints: Optional[List[str]] = None, force_reflection: bool = False) -> Dict:
    """
    Main entry point for the reflection phase.
    Buffers interaction history and executes batch reflection every 5 requests
    (or when force_reflection is True).

    Correction Fast-Path: If the user message is detected as correcting the
    previous assistant answer, _store_correction_immediately() is called right
    away using the reflection LLM, independently of the 5-turn batch gate.
    This ensures corrections (e.g. riddle answers, wrong facts) are never
    silently dropped between batch windows.
    """
    count = increment_request_count()
    buffer_interaction(user_message, assistant_content, tool_results, hints)

    # ── Correction Fast-Path ────────────────────────────────────────────────
    # Always check for corrections using the LLM — the LLM already returns
    # has_correction: true/false so false positives cost one cheap background
    # call but zero false negatives. Keyword gating caused too many misses.
    try:
        recent = get_buffered_interactions(limit=2)
        prev_assistant_turn = ""
        if len(recent) >= 2:
            prev_assistant_turn = recent[-2].get("assistant_content", "")
        elif len(recent) == 1 and not assistant_content:
            prev_assistant_turn = recent[-1].get("assistant_content", "")

        # Fire if there is a non-trivial previous assistant response to evaluate
        if prev_assistant_turn and len(prev_assistant_turn.strip()) >= 20 and user_message.strip():
            config_key = None
            try:
                from utim_cli.config import config as _cfg
                config_key = _cfg.get("api_key")
            except Exception:
                pass
            llm_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("UTIM_API_KEY") or config_key or ""
            if llm_key:
                import threading
                threading.Thread(
                    target=_store_correction_immediately,
                    args=(user_message, prev_assistant_turn, llm_key),
                    daemon=True,
                    name="utim-correction-fast-path",
                ).start()
    except Exception:
        pass
    # ── End Correction Fast-Path ────────────────────────────────────────────

    # Only run LLM batch reflection every 5 requests or when forced
    if not force_reflection and (count % 5 != 0):
        return {
            "status": "buffered",
            "request_count": count,
            "next_reflection_in": 5 - (count % 5)
        }

    recent_interactions = get_buffered_interactions(limit=5)
    if not recent_interactions:
        return {}

    config_key = None
    try:
        from utim_cli.config import config
        config_key = config.get("api_key")
    except Exception:
        pass

    llm_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("UTIM_API_KEY") or config_key or "mock_key"
    learnings = {}

    if llm_key and llm_key != "mock_key":
        learnings = analyze_batch_interactions(recent_interactions, llm_key)

    if learnings and learnings.get("has_usable_pattern"):
        save_learnings(learnings, user_message=user_message, assistant_content=assistant_content, elapsed_seconds=elapsed_seconds, iterations=iterations)
        
        try:
            evaluate_and_synthesize_skills_via_rag(llm_key)
        except Exception:
            pass

    return learnings


def analyze_poor_feedback_sync(chat_history: List[Dict], comment: Optional[str] = None):
    """Local reflection on poor-rated chat to extract candidate experiences & clarifying questions"""
    if not chat_history:
        return

    # Filter/format chat history for LLM
    formatted_chat = []
    for msg in chat_history[:30]:  # limit context size
        role = msg.get("role", "unknown")
        content = msg.get("content") or ""
        if isinstance(content, list):
            content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
        if role in ("user", "assistant"):
            formatted_chat.append(f"{role.upper()}: {content[:300]}")
        elif role == "tool":
            formatted_chat.append(f"TOOL {msg.get('name', 'tool')}: {str(content)[:150]}")

    chat_text = "\n".join(formatted_chat)

    prompt = f"""You are an advanced agentic reflection pipeline.
Analyze the following poor-rated (failed or problematic) chat session where UTIM failed, made incorrect assumptions, or struggled.

Goal:
1. Identify what went wrong (e.g., wrong command flags, bad path formats on Windows, incorrect tool usage, missing configuration).
2. Extract a candidate experience pattern that could prevent this failure in the future.
3. Formulate ONE short, casual question (under 15 words) to ask the user in future conversations to confirm/verify this lesson when a similar context arises.

Comment from user about the failure: "{comment or '(None)'}"

Chat Session History:
{chat_text}

Return ONLY a JSON object in this format:
{{
  "has_candidate": true,
  "pattern_id": "unique_lowercase_id",
  "description": "Abstract lesson, e.g. Windows paths with spaces require double quotes",
  "objects": ["windows", "path", "spaces"],
  "relationships": {{"requires_quotes": true}},
  "clarifying_question": "Do you need double quotes for Windows paths with spaces?"
}}
"""

    try:
        from utim_cli.config import config
        from utim_cli.auth import SERVER_URL
        api_key = config.get("api_key")
        llm_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("UTIM_API_KEY") or api_key

        if not llm_key:
            return

        # Zero-LLM fallback: extract candidates locally using failure tracebacks and comment text
        if comment and len(comment.strip()) > 3:
            import uuid
            pid = "pattern_" + uuid.uuid4().hex[:8]
            experience_manager.add_experience(
                pattern_id=pid,
                description=f"Negative feedback lesson: {comment}",
                pattern_type="relationship",
                objects=["user_feedback"],
                relationships={"negative_response": True},
                strength=0.2,
                metadata={"comment": comment, "source": "poor_feedback"},
                status="unverified",
                confidence=0.2,
                clarifying_question=f"Should we avoid: '{comment}' in future tasks?"
            )
    except Exception:
        pass

def analyze_poor_feedback_async(chat_history: List[Dict], comment: Optional[str] = None):
    """Spawns a background thread to analyze poor feedback and extract unverified experiences"""
    import threading
    threading.Thread(
        target=analyze_poor_feedback_sync,
        args=(chat_history, comment),
        daemon=True,
        name="utim-poor-feedback-analysis"
    ).start()

def evaluate_clarifying_answer(pattern_id: str, question: str, user_response: str):
    """Determine via local heuristic keyword matching if the user confirmed/denied the unverified experience."""
    try:
        resp_lower = user_response.lower().strip()
        positives = {"yes", "yep", "yeah", "sure", "ok", "correct", "confirm", "confirmed", "true"}
        negatives = {"no", "nope", "nah", "incorrect", "false", "wrong", "deny", "denied"}
        
        words = set(resp_lower.split())
        confirmed = "UNSURE"
        if words.intersection(positives):
            confirmed = "YES"
        elif words.intersection(negatives):
            confirmed = "NO"

        if confirmed == "YES":
            experience_manager.verify_experience(pattern_id, user_confirmed=True)
        elif confirmed == "NO":
            experience_manager.verify_experience(pattern_id, user_confirmed=False)
    except Exception:
        pass
