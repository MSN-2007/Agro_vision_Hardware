import unittest
from unittest.mock import patch, MagicMock
from hardware.oled import ConsoleOledDriver
from hardware.speaker import ConsoleSpeakerDriver
from hardware.microphone import TextModeAudioDriver
from ui.display_manager import DisplayManager

class TestHardwareAbstractions(unittest.TestCase):
    def test_console_oled(self):
        driver = ConsoleOledDriver()
        self.assertTrue(driver.initialize())
        self.assertEqual(driver.width, 28)
        self.assertEqual(driver.height, 7)
        
        # Test display rendering
        driver.show_text(["Line 1", "Line 2"])
        driver.clear()

    def test_display_manager(self):
        driver = ConsoleOledDriver()
        mgr = DisplayManager(driver)
        # Should render various states without error
        mgr.show_boot()
        mgr.show_connecting()
        mgr.show_ready("Valley Farm", "North Field")
        mgr.show_listening()
        mgr.show_thinking()
        mgr.show_speaking("Status OK")
        mgr.show_offline()
        mgr.show_error("Test Error")

    def test_console_speaker(self):
        speaker = ConsoleSpeakerDriver()
        self.assertTrue(speaker.initialize())
        # Should execute speak without error
        speaker.speak("Testing unit audio")
        speaker.stop()

    def test_text_mic(self):
        mic = TextModeAudioDriver()
        self.assertTrue(mic.initialize())
        with patch('builtins.input', return_value='What is the weather?'):
            cmd = mic.listen_and_transcribe()
            self.assertEqual(cmd, 'What is the weather?')

if __name__ == '__main__':
    unittest.main()
