from hardware.base import AudioInputDriver
from utils.logger import logger
from typing import Optional

class TextModeAudioDriver(AudioInputDriver):
    def initialize(self) -> bool:
        logger.info("[MIC] TextMode Audio Driver ready (type voice commands directly)")
        return True

    def listen_and_transcribe(self, prompt: str = "Listening...") -> Optional[str]:
        try:
            print(f"\n🎤 [MIC: {prompt}] (Type command or 'q' to exit):")
            val = input("> ").strip()
            if not val or val.lower() == 'q':
                return None
            return val
        except (KeyboardInterrupt, EOFError):
            return None

class AlsaAudioDriver(AudioInputDriver):
    def __init__(self):
        self.recognizer = None
        self.microphone = None
        self.fallback = TextModeAudioDriver()

    def initialize(self) -> bool:
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            logger.info("[MIC] ALSA / PyAudio Hardware Microphone initialized")
            return True
        except Exception as e:
            logger.info(f"[MIC] Physical microphone not detected ({e}). Using Text-Mode input.")
            return self.fallback.initialize()

    def listen_and_transcribe(self, prompt: str = "Listening...") -> Optional[str]:
        if self.recognizer and self.microphone:
            try:
                import speech_recognition as sr
                logger.info(f"[MIC] {prompt}")
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio)
                logger.info(f"[MIC Transcribed]: '{text}'")
                return text
            except Exception as e:
                logger.warning(f"[MIC] Recognition timeout or error: {e}")
                return None

        return self.fallback.listen_and_transcribe(prompt)
