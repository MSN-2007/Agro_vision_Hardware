from abc import ABC, abstractmethod
from typing import Optional, List

class DisplayDriver(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def show_text(self, lines: List[str], title: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

class AudioInputDriver(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def listen_and_transcribe(self, prompt: str = "Listening...") -> Optional[str]:
        pass

class AudioOutputDriver(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def speak(self, text: str) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass
