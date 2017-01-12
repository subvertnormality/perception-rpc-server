import voice_engine
from chatterbot import ChatBot
import requests

url = 'https://game.playperception.com/game/attemptunlockround/'
url_local = 'https://game.localhost/game/attemptunlockround/'

cert_file_path = "certs/client.crt"
key_file_path = "certs/client.key"
cert = (cert_file_path, key_file_path)

keywords = [ 
  'hello',
  'help',
]

chatbot = ChatBot(
    'The Presence',
    storage_adapter='chatterbot.storage.MongoDatabaseAdapter',
    logic_adapters=[
        'chatterbot.logic.BestMatch',
        {
            'import_path': 'chatterbot.logic.LowConfidenceAdapter',
            'threshold': 0.65,
            'default_response': 'You must progress through the levels for more information.'
        }
    ],
    filters=[
        'chatterbot.filters.RepetitiveResponseFilter'
    ],
    database='presense-database'
)

def process_speech_input(input):

  if (len(input.split()) > 1 or input in keywords):
    voice_engine.mspeak(input)
    voice_engine.fspeak(chatbot.get_response(input))
  else:
    voice_engine.mspeak(input)
    r = requests.post(url, json={'attempt': input}, cert=cert, verify=False)

    if (r.status_code is 202 and r.json()['unlocked']):
      voice_engine.fspeak('Task unlocked')
    else:
      voice_engine.fspeak('Incorrect attempt. Try again.')