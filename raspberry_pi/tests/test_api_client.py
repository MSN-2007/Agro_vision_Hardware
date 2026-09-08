import unittest
from unittest.mock import patch, MagicMock
from services.agrovision_api import AgroVisionApiService
from models.response import AssistantResponse

class TestAgroVisionApiClient(unittest.TestCase):
    def setUp(self):
        self.api = AgroVisionApiService(base_url="http://localhost:5000")

    def test_health_check(self):
        healthy = self.api.check_health()
        self.assertTrue(healthy)

    def test_heartbeat(self):
        result = self.api.send_heartbeat()
        self.assertTrue(result)

    def test_get_farms(self):
        farms = self.api.get_farms()
        self.assertIsInstance(farms, list)
        self.assertGreater(len(farms), 0)

    def test_get_tasks(self):
        tasks = self.api.get_tasks()
        self.assertIsInstance(tasks, list)

    def test_converse_weather(self):
        resp = self.api.converse("What is the weather today?")
        self.assertIsInstance(resp, AssistantResponse)
        self.assertTrue(resp.success)
        self.assertEqual(resp.intent, "GET_WEATHER")
        self.assertIn("weather", resp.text.lower())

    def test_converse_tasks(self):
        resp = self.api.converse("What tasks do I have today?")
        self.assertIsInstance(resp, AssistantResponse)
        self.assertTrue(resp.success)
        self.assertEqual(resp.intent, "GET_TODAYS_TASKS")

if __name__ == '__main__':
    unittest.main()
