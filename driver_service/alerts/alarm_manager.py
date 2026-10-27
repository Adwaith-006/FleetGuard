import os
import threading
from typing import Optional
from config.settings import ALARM_ENABLED, ALARM_SOUND_PATH, ALARM_VOLUME
from utils.logger import logger

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    pygame = None
    PYGAME_AVAILABLE = False

# Windows winsound support for hardware audio fallback
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    winsound = None
    WINSOUND_AVAILABLE = False


class AlarmManager:
    """
    Handles local driver warning alarms using Pygame Mixer with Windows winsound fallback.
    
    Guarantees:
    - 100% offline local operation (zero cloud/network dependency)
    - Anti-flicker: Never restarts playback loop on consecutive frames
    - Safe fallback: If audio file is missing or pygame fails, uses system speaker beep
    - Clean shutdown and resource release
    """

    def __init__(
        self,
        sound_path: str = ALARM_SOUND_PATH,
        enabled: bool = ALARM_ENABLED,
        volume: float = ALARM_VOLUME
    ):
        self.sound_path = sound_path
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.alarm_on = False
        self.mixer_initialized = False
        self.fallback_beep_active = False

        if self.enabled:
            self._init_audio()

    def _init_audio(self):
        """Initializes Pygame mixer and loads the alarm mp3 sound file."""
        if not PYGAME_AVAILABLE:
            logger.warning("Pygame not installed. Alarm manager will use system beep fallback.")
            return

        try:
            if not os.path.exists(self.sound_path):
                fallback_asset = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "alarm.mp3"))
                if os.path.exists(fallback_asset):
                    self.sound_path = fallback_asset

            if os.path.exists(self.sound_path):
                # Initialize pygame mixer safely
                pygame.mixer.init()
                pygame.mixer.music.load(self.sound_path)
                pygame.mixer.music.set_volume(self.volume)
                self.mixer_initialized = True
                logger.info(f"Local audio alarm initialized with audio file: {self.sound_path}")
            else:
                logger.warning(
                    f"Alarm sound file not found at: {self.sound_path}. System beep fallback will be used."
                )
        except Exception as e:
            logger.warning(f"Could not initialize Pygame audio mixer: {e}. System beep fallback will be used.")
            self.mixer_initialized = False

    def _beep_worker(self):
        """Background worker for Windows system beep when Pygame is unavailable."""
        while self.fallback_beep_active:
            try:
                if WINSOUND_AVAILABLE and winsound is not None:
                    winsound.Beep(1800, 300)
                else:
                    break
            except Exception:
                break

    def update(self, unsafe_condition: bool, severity: str = "WARNING"):
        """
        Updates alarm playback status based on whether an unsafe condition exists.
        Prevents restarting audio playback on every video frame.
        """
        if not self.enabled:
            return

        try:
            if unsafe_condition:
                if not self.alarm_on:
                    self.alarm_on = True
                    logger.warning(f"[ALARM INVOCATION] Driver safety warning triggered! Severity: {severity} | Audio: {self.sound_path}")

                    if self.mixer_initialized and pygame is not None:
                        try:
                            pygame.mixer.music.play(-1)
                            logger.info(f"[ALARM PLAYBACK] Pygame mixer playing loop: {self.sound_path}")
                        except Exception as e:
                            logger.error(f"Error playing alarm audio: {e}")
                    elif WINSOUND_AVAILABLE and not self.fallback_beep_active:
                        self.fallback_beep_active = True
                        threading.Thread(target=self._beep_worker, daemon=True).start()
                        logger.info("[ALARM PLAYBACK] Hardware winsound system beep active.")
            else:
                if self.alarm_on:
                    self.reset()
                    logger.info("[ALARM DEACTIVATED] Driver condition resolved to safe. Audio alarm stopped.")
        except Exception as e:
            logger.error(f"Error updating alarm status: {e}")

    def reset(self):
        """Stops active audio alarm and resets state to silent."""
        self.alarm_on = False
        self.fallback_beep_active = False

        if self.mixer_initialized and pygame is not None:
            try:
                pygame.mixer.music.stop()
            except Exception as e:
                logger.debug(f"Error stopping pygame mixer: {e}")

    def stop(self):
        """Stops audio and cleans up resources completely on shutdown."""
        self.reset()
        if self.mixer_initialized and pygame is not None:
            try:
                pygame.mixer.quit()
                self.mixer_initialized = False
                logger.info("Alarm mixer cleanly shut down.")
            except Exception as e:
                logger.debug(f"Error quitting pygame mixer: {e}")

