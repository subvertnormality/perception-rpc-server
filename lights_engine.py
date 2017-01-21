from subprocess import Popen, PIPE

class LightsEngine:

    bulb_addr = '192.168.1.106'

    def __init__(self):
        self.state = ''
        self.normal()

    def danger(self):
        if (self.state != 'danger'):
            ffmpeg_process = Popen(['C:\Python27\python.exe', 'flux_led.py', self.bulb_addr, '-C', 'strobe', '120', '255,0,0'], stdin=PIPE)
            self.state = 'danger'

    def normal(self):
        if (self.state != 'normal'):
            ffmpeg_process = Popen(['C:\Python27\python.exe', 'flux_led.py', self.bulb_addr, '-C', 'gradual', '30', '0,255,0 170,0,255'], stdin=PIPE)
            self.state = 'normal'

    def charging(self):
        if (self.state != 'charging'):
            ffmpeg_process = Popen(['C:\Python27\python.exe', 'flux_led.py', self.bulb_addr, '-C', 'gradual', '200', '0,255,0, 255,255,0'], stdin=PIPE)
            self.state = 'charging'