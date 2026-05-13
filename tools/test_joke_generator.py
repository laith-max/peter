"""
Tests for the joke generator module
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.joke_generator import JokeGenerator


class TestJokeGenerator(unittest.TestCase):
    """Test cases for JokeGenerator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.generator = JokeGenerator()
    
    @patch('tools.joke_generator.requests.Session.get')
    def test_get_random_joke_success(self, mock_get):
        """Test successful joke retrieval"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": False,
            "type": "single",
            "joke": "Why do programmers prefer dark mode? Because light attracts bugs!"
        }
        mock_get.return_value = mock_response
        
        result = self.generator.get_random_joke("Programming")
        
        self.assertIsNotNone(result)
        self.assertFalse(result.get("error"))
        self.assertIn("joke", result)
    
    @patch('tools.joke_generator.requests.Session.get')
    def test_get_twopart_joke(self, mock_get):
        """Test retrieving a two-part joke"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": False,
            "type": "twopart",
            "setup": "Why did the chicken cross the road?",
            "delivery": "To get to the other side!"
        }
        mock_get.return_value = mock_response
        
        result = self.generator.get_random_joke()
        
        self.assertEqual(result.get("type"), "twopart")
        self.assertIn("setup", result)
        self.assertIn("delivery", result)
    
    def test_format_single_joke(self):
        """Test formatting a single joke"""
        joke_data = {
            "type": "single",
            "joke": "This is a test joke"
        }
        
        formatted = self.generator.format_joke(joke_data)
        self.assertEqual(formatted, "This is a test joke")
    
    def test_format_twopart_joke(self):
        """Test formatting a two-part joke"""
        joke_data = {
            "type": "twopart",
            "setup": "Why?",
            "delivery": "Because!"
        }
        
        formatted = self.generator.format_joke(joke_data)
        self.assertIn("Q: Why?", formatted)
        self.assertIn("A: Because!", formatted)
    
    def test_format_none_joke(self):
        """Test formatting None returns default message"""
        formatted = self.generator.format_joke(None)
        self.assertIn("Could not fetch", formatted)
    
    @patch('tools.joke_generator.requests.Session.get')
    def test_get_joke_json(self, mock_get):
        """Test getting joke as JSON string"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": False,
            "joke": "Test joke"
        }
        mock_get.return_value = mock_response
        
        result = self.generator.get_joke_json()
        
        self.assertIn("Test joke", result)
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
