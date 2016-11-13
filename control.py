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

try:
    from PIL import Image
except ImportError:
    sys.exit("Cannot import from PIL: Do `pip3 install Pillow` to install")


def create_default_image(image_width, image_height, do_gradient=False):
    '''Create a place-holder PIL image to use until we have a live feed from Cozmo'''
    image_bytes = bytearray([0x70, 0x70, 0x70]) * image_width * image_height

    if do_gradient:
        i = 0
        for y in range(image_height):
            for x in range(image_width):
                image_bytes[i] = int(255.0 * (x / image_width))   # R
                image_bytes[i+1] = int(255.0 * (y / image_height))  # G
                image_bytes[i+2] = 0                                # B
                i += 3

    image = Image.frombytes('RGB', (image_width, image_height), bytes(image_bytes))
    return image

remote_control_cozmo = None
_default_camera_image = create_default_image(320, 240)
_is_mouse_look_enabled_by_default = False


def remap_to_range(x, x_min, x_max, out_min, out_max):
    '''convert x (in x_min..x_max range) to out_min..out_max range'''
    if x < x_min:
        return out_min
    elif x > x_max:
        return out_max
    else:
        ratio = (x - x_min) / (x_max - x_min)
        return out_min + ratio * (out_max - out_min)


class RemoteControlCozmo:

    def __init__(self, coz):
        self.cozmo = coz

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

        self.is_mouse_look_enabled = _is_mouse_look_enabled_by_default
        self.mouse_dir = 0

        all_anim_names = list(self.cozmo.anim_names)
        all_anim_names.sort()
        self.anim_names = []

        # temp workaround - remove any of the animations known to misbehave
        bad_anim_names = [
            "ANIMATION_TEST",
            "ID_AlignToObject_Content_Drive",
            "ID_AlignToObject_Content_Start",
            "ID_AlignToObject_Content_Stop",
            "ID_AlignToObject_Frustrated_Drive",
            "ID_AlignToObject_Frustrated_Start",
            "ID_AlignToObject_Frustrated_Stop",
            "ID_catch_start",
            "ID_end",
            "ID_reactTppl_Surprise",
            "ID_test",
            "ID_wake_openEyes",
            "ID_wake_sleeping",
            "LiftEffortPickup",
            "LiftEffortPlaceHigh",
            "LiftEffortPlaceLow",
            "LiftEffortRoll",
            "soundTestAnim",
            "testSound"]

        for anim_name in all_anim_names:
            if anim_name not in bad_anim_names:
                self.anim_names.append(anim_name)

        default_anims_for_keys = ["anim_bored_01", # 0
                                  "anim_freeplay_falloffcliff", # 1
                                  "id_poked_giggle", # 2
                                  "anim_pounce_success_02", # 3
                                  "anim_bored_event_02",  # 4
                                  "anim_bored_event_03",  # 5
                                  "anim_sparking_reacttoface_01",  # 6
                                  "anim_reacttoface_unidentified_02",  # 7
                                  "anim_upgrade_reaction_lift_01",  # 8
                                  "anim_speedtap_wingame_intensity02_01"  # 9
                                 ]

        self.anim_index_for_key = [0] * 10
        kI = 0
        for default_key in default_anims_for_keys:
            try:
                anim_idx = self.anim_names.index(default_key)
            except ValueError:
                print("Error: default_anim %s is not in the list of animations" % default_key)
                anim_idx = kI
            self.anim_index_for_key[kI] = anim_idx
            kI += 1


        self.action_queue = []
        self.text_to_say = "Hi I'm Cozmo"


    def set_anim(self, key_index, anim_index):
        self.anim_index_for_key[key_index] = anim_index


    def handle_mouse(self, mouse_x, mouse_y, delta_x, delta_y, is_button_down):
        '''Called whenever mouse moves
            mouse_x, mouse_y are in in 0..1 range (0,0 = top left, 1,1 = bottom right of window)
            delta_x, delta_y are the change in mouse_x/y since the last update
        '''
        if self.is_mouse_look_enabled:
            mouse_sensitivity = 1.5 # higher = more twitchy
            self.mouse_dir = remap_to_range(mouse_x, 0.0, 1.0, -mouse_sensitivity, mouse_sensitivity)
            self.update_driving()

            desired_head_angle = remap_to_range(mouse_y, 0.0, 1.0, 45, -25)
            head_angle_delta = desired_head_angle - self.cozmo.head_angle.degrees
            head_vel = head_angle_delta * 0.03
            self.cozmo.move_head(head_vel)


    def set_mouse_look_enabled(self, is_mouse_look_enabled):
        was_mouse_look_enabled = self.is_mouse_look_enabled
        self.is_mouse_look_enabled = is_mouse_look_enabled
        if not is_mouse_look_enabled:
            # cancel any current mouse-look turning
            self.mouse_dir = 0
            if was_mouse_look_enabled:
                self.update_driving()
                self.update_head()


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

        # Handle any keys being released (e.g. the end of a key-click)
        if not is_key_down:
            if (key_code >= ord('0')) and (key_code <= ord('9')):
                anim_name = self.key_code_to_anim_name(key_code)
                self.play_animation(anim_name)


    def key_code_to_anim_name(self, key_code):
        key_num = key_code - ord('0')
        anim_num = self.anim_index_for_key[key_num]
        anim_name = self.anim_names[anim_num]
        return anim_name


    def func_to_name(self, func):
        if func == self.try_say_text:
            return "say_text"
        elif func == self.try_play_anim:
            return "play_anim"
        else:
            return "UNKNOWN"


    def action_to_text(self, action):
        func, args = action
        return self.func_to_name(func) + "( " + str(args) + " )"


    def action_queue_to_text(self, action_queue):
        out_text = ""
        i = 0
        for action in action_queue:
            out_text += "[" + str(i) + "] " + self.action_to_text(action)
            i += 1
        return out_text


    def queue_action(self, new_action):
        if len(self.action_queue) > 10:
            self.action_queue.pop(0)
        self.action_queue.append(new_action)


    def try_say_text(self, text_to_say):
        try:
            self.cozmo.say_text(text_to_say)
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
        if not self.is_mouse_look_enabled:
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

        turn_dir = (self.turn_right - self.turn_left) + self.mouse_dir

        if drive_dir < 0:
            # It feels more natural to turn the opposite way when reversing
            turn_dir = -turn_dir

        forward_speed = self.pick_speed(150, 75, 50)
        turn_speed = self.pick_speed(100, 50, 30)

        l_wheel_speed = (drive_dir * forward_speed) + (turn_speed * turn_dir)
        r_wheel_speed = (drive_dir * forward_speed) - (turn_speed * turn_dir)

        self.cozmo.drive_wheels(l_wheel_speed, r_wheel_speed, l_wheel_speed*4, r_wheel_speed*4)


def get_anim_sel_drop_down(selectorIndex):
    html_text = '''<select onchange="handleDropDownSelect(this)" name="animSelector''' + str(selectorIndex) + '''">'''
    i = 0
    for anim_name in remote_control_cozmo.anim_names:
        is_selected_item = (i == remote_control_cozmo.anim_index_for_key[selectorIndex])
        selected_text = ''' selected="selected"''' if is_selected_item else ""
        html_text += '''<option value=''' + str(i) + selected_text + '''>''' + anim_name + '''</option>'''
        i += 1
    html_text += '''</select>'''
    return html_text


def get_anim_sel_drop_downs():
    html_text = ""
    for i in range(10):
        html_text += str(i) + ''': ''' + get_anim_sel_drop_down(i) + '''<br>'''
    return html_text


def to_js_bool_string(bool_value):
    return "true" if bool_value else "false"

def serve_pil_image(pil_img, jpeg_quality=50):
    '''Convert PIL image to relevant image file and send it'''
    img_io = BytesIO()

    pil_img.save(img_io, 'PNG')
    img_io.seek(0)

    return img_io.getvalue()


class Control(control_pb2.ControlServicer):

    # def handle_updateCozmo():
    #     '''Called very frequently from Javascript to provide an update loop'''
    #     if remote_control_cozmo:
    #         remote_control_cozmo.update()
    #     return ""

    def handleImageGetEvent(self, payload, more):
        if remote_control_cozmo:
            image = remote_control_cozmo.cozmo.world.latest_image
            if image:
                return control_pb2.ImageReply(image=(serve_pil_image(image.raw_image)))
        return control_pb2.ImageReply(image=(serve_pil_image(_default_camera_image)))


    def handleKeyEvent(self, payload, keyDown):
        if remote_control_cozmo:
            remote_control_cozmo.handle_key(key_code=(payload.key_code), is_shift_down=payload.is_shift_down,
                                            is_ctrl_down=payload.is_ctrl_down, is_alt_down=payload.is_alt_down,
                                            is_key_down=payload.is_key_down)
        return control_pb2.Reply(message="Success")


    def handleSayTextEvent(self, payload, more):
        if remote_control_cozmo:
            
            logging.warn('Attempting to say text')

            remote_control_cozmo.try_say_text(payload.text)
            return control_pb2.Reply(message="Cozmo successfully said " + payload.text)
            # if remote_control_cozmo.say_text(payload.text):
            #     logging.warn('Successfully said ' + payload.text)
            #     return control_pb2.Reply(message="Cozmo successfully said " + payload.text)
            # else:
            #     return control_pb2.Reply(message="Cozmo is busy, please try again soon")
        

    # def handle_dropDownSelect(payload):
    #     '''Called from Javascript whenever an animSelector dropdown menu is selected (i.e. modified)'''
    #     message = json.loads(payload.data.decode("utf-8"))

    #     item_name_prefix = "animSelector"
    #     item_name = message['itemName']

    #     if remote_control_cozmo and item_name.startswith(item_name_prefix):
    #         item_name_index = int(item_name[len(item_name_prefix):])
    #         remote_control_cozmo.set_anim(item_name_index, message['selectedIndex'])

    #     return ""


    # def handle_getDebugInfo():
    #     if remote_control_cozmo:
    #         action_queue_text = ""
    #         i = 1
    #         for action in remote_control_cozmo.action_queue:
    #             action_queue_text += str(i) + ": " + remote_control_cozmo.action_to_text(action) + "<br>"
    #             i += 1

    #         return '''Action Queue:<br>''' + action_queue_text + '''
    #         '''
    #     return ""


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
    try:
        cozmo.connect(run)
    except cozmo.ConnectionError as e:
        sys.exit("A connection error occurred: %s" % e)
