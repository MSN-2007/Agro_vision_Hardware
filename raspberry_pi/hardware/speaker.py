from hardware.base import AudioOutputDriver
from utils.logger import logger

class ConsoleSpeakerDriver(AudioOutputDriver):
    def initialize(self) -> bool:
        logger.info("[SPEAKER] Console Speaker Driver initialized")
        return True

    def speak(self, text: str) -> None:
        print(f"\n🔊 [AGROVISION SPEAKS]: \"{text}\"\n")

    def stop(self) -> None:
        pass

class TtsSpeakerDriver(AudioOutputDriver):
    def __init__(self):
        self.engine = None
        self.fallback = ConsoleSpeakerDriver()

    def initialize(self) -> bool:
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)
            logger.info("[SPEAKER] pyttsx3 TTS Engine initialized")
            return True
        except Exception as e:
            logger.info(f"[SPEAKER] pyttsx3 not available ({e}). Using Console Speaker.")
            return self.fallback.initialize()

    def speak(self, text: str) -> None:
        self.fallback.speak(text)
        if self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                logger.warning(f"[SPEAKER] TTS playback error: {e}")

    def stop(self) -> None:
        if self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass
