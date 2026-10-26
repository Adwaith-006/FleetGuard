import os
import pygame
from config.settings import ALARM_ENABLED, ALARM_SOUND_PATH
from utils.logger import logger

class AlarmManager:
    """Handles vehicle local audio warning alarms using Pygame Mixer."""

    def __init__(self, sound_path: str = ALARM_SOUND_PATH, enabled: bool = ALARM_ENABLED):
        self.sound_path = sound_path
        self.enabled = enabled
        self.alarm_on = False
        self.initialized = False

        if self.enabled:
            self._init_mixer()

    def _init_mixer(self):
        """Initializes pygame mixer and loads the alarm mp3 sound file."""
        try:
            if os.path.exists(self.sound_path):
                pygame.mixer.init()
                pygame.mixer.music.load(self.sound_path)
                self.initialized = True
                logger.info(f"Alarm system initialized with audio file: {self.sound_path}")
            else:
                logger.error(f"Alarm sound file not found at path: {self.sound_path}")
        except Exception as e:
            logger.error(f"Failed to initialize audio mixer: {e}")
            self.initialized = False

    def update(self, unsafe_condition: bool):
        """
        Updates alarm playback status based on whether an unsafe condition exists.
        Prevents restarting audio loop unnecessarily every frame.
        """
        if not self.enabled or not self.initialized:
            return

        try:
            if unsafe_condition:
                if not self.alarm_on:
                    pygame.mixer.music.play(-1)
                    self.alarm_on = True
                    logger.warning("[ALARM STARTED] Driver audio warning activated!")
            else:
                if self.alarm_on:
                    pygame.mixer.music.stop()
                    self.alarm_on = False
                    logger.info("[ALARM STOPPED] Driver returned to safe condition.")
        except Exception as e:
            logger.error(f"Error updating alarm status: {e}")

    def stop(self):
        """Stops alarm audio and cleans up pygame mixer."""
        if self.initialized:
            try:
                if self.alarm_on:
                    pygame.mixer.music.stop()
                    self.alarm_on = False
                pygame.mixer.quit()
                logger.info("Alarm system safely shutdown.")
            except Exception as e:
                logger.error(f"Error shutting down alarm mixer: {e}")
