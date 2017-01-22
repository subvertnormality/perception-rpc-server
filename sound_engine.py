import pygame as pg
import time
import os

pg.mixer.init()
pg.init()

pg.mixer.set_num_channels(50)

_sound_library = {}

def play_sound(path, loops, volume):
  global _sound_library
  sound = _sound_library.get(path)
  if sound == None:
    canonicalized_path = path.replace('/', os.sep).replace('\\', os.sep)
    sound = pg.mixer.Sound(canonicalized_path)
    sound.set_volume(volume)
    _sound_library[path] = sound
  sound.play(loops = loops)

def stop_sound(path):
  global _sound_library
  sound = _sound_library.get(path)
  if sound == None:
    canonicalized_path = path.replace('/', os.sep).replace('\\', os.sep)
    sound = pg.mixer.Sound(canonicalized_path)
    _sound_library[path] = sound
  sound.stop()

def charging():
  stop_sound("../sounds/siren.wav")
  stop_sound("../sounds/playing.wav")
  stop_sound("../sounds/charging.wav")
  play_sound("../sounds/charging.wav", -1, 1)

def danger():
  stop_sound("../sounds/siren.wav")
  stop_sound("../sounds/playing.wav")
  stop_sound("../sounds/charging.wav")
  play_sound("../sounds/siren.wav", -1, 0.6)

def playing():
  stop_sound("../sounds/siren.wav")
  stop_sound("../sounds/playing.wav")
  stop_sound("../sounds/charging.wav")
  play_sound("../sounds/playing.wav", -1, 1)

def off_ramp():
  play_sound("../sounds/off_ramp.wav", 0, 0.2)

def level_unlocked():
  play_sound("../sounds/level_unlocked.wav", 0, 1)

def level_complete():
  play_sound("../sounds/level_complete.wav", 0, 1)