import subprocess, sys

MALE = 'Microsoft David Desktop'
FEMALE = 'Microsoft Hazel Desktop'

def speak(voice, speech):

  p = subprocess.Popen(["powershell.exe", 
                "Add-Type -AssemblyName System.speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.SelectVoice('%s'); $speak.Speak('%s')" % (voice, speech)], 
                stdout=sys.stdout)
  p.communicate()

def mspeak(speech):
  speak(MALE, speech)

def fspeak(speech):
  speak(FEMALE, speech)