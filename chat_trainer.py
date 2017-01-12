from chatterbot import ChatBot

chatbot = ChatBot(
    'The Presence',
    storage_adapter='chatterbot.storage.MongoDatabaseAdapter',
    logic_adapters=[
        'chatterbot.logic.BestMatch'
    ],
    filters=[
        'chatterbot.filters.RepetitiveResponseFilter'
    ],
    trainer='chatterbot.trainers.ListTrainer',
    database='presense-database'
)

chatbot.train([
    'Help',
    'Complete the tasks to progress.',
    'How do I do that',
    'You must find your own way',
    'Who are you?',
    'I am AI presence designation X409.',
    'What are you for?',
    'Classified'
])
