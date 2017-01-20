from subprocess import Popen, PIPE

class RemoteControlCozmo:

    bulb_addr = '192.168.1.100'

    def __init__(self):
        self.state = ''
        self.normal()

    def danger():
        if (self.state != 'danger'):
            ffmpeg_process = Popen(['flux_led.py', self.bulb_addr, '-C', 'strobe', 80, '"red"'], stdin=PIPE)
            self.state = 'danger'

    def normal():
        if (self.state != 'normal'):
            ffmpeg_process = Popen(['flux_led.py', self.bulb_addr, '-C', 'gradual', 10, '"green, purple"'], stdin=PIPE)
            self.state = 'normal'

    def charging():
        if (self.state != charging):
            ffmpeg_process = Popen(['flux_led.py', self.bulb_addr, '-C', 'strobe', 80, '"green, yellow"'], stdin=PIPE)
            self.state = 'charging'