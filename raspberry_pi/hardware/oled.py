from hardware.base import DisplayDriver
from utils.logger import logger
from typing import Optional, List

class ConsoleOledDriver(DisplayDriver):
    def __init__(self, width=28, height=7):
        self.width = width
        self.height = height

    def initialize(self) -> bool:
        logger.info("[OLED] Console OLED Driver initialized")
        return True

    def show_text(self, lines: List[str], title: Optional[str] = None) -> None:
        border = "+" + "-" * (self.width + 2) + "+"
        rendered = []
        rendered.append(border)
        header_text = title if title else "AGROVISION PI"
        rendered.append(f"| {header_text.center(self.width)} |")
        rendered.append("+" + "=" * (self.width + 2) + "+")

        content_lines = []
        for raw_l in lines:
            for sub_l in raw_l.split("\n"):
                if sub_l.strip():
                    while len(sub_l) > self.width:
                        content_lines.append(sub_l[:self.width])
                        sub_l = sub_l[self.width:]
                    content_lines.append(sub_l)

        content_lines = content_lines[:self.height]
        while len(content_lines) < self.height:
            content_lines.append("")

        for line in content_lines:
            rendered.append(f"| {line.ljust(self.width)} |")

        rendered.append(border)
        print("\n" + "\n".join(rendered) + "\n")

    def clear(self) -> None:
        pass

class LumaOledDriver(DisplayDriver):
    def __init__(self, port=1, address=0x3C, width=128, height=64):
        self.port = port
        self.address = address
        self.width = width
        self.height = height
        self.device = None
        self.fallback = ConsoleOledDriver()

    def initialize(self) -> bool:
        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import ssd1306
            serial = i2c(port=self.port, address=self.address)
            self.device = ssd1306(serial, width=self.width, height=self.height)
            logger.info(f"[OLED] Hardware SSD1306 OLED initialized on I2C port={self.port}, addr=0x{self.address:02X}")
            return True
        except Exception as e:
            logger.info(f"[OLED] Physical I2C display not detected ({e}). Using Console OLED emulator.")
            return self.fallback.initialize()

    def show_text(self, lines: List[str], title: Optional[str] = None) -> None:
        if self.device:
            try:
                from PIL import Image, ImageDraw, ImageFont
                image = Image.new('1', (self.device.width, self.device.height))
                draw = ImageDraw.Draw(image)
                font = ImageFont.load_default()

                y = 2
                if title:
                    draw.text((0, y), title.upper()[:18], font=font, fill=255)
                    y += 12
                    draw.line((0, y, self.device.width, y), fill=255)
                    y += 4

                for line in lines:
                    for sub in line.split("\n"):
                        draw.text((0, y), sub[:20], font=font, fill=255)
                        y += 10
                        if y > self.device.height - 10:
                            break

                self.device.display(image)
                return
            except Exception as e:
                logger.warning(f"[OLED] Framebuffer draw error: {e}")

        self.fallback.show_text(lines, title)

    def clear(self) -> None:
        if self.device:
            try:
                self.device.clear()
            except Exception:
                pass
        self.fallback.clear()
