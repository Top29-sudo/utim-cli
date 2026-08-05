import os
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from utim_cli.bootstrap import scan_available_skills, get_rag_context
from utim_cli.reflection import apply_skill_modifications, save_learnings
from utim_cli.orchestrator import Orchestrator

class TestSkillsReflectionPipeline(unittest.TestCase):

    def setUp(self):
        # Create temp directories to isolate the test from actual skills
        self.temp_utim_skills = Path('.utim/skills/temp-pytest-skill')
        self.temp_agents_skills = Path('.agents/skills/temp-pytest-skill')
        self.temp_agents_new_skill = Path('.agents/skills/temp-new-pytest-skill')
        self.temp_utim_new_skill = Path('.utim/skills/temp-new-pytest-skill')

        self.cleanup_temp_paths()

    def tearDown(self):
        self.cleanup_temp_paths()

    def cleanup_temp_paths(self):
        # Remove created test skills
        for p in [
            self.temp_utim_skills, self.temp_agents_skills, self.temp_agents_new_skill, self.temp_utim_new_skill,
            Path('.utim_tmp/skills/temp-pytest-skill'), Path('.utim_tmp/skills/temp-new-pytest-skill')
        ]:
            if p.exists():
                try:
                    shutil.rmtree(p)
                except Exception:
                    pass

    def test_scan_available_skills_detection_and_keywords(self):
        """Test that scan_available_skills dynamically discovers the skills and extracts metadata and keywords."""
        self.temp_agents_skills.mkdir(parents=True, exist_ok=True)
        skill_md = self.temp_agents_skills / "SKILL.md"
        
        # Write temporary skill file with Yaml frontmatter
        skill_md.write_text("""---
name: temp-pytest-skill
description: Custom guidelines for unit testing and pytest automation.
---

# Pytest Skill Guidelines
- Use fixture instead of setUp when possible.
""", encoding="utf-8")

        skills = scan_available_skills()
        self.assertIn("temp-pytest-skill", skills)
        skill_info = skills["temp-pytest-skill"]
        self.assertEqual(skill_info["name"], "temp-pytest-skill")
        self.assertEqual(skill_info["description"], "Custom guidelines for unit testing and pytest automation.")
        
        # Verify extracted keywords (like 'pytest', 'automation', 'testing', 'unit')
        keywords = skill_info["keywords"]
        self.assertIn("pytest", keywords)
        self.assertIn("automation", keywords)
        self.assertIn("testing", keywords)
        self.assertIn("unit", keywords)

    def test_apply_skill_modifications_creates_and_updates(self):
        """Test apply_skill_modifications appends rules to existing files or creates new skills."""
        # 1. Test creation of a new skill (must satisfy >40 chars and >= 3 rules guardrails)
        mods = {
            "temp-new-pytest-skill": [
                "Always run coverage check after tests to ensure code is complete",
                "Ensure fixtures are placed in conftest.py and are properly scoped",
                "Mock external APIs and database calls to prevent dependencies"
            ]
        }
        apply_skill_modifications(mods)

        utim_md = Path('.utim/skills/temp-new-pytest-skill/SKILL.md')
        agents_md = Path('.agents/skills/temp-new-pytest-skill/SKILL.md')

        self.assertTrue(utim_md.exists())
        self.assertTrue(agents_md.exists())

        content = utim_md.read_text(encoding="utf-8")
        self.assertIn("Temp New Pytest Skill Guidelines", content)
        self.assertIn("Always run coverage check after tests to ensure code is complete", content)
        self.assertIn("Ensure fixtures are placed in conftest.py and are properly scoped", content)

        # 2. Test updating existing skill and avoiding duplicates (min_len becomes 25 since skill exists)
        mods_update = {
            "temp-new-pytest-skill": [
                "Always run coverage check after tests to ensure code is complete", # Duplicate, should not be repeated
                "Use mock patches carefully in tests" # New rule (>25 chars)
            ]
        }
        apply_skill_modifications(mods_update)

        content_updated = utim_md.read_text(encoding="utf-8")
        # Counts occurrences of the rule
        self.assertEqual(content_updated.count("Always run coverage check after tests to ensure code is complete"), 1)
        self.assertIn("Use mock patches carefully in tests", content_updated)

    def test_save_learnings_triggers_skill_updates(self):
        """Test that save_learnings correctly calls apply_skill_modifications."""
        # Since it is a new skill creation in this test isolate, we must satisfy the 3 substantial rules guardrail too
        learnings = {
            "skill_modifications": {
                "temp-new-pytest-skill": [
                    "A learn rule from save_learnings that is longer than forty characters",
                    "Second learn rule from save_learnings that is longer than forty characters",
                    "Third learn rule from save_learnings that is longer than forty characters"
                ]
            }
        }
        save_learnings(learnings)

        utim_md = Path('.utim/skills/temp-new-pytest-skill/SKILL.md')
        self.assertTrue(utim_md.exists())
        self.assertIn("A learn rule from save_learnings that is longer than forty characters", utim_md.read_text(encoding="utf-8"))

    def test_situational_scoring_matches_new_skill(self):
        """Test that get_rag_context picks up the new skill dynamically based on keywords."""
        self.temp_agents_skills.mkdir(parents=True, exist_ok=True)
        skill_md = self.temp_agents_skills / "SKILL.md"
        skill_md.write_text("""---
name: temp-pytest-skill
description: Custom guidelines for unit testing and pytest automation.
---
# Pytest Skill Guidelines
""", encoding="utf-8")

        # Test matching on keyword 'pytest'
        ctx_pytest = get_rag_context("Please help me write a pytest suite")
        self.assertIn("RELEVANT CORE SKILL: TEMP-PYTEST-SKILL", ctx_pytest)

        # Test matching on keyword 'automation'
        ctx_auto = get_rag_context("Check my test automation setup")
        self.assertIn("RELEVANT CORE SKILL: TEMP-PYTEST-SKILL", ctx_auto)

if __name__ == "__main__":
    unittest.main()
