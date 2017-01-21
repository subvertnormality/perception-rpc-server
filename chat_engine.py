import voice_engine
from chatterbot import ChatBot
from threading import Thread
import requests

url = 'https://game.playperception.com/game/attemptunlockround/'
url_local = 'https://game.localhost/game/attemptunlockround/'

cert_file_path = "certs/client.crt"
key_file_path = "certs/client.key"
cert = (cert_file_path, key_file_path)

keywords = [ 
  'hello',
  'help',
  'Kappa',
  'BibleThump',
  'PJSalt',
  'DansGame',
  'Jebaited',
  'PogChamp'
]

chatbot = ChatBot(
    'The Presence',
    storage_adapter='chatterbot.storage.MongoDatabaseAdapter',
    logic_adapters=[
        'chatterbot.logic.BestMatch',
        {
            'import_path': 'chatterbot.logic.LowConfidenceAdapter',
            'threshold': 0.65,
            'default_response': ''
        }
    ],
    filters=[
        'chatterbot.filters.RepetitiveResponseFilter'
    ],
    database='presense-chat-database'
)

def process_speech_input(input):

  if (len(input.split()) > 1 or input in keywords):
    voice_engine.mspeak(input)
    response = chatbot.get_response(input)
    t = Thread(target=voice_engine.fspeak, args=[response])
    t.daemon = True
    t.start()
    return str(response)
  else:
    voice_engine.mspeak(input)
    r = requests.post(url, json={'attempt': input}, cert=cert, verify=False)

    if (r.status_code is 202 and r.json()['unlocked']):
      response = 'Task unlocked'
      t = Thread(target=voice_engine.fspeak, args=[response])
      t.daemon = True
      t.start()
      return str(response)
    else:
      response = 'Incorrect attempt. Try again.'
      t = Thread(target=voice_engine.fspeak, args=[response])
      t.daemon = True
      t.start()
      return str(response)