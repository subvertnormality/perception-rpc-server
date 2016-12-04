#!/usr/bin/env python3

import json
import sys
import time
import cozmo
import concurrent.futures as futures
import grpc
import control_pb2
import logging
from io import BytesIO
from PIL import Image

remote_control_cozmo = None

class RemoteControlCozmo:

    def __init__(self, coz):
        self.cozmo = coz
        self.reset()

    def reset(self):
        self.drive_forwards = 0
        self.drive_back = 0
        self.turn_left = 0
        self.turn_right = 0
        self.lift_up = 0
        self.lift_down = 0
        self.head_up = 0
        self.head_down = 0

        self.go_fast = 0
        self.go_slow = 0

        self.action_queue = []

        self.update_driving()
        self.update_head()
        self.update_lift()

    def handle_key(self, key_code, is_shift_down, is_ctrl_down, is_alt_down, is_key_down):
        '''Called on any key press or release
           Holding a key down may result in repeated handle_key calls with is_key_down==True
        '''
         # Update desired speed / fidelity of actions based on shift/alt being held
        was_go_fast = self.go_fast
        was_go_slow = self.go_slow

        self.go_fast = is_shift_down
        self.go_slow = is_alt_down

        speed_changed = (was_go_fast != self.go_fast) or (was_go_slow != self.go_slow)

        # Update state of driving intent from keyboard, and if anything changed then call update_driving
        update_driving = True
        if key_code == ord('W'):
            self.drive_forwards = is_key_down
        elif key_code == ord('S'):
            self.drive_back = is_key_down
        elif key_code == ord('A'):
            self.turn_left = is_key_down
        elif key_code == ord('D'):
            self.turn_right = is_key_down
        else:
            if not speed_changed:
                update_driving = False

        # Update state of lift move intent from keyboard, and if anything changed then call update_lift
        update_lift = True
        if key_code == ord('R'):
            self.lift_up = is_key_down
        elif key_code == ord('F'):
            self.lift_down = is_key_down
        else:
            if not speed_changed:
                update_lift = False

        # Update state of head move intent from keyboard, and if anything changed then call update_head
        update_head = True
        if key_code == ord('T'):
            self.head_up = is_key_down
        elif key_code == ord('G'):
            self.head_down = is_key_down
        else:
            if not speed_changed:
                update_head = False

        # Update driving, head and lift as appropriate
        if update_driving:
            self.update_driving()
        if update_head:
            self.update_head()
        if update_lift:
            self.update_lift()


    def queue_action(self, new_action):
        if len(self.action_queue) > 10:
            self.action_queue.pop(0)
        self.action_queue.append(new_action)


    def try_say_text(self, text_to_say):
        try:
            self.cozmo.say_text(text_to_say, False, True, 1.0, -16.0)
            return True
        except cozmo.exceptions.RobotBusy:
            return False


    def try_play_anim(self, anim_name):
        try:
            self.cozmo.play_anim(name=anim_name)
            return True
        except cozmo.exceptions.RobotBusy:
            return False


    def say_text(self, text_to_say):
        self.queue_action((self.try_say_text, text_to_say))
        self.update()


    def play_animation(self, anim_name):
        self.queue_action((self.try_play_anim, anim_name))
        self.update()


    def update(self):
        '''Try and execute the next queued action'''
        if len(self.action_queue) > 0:
            queued_action, action_args = self.action_queue[0]
            if queued_action(action_args):
                self.action_queue.pop(0)


    def pick_speed(self, fast_speed, mid_speed, slow_speed):
        if self.go_fast:
            if not self.go_slow:
                return fast_speed
        elif self.go_slow:
            return slow_speed
        return mid_speed


    def update_lift(self):
        lift_speed = self.pick_speed(8, 4, 2)
        lift_vel = (self.lift_up - self.lift_down) * lift_speed
        self.cozmo.move_lift(lift_vel)


    def update_head(self):
        head_speed = self.pick_speed(2, 1, 0.5)
        head_vel = (self.head_up - self.head_down) * head_speed
        self.cozmo.move_head(head_vel)


    def update_driving(self):
        drive_dir = (self.drive_forwards - self.drive_back)

        if (drive_dir > 0.1) and self.cozmo.is_on_charger:
            # cozmo is stuck on the charger, and user is trying to drive off - issue an explicit drive off action
            try:
                self.cozmo.drive_off_charger_contacts().wait_for_completed()
            except cozmo.exceptions.RobotBusy:
                # Robot is busy doing another action - try again next time we get a drive impulse
                pass

        turn_dir = (self.turn_right - self.turn_left)

        if drive_dir < 0:
            # It feels more natural to turn the opposite way when reversing
            turn_dir = -turn_dir

        forward_speed = self.pick_speed(150, 75, 50)
        turn_speed = self.pick_speed(100, 50, 30)

        l_wheel_speed = (drive_dir * forward_speed) + (turn_speed * turn_dir)
        r_wheel_speed = (drive_dir * forward_speed) - (turn_speed * turn_dir)

        self.cozmo.drive_wheels(l_wheel_speed, r_wheel_speed, l_wheel_speed*4, r_wheel_speed*4)


class Control(control_pb2.ControlServicer):

    def __init__(self):
        image_bytes = bytearray([0x70, 0x70, 0x70]) * 320 * 240
        default_camera_image = Image.frombytes('RGB', (320, 240), bytes(image_bytes))
        self.last_camera_image = control_pb2.ImageReply(image=(self.serve_pil_image(default_camera_image)))
        self.last_camera_update_time = int(time.time() * 1000)

    def serve_pil_image(self, pil_img, jpeg_quality=50):
        '''Convert PIL image to relevant image file and send it'''
        img_io = BytesIO()
        pil_img.save(img_io, 'JPEG')
        img_io.seek(0)

        return img_io.getvalue()

    def handleImageGetEvent(self, payload, more):
        if remote_control_cozmo:
            image = remote_control_cozmo.cozmo.world.latest_image
            if image:
                curr_time = int(time.time() * 1000)
                if (curr_time - self.last_camera_update_time > 33):
                    self.last_camera_update_time = curr_time
                    new_camera_image = control_pb2.ImageReply(image=(self.serve_pil_image(image.raw_image)))
                    self.last_camera_image = new_camera_image
                    return new_camera_image
                return self.last_camera_image
        return self.last_camera_image


    def handleKeyEvent(self, payload, keyDown):
        if remote_control_cozmo:
            remote_control_cozmo.handle_key(key_code=(payload.key_code), is_shift_down=payload.is_shift_down,
                                            is_ctrl_down=payload.is_ctrl_down, is_alt_down=payload.is_alt_down,
                                            is_key_down=payload.is_key_down)
        return control_pb2.Reply(message="Success")


    def handleSayTextEvent(self, payload, more):
        if remote_control_cozmo:
            remote_control_cozmo.try_say_text(payload.text)
            return control_pb2.Reply(message="Cozmo successfully said " + payload.text)

    def handleResetEvent(self, payload, more):
        if remote_control_cozmo:
            remote_control_cozmo.reset()
        return control_pb2.Reply(message="Success")


def run(sdk_conn):
    robot = sdk_conn.wait_for_robot()

    global remote_control_cozmo
    remote_control_cozmo = RemoteControlCozmo(robot)

    # Turn on image receiving by the camera
    robot.camera.image_stream_enabled = True

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    control_pb2.add_ControlServicer_to_server(Control(), server)
    server.add_insecure_port('[::]:50051')
    server.start()

    while True:
        time.sleep(1)

if __name__ == '__main__':
    cozmo.setup_basic_logging()
    while True:
        try:
            cozmo.connect(run, connector=cozmo.run.FirstAvailableConnector())
            break
        except cozmo.ConnectionError as e:
            logging.error("A connection error occurred: %s. Retrying in 10 seconds" % e)
            time.sleep(10)

