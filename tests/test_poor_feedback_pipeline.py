import os
import json
import unittest
from unittest.mock import patch, MagicMock
from utim_cli.reflection import (
    ExperienceNode,
    ExperienceManager,
    analyze_poor_feedback_sync,
    evaluate_clarifying_answer,
    extract_context_from_interaction
)
from utim_cli.state import STATE

class TestPoorFeedbackPipeline(unittest.TestCase):

    def setUp(self):
        # Create a temp file path for test experience storage
        self.test_storage_path = ".utim_tmp/test_experience_memory.json"
        if os.path.exists(self.test_storage_path):
            try:
                os.remove(self.test_storage_path)
            except Exception:
                pass
        self.manager = ExperienceManager(storage_path=self.test_storage_path)

    def tearDown(self):
        # Clean up temp file path
        if os.path.exists(self.test_storage_path):
            try:
                os.remove(self.test_storage_path)
            except Exception:
                pass
        # Clear temporary STATE keys
        STATE.pop("asked_clarifying_question", None)

    def test_experience_node_new_fields(self):
        """Test that ExperienceNode supports status, confidence, and clarifying_question fields"""
        node = ExperienceNode(
            pattern_id="test_node",
            description="Testing unverified experience",
            pattern_type="relationship",
            objects=["pytest", "python"],
            relationships={"version": 3},
            strength=0.2,
            status="unverified",
            confidence=0.3,
            clarifying_question="Is this a test?"
        )
        self.assertEqual(node.status, "unverified")
        self.assertEqual(node.confidence, 0.3)
        self.assertEqual(node.clarifying_question, "Is this a test?")

    def test_save_and_load_experiences(self):
        """Test serializing and deserializing of unverified experiences"""
        self.manager.add_experience(
            pattern_id="test_unverified",
            description="Testing serialization",
            pattern_type="relationship",
            objects=["cmd", "spaces"],
            relationships={"quote_needed": True},
            strength=0.2,
            status="unverified",
            confidence=0.2,
            clarifying_question="Do you need quotes for spaces in cmd?"
        )

        # Load fresh manager from same storage
        new_manager = ExperienceManager(storage_path=self.test_storage_path)
        node = new_manager.experience_nodes.get("test_unverified")
        self.assertIsNotNone(node)
        self.assertEqual(node.status, "unverified")
        self.assertEqual(node.confidence, 0.2)
        self.assertEqual(node.clarifying_question, "Do you need quotes for spaces in cmd?")

    @patch("requests.post")
    @patch("utim_cli.config.config.get")
    def test_analyze_poor_feedback_sync(self, mock_config_get, mock_post):
        """Test that analyze_poor_feedback_sync queries LLM and extracts candidate experience"""
        mock_config_get.return_value = "test-api-key"
        
        # Mock LLM response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            json.dumps({
                "type": "content_delta",
                "text": json.dumps({
                    "has_candidate": True,
                    "pattern_id": "pytest_spaces_windows",
                    "description": "Windows paths with spaces fail without quotes in pytest",
                    "objects": ["pytest", "windows", "spaces"],
                    "relationships": {"requires_quotes": True},
                    "clarifying_question": "Does running pytest on Windows fail when path has spaces?"
                })
            }).encode("utf-8")
        ]
        mock_post.return_value = mock_resp

        chat_history = [
            {"role": "user", "content": "run tests on C:\\Program Files\\project"},
            {"role": "assistant", "content": "Okay, running pytest C:\\Program Files\\project"},
            {"role": "tool", "name": "run_command", "content": "pytest: error: unrecognized arguments: Files\\project"}
        ]

        # Patch the global experience_manager used inside analyze_poor_feedback_sync
        with patch("utim_cli.reflection.experience_manager", self.manager):
            analyze_poor_feedback_sync(chat_history, comment="Failed to parse path with spaces")

            # Check that the experience was saved
            node = self.manager.experience_nodes.get("pytest_spaces_windows")
            self.assertIsNotNone(node)
            self.assertEqual(node.status, "unverified")
            self.assertEqual(node.confidence, 0.2)
            self.assertEqual(node.clarifying_question, "Does running pytest on Windows fail when path has spaces?")

    @patch("requests.post")
    @patch("utim_cli.config.config.get")
    def test_evaluate_clarifying_answer(self, mock_config_get, mock_post):
        """Test evaluating user's answer to clarifying question and updating confidence"""
        mock_config_get.return_value = "test-api-key"
        
        # Add an unverified experience node
        self.manager.add_experience(
            pattern_id="test_verify_node",
            description="Testing verification",
            pattern_type="relationship",
            objects=["node"],
            strength=0.2,
            status="unverified",
            confidence=0.2,
            clarifying_question="Are you verifying this?"
        )

        # Mock YES confirmation from LLM
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            json.dumps({
                "type": "content_delta",
                "text": '{"confirmed": "YES"}'
            }).encode("utf-8")
        ]
        mock_post.return_value = mock_resp

        # Patch experience_manager to use our test manager
        with patch("utim_cli.reflection.experience_manager", self.manager):
            evaluate_clarifying_answer("test_verify_node", "Are you verifying this?", "Yes, absolutely.")

            node = self.manager.experience_nodes.get("test_verify_node")
            self.assertIsNotNone(node)
            # Confidence should increase (0.2 + 0.3 = 0.5)
            self.assertAlmostEqual(node.confidence, 0.5)
            self.assertEqual(node.status, "unverified")

            # Mock second YES confirmation to reach verified status (>= 0.8)
            mock_resp.iter_lines.return_value = [
                json.dumps({
                    "type": "content_delta",
                    "text": '{"confirmed": "YES"}'
                }).encode("utf-8")
            ]
            evaluate_clarifying_answer("test_verify_node", "Are you verifying this?", "Yes, indeed.")
            
            node = self.manager.experience_nodes.get("test_verify_node")
            self.assertIsNotNone(node)
            # Confidence should increase to 0.8
            self.assertAlmostEqual(node.confidence, 0.8)
            self.assertEqual(node.status, "verified")

    @patch("requests.post")
    @patch("utim_cli.config.config.get")
    def test_evaluate_clarifying_answer_no(self, mock_config_get, mock_post):
        """Test that disconfirming answer decreases confidence and eventually deletes unverified node"""
        mock_config_get.return_value = "test-api-key"
        
        # Add an unverified experience node
        self.manager.add_experience(
            pattern_id="test_verify_node_no",
            description="Testing verification no",
            pattern_type="relationship",
            objects=["node"],
            strength=0.2,
            status="unverified",
            confidence=0.2,
            clarifying_question="Are you verifying this?"
        )

        # Mock NO response from LLM
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            json.dumps({
                "type": "content_delta",
                "text": '{"confirmed": "NO"}'
            }).encode("utf-8")
        ]
        mock_post.return_value = mock_resp

        with patch("utim_cli.reflection.experience_manager", self.manager):
            evaluate_clarifying_answer("test_verify_node_no", "Are you verifying this?", "No, that is not correct.")

            # Since confidence goes from 0.2 to 0.0 (<= 0.2), the node should be deleted
            node = self.manager.experience_nodes.get("test_verify_node_no")
            self.assertIsNone(node)

if __name__ == "__main__":
    unittest.main()
