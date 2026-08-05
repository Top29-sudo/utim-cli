import os
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from utim_cli.reflection import (
    ExperienceNode,
    experience_manager,
    increment_request_count,
    buffer_interaction,
    get_buffered_interactions,
    analyze_batch_interactions,
    evaluate_and_synthesize_skills_via_rag,
    run_reflection_phase,
    MIN_EXPERIENCES_FOR_SKILL
)

class TestEnhancedReflectionPipeline(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(".utim_tmp")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        # Clear buffer, counter, and synthesis history before each test
        for p in [self.tmp_dir / "interaction_buffer.json", self.tmp_dir / "request_counter.json", self.tmp_dir / "skill_synthesis_history.json"]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def tearDown(self):
        pass

    def test_buffering_and_5_request_trigger(self):
        """Test that requests buffer silently until the 5th request."""
        with patch("utim_cli.reflection.analyze_batch_interactions") as mock_batch:
            mock_batch.return_value = {"has_usable_pattern": False}

            # Turns 1 to 4 should buffer without calling LLM batch analysis
            for i in range(1, 5):
                res = run_reflection_phase(
                    user_message=f"Task {i}",
                    assistant_content=f"Response {i}",
                    tool_results=[]
                )
                self.assertEqual(res.get("status"), "buffered")
                self.assertEqual(res.get("request_count"), i)
                self.assertFalse(mock_batch.called)

            # Turn 5 should trigger batch analysis
            res5 = run_reflection_phase(
                user_message="Task 5",
                assistant_content="Response 5",
                tool_results=[]
            )
            self.assertTrue(mock_batch.called)

    def test_silent_tool_calling_and_pdf_complaint_detection(self):
        """Test trajectory analysis detects silent tool calling and PDF image vs text complaints."""
        interactions = [
            {
                "user_message": "Read my document report.pdf",
                "assistant_content": "",
                "tool_calls": [{"name": "view_file", "result": "Error: binary or unreadable text"}]
            },
            {
                "user_message": "The pdf contains pictures not text properly extract",
                "assistant_content": "Apologies, let me check again.",
                "tool_calls": [{"name": "view_file", "result": "Error: binary"}]
            }
        ]

        mock_llm_response = {
            "has_usable_pattern": True,
            "experiences": [
                {
                    "pattern_id": "pdf_image_extraction",
                    "description": "PDF contains scanned images rather than raw text",
                    "pattern_type": "relationship",
                    "objects": ["pdf", "scanned_images", "text_extraction"],
                    "relationships": {"contains_scanned_images": True},
                    "rule": "Verify if PDF contains raw text or scanned images before running text extraction repeatedly.",
                    "clarifying_question": "Does this PDF contain raw text or scanned images?"
                }
            ],
            "preference_signals": [
                {
                    "domain": "communication_style",
                    "value": "explain_before_tools",
                    "polarity": 1.0,
                    "description": "User requested explanation before tool execution"
                }
            ]
        }

        with patch("utim_cli.reflection._call_reflection_llm", return_value=mock_llm_response):
            learnings = analyze_batch_interactions(interactions, llm_key="test_key")
            self.assertTrue(learnings.get("has_usable_pattern"))
            self.assertEqual(len(learnings.get("experiences")), 1)
            exp = learnings["experiences"][0]
            self.assertEqual(exp["pattern_id"], "pdf_image_extraction")
            self.assertIn("scanned_images", exp["objects"])

    def test_rag_skill_synthesis_requires_threshold(self):
        """Test that skill synthesis via RAG requires at least MIN_EXPERIENCES_FOR_SKILL (3+ experiences) before generating a skill."""
        # Scenario 1: Only 1 experience in cluster -> should NOT synthesize skill
        experience_manager.experience_nodes = {
            "exp_1": ExperienceNode(
                pattern_id="exp_1",
                description="PDF text extraction issue",
                pattern_type="relationship",
                objects=["pdf", "scanned_images"]
            )
        }

        with patch("utim_cli.reflection._call_reflection_llm") as mock_llm:
            skills = evaluate_and_synthesize_skills_via_rag(llm_key="test_key")
            self.assertEqual(len(skills), 0)
            self.assertFalse(mock_llm.called)

        # Scenario 2: 3 experiences in same domain cluster -> SHOULD synthesize skill
        experience_manager.experience_nodes.update({
            "exp_2": ExperienceNode(
                pattern_id="exp_2",
                description="PDF OCR requirement",
                pattern_type="relationship",
                objects=["pdf", "image"]
            ),
            "exp_3": ExperienceNode(
                pattern_id="exp_3",
                description="PDF binary format handling",
                pattern_type="relationship",
                objects=["pdf", "ocr"]
            )
        })

        mock_skill_resp = {
            "is_sufficiently_usable": True,
            "skill_name": "pdf-document-processing",
            "description": "Guidelines for PDF image and document processing.",
            "sections": [
                {
                    "title": "Core Guidelines",
                    "rules": [
                        "Always verify whether the PDF contains raw text or scanned images before running text extraction.",
                        "Ask the user or use OCR when processing image-heavy PDFs."
                    ]
                }
            ],
            "examples": ["Verify PDF type before extraction."]
        }

        with patch("utim_cli.reflection._call_reflection_llm", return_value=mock_skill_resp):
            skills = evaluate_and_synthesize_skills_via_rag(llm_key="test_key")
            self.assertIn("pdf-document-processing", skills)

if __name__ == "__main__":
    unittest.main()
