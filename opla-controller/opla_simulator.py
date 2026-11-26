
import curses
import json
import time
import re
import uuid
from queue import SimpleQueue, Empty
from getpass import getpass

import paho.mqtt.client as mqtt


# MQTT configuration

BROKER = "localhost"
PORT = 1883
USERNAME = "mqttuser"
PASSWORD = getpass("Enter MQTT password: ")

STATUS_TOPIC = "sauna/status"
PREFIX = "sauna/profiles/"
events = SimpleQueue()

connected = False
latest_status = {}
last_message = 0


# MQTT callbacks

def on_connect(client, userdata, flags, reason_code, properties):
    global connected

    if reason_code == 0:
        connected = True
        client.subscribe([(STATUS_TOPIC, 0), (PREFIX + "list", 1), (PREFIX + "result", 1)])
        client.publish(PREFIX + "request", "{}")
    else:
        connected = False


def on_disconnect(client, userdata, flags, reason_code, properties):
    global connected
    connected = False


def on_message(client, userdata, message):
    global latest_status, last_message

    try:
        data = json.loads(message.payload.decode())

        if message.topic == PREFIX + "list" and isinstance(data, list):
            events.put(("list", data))
        elif message.topic == PREFIX + "result" and isinstance(data, dict):
            events.put(("result", data))
        elif message.topic == STATUS_TOPIC and isinstance(data, dict):
            latest_status = data
            last_message = time.monotonic()

    except (ValueError, UnicodeDecodeError):
        pass


# Profiles received from MQTT

profiles = []


# OPLA navigation

class OplaController:

    def __init__(self, screen):
        self.screen = screen
        self.page = "home"
        self.selected = 0
        self.history = []

        self.sauna_on = False
        self.selected_profile = 0
        self.pending = None
        self.loaded = False
        self.last_request = 0

        self.draft = None
        self.edit_step = 0
        self.adding_profile = False

        self.notification = ""

    def write(self, row, text, color=0):
        height, width = self.screen.getmaxyx()

        if row < height - 1 and width > 2:
            self.screen.addnstr(
                row, 1, str(text), width - 2, color
            )

    def open_page(self, page):
        self.history.append((self.page, self.selected))
        self.page = page
        self.selected = 0
        self.notification = ""

    def home(self):
        self.page = "home"
        self.selected = 0
        self.history = []
        self.draft = None
        self.edit_step = 0
        self.notification = ""

    def back(self):
        if self.page == "edit" and self.edit_step > 0:
            self.edit_step -= 1
            return

        if self.page == "edit":
            self.draft = None

        if self.history:
            self.page, self.selected = self.history.pop()
        else:
            self.home()

        self.notification = ""

    def menu_items(self):

        if self.page == "menu":
            return [
                "Turn sauna OFF" if self.sauna_on
                else "Turn sauna ON",
                "Profiles",
                "Notifications"
            ]

        if self.page == "profiles":
            return [p["name"] + (" [ACTIVE]" if p["active"] else "") for p in profiles] + [
                "Add profile"
            ]

        if self.page == "profile_options":
            return ["Choose", "Edit", "Delete"]

        if self.page == "delete":
            return ["No", "Yes"]

        return []

    def draw_menu(self, items, start_row=5):

        offset = max(0, self.selected - 10)
        for index in range(offset, min(len(items), offset + 11)):
            item = items[index]

            if index == self.selected:
                self.write(
                    start_row + index - offset,
                    "> " + item,
                    curses.A_REVERSE
                )
            else:
                self.write(start_row + index - offset, "  " + item)

    def draw_home(self):

        status = latest_status.copy()

        self.write(
            4,
            "Sauna: " + ("ON" if self.sauna_on else "OFF")
        )

        self.write(
            5,
            "MQTT: " + ("ONLINE" if connected else "OFFLINE"),
            curses.color_pair(1 if connected else 3)
        )

        if not connected:
            self.write(7, "Connection lost", curses.color_pair(3))
            self.write(8, "LED: RED", curses.color_pair(3))
            return

        if not status:
            self.write(7, "Waiting for measurements...")
            return

        if time.monotonic() - last_message > 15:
            self.write(7, "No recent sauna data")
            self.write(8, "LED: RED", curses.color_pair(3))
            return

        self.write(7, "Temperature: {} C".format(
            status.get("temperature", "-")
        ))

        self.write(8, "Humidity: {} %".format(
            status.get("humidity", "-")
        ))

        self.write(10, "Backend profile: {}".format(
            status.get("profile", "-")
        ))

        self.write(11, "Target temperature: {} C".format(
            status.get("target_temperature", "-")
        ))

        self.write(12, "Target humidity: {} %".format(
            status.get("target_humidity", "-")
        ))

        if status.get("ready"):
            self.write(14, "SAUNA READY", curses.color_pair(1))
            self.write(15, "LED: GREEN", curses.color_pair(1))
        else:
            self.write(14, "SAUNA NOT READY", curses.color_pair(2))
            self.write(15, "LED: ORANGE", curses.color_pair(2))

        self.write(17, "Press OK to open menu")

    def draw_edit(self):

        fields = [
            "Profile name",
            "Target temperature",
            "Target humidity"
        ]

        self.write(4, "ADD PROFILE" if self.adding_profile
                   else "EDIT PROFILE")

        self.write(6, "Step {}/3".format(self.edit_step + 1))
        self.write(8, fields[self.edit_step])

        if self.edit_step == 0:
            value = self.draft["name"]

        elif self.edit_step == 1:
            value = str(self.draft["target_temperature"]) + " C"

        else:
            value = str(self.draft["target_humidity"]) + " %"

        self.write(10, "< " + value + " >", curses.A_BOLD)

        if self.edit_step == 2:
            self.write(13, "OK to save")
        else:
            self.write(13, "OK to continue")
        if self.edit_step == 0:
            self.write(15, "- / + changes name number")

    def draw(self):

        self.screen.erase()

        self.write(0, "==============================")
        self.write(1, "          LAMPOALY", curses.A_BOLD)
        self.write(2, "==============================")

        if self.page == "home":
            self.draw_home()

        elif self.page == "menu":
            self.write(4, "MAIN MENU")
            self.draw_menu(self.menu_items(), 6)

        elif self.page == "profiles":
            self.write(4, "PROFILES - DATABASE" if self.loaded else "WAITING FOR PROFILES")
            self.draw_menu(self.menu_items(), 6)

        elif self.page == "profile_options":
            profile = self.profile()

            self.write(4, profile["name"], curses.A_BOLD)
            self.write(6, "Temperature: {} C".format(
                profile["target_temperature"]
            ))
            self.write(7, "Humidity: {} %".format(
                profile["target_humidity"]
            ))

            self.draw_menu(self.menu_items(), 9)

        elif self.page == "edit":
            self.draw_edit()

        elif self.page == "delete":
            self.write(4, "DELETE PROFILE?")
            self.write(6, self.profile()["name"])
            self.draw_menu(self.menu_items(), 8)

        elif self.page == "notifications":
            self.write(4, "NOTIFICATIONS")

            if not connected:
                self.write(6, "MQTT connection lost",
                           curses.color_pair(3))

            elif time.monotonic() - last_message > 15:
                self.write(6, "No recent sensor data",
                           curses.color_pair(3))

            elif latest_status.get("ready"):
                self.write(6, "Sauna is ready",
                           curses.color_pair(1))

            else:
                self.write(6, "No active notifications")

        if self.notification:
            self.write(19, self.notification)

        self.write(21, "==============================")
        self.write(22, "H:HOME B:BACK -:MINUS +:PLUS")
        self.write(23, "ENTER:OK Q:QUIT")

        self.screen.refresh()

    def start_edit(self, adding=False):

        self.adding_profile = adding
        self.edit_step = 0

        if adding:
            number = 1
            names = {p["name"] for p in profiles}
            while f"User {number}" in names:
                number += 1
            self.draft = {"name": f"User {number}",
                          "target_temperature": 80,
                          "target_humidity": 45}
        else:
            self.draft = self.profile().copy()

        self.open_page("edit")

    def adjust(self, direction):

        if self.page == "edit":

            if self.edit_step == 0:

                name = self.draft["name"]
                match = re.search(r"\d+", name)
                if match:
                    number = max(1, min(999, int(match.group()) + direction))
                    self.draft["name"] = name[:match.start()] + str(number) + name[match.end():]
                else:
                    self.draft["name"] = name + " 1"

            elif self.edit_step == 1:
                self.draft["target_temperature"] = max(
                    0, min(100,
                           self.draft["target_temperature"] + direction)
                )

            elif self.edit_step == 2:
                self.draft["target_humidity"] = max(
                    0, min(100,
                           self.draft["target_humidity"] + direction)
                )

            return

        items = self.menu_items()

        if items:
            self.selected = (
                self.selected + direction
            ) % len(items)

    
    def profile(self):
        return next((p for p in profiles if p["id"] == self.selected_profile), None)

    def send(self, action, data):
        if not connected or not self.loaded:
            self.notification = "Profile service unavailable"
            return
        request_id = uuid.uuid4().hex
        payload = dict(data, request_id=request_id)
        result = client.publish(PREFIX + action, json.dumps(payload), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.notification = "Could not send request"
            return
        self.pending = (request_id, action, time.monotonic())
        self.notification = "Waiting for backend..."

    def save_profile(self):
        self.send("create" if self.adding_profile else "update", self.draft)

    def process_events(self):
        global profiles
        while True:
            try:
                kind, data = events.get_nowait()
            except Empty:
                break
            if kind == "list":
                old_id = (profiles[self.selected]["id"]
                          if self.page == "profiles" and self.selected < len(profiles) else None)
                profiles = data
                self.loaded = True
                if self.page == "profiles":
                    self.selected = next((i for i, p in enumerate(profiles) if p["id"] == old_id), len(profiles))
                if self.page in ("profile_options", "delete", "edit") and not (self.page == "edit" and self.adding_profile) and self.profile() is None:
                    self.home()
                    self.notification = "Profile no longer exists"
            elif self.pending and data.get("request_id") == self.pending[0]:
                action = self.pending[1]
                self.pending = None
                if data.get("success"):
                    self.home()
                self.notification = data.get("message", "Unknown result")
                client.publish(PREFIX + "request", "{}")
        if not connected:
            self.loaded = False
        now = time.monotonic()
        if connected and now - self.last_request >= 5:
            client.publish(PREFIX + "request", "{}")
            self.last_request = now
        if self.pending and now - self.pending[2] > 12:
            self.pending = None
            self.notification = "Result unknown; check profiles before retry"
            client.publish(PREFIX + "request", "{}")

    def confirm(self):

        if self.page == "home":
            self.open_page("menu")

        elif self.page == "menu":

            if self.selected == 0:
                self.sauna_on = not self.sauna_on
                self.home()

            elif self.selected == 1:
                self.open_page("profiles")

            elif self.selected == 2:
                self.open_page("notifications")

        elif self.page == "profiles":

            if not self.loaded or not connected:
                self.notification = "Waiting for profile service"
                return
            if self.selected == len(profiles):
                self.start_edit(adding=True)
            else:
                self.selected_profile = profiles[self.selected]["id"]
                self.open_page("profile_options")

        elif self.page == "profile_options":

            if self.selected == 0:
                self.send("activate", {"id": self.selected_profile})

            elif self.selected == 1:
                self.start_edit()

            elif self.selected == 2:

                if self.profile()["active"]:
                    self.notification = "Cannot delete active profile"
                else:
                    self.open_page("delete")

        elif self.page == "edit":

            if self.edit_step < 2:
                self.edit_step += 1
            else:
                self.save_profile()

        elif self.page == "delete":

            if self.selected == 1:

                self.send("delete", {"id": self.selected_profile})

            else:
                self.back()

    def run(self):

        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)

        self.screen.keypad(True)
        self.screen.timeout(200)

        while True:

            self.process_events()
            self.draw()
            key = self.screen.getch()

            if key in (ord("q"), ord("Q")):
                break

            elif self.pending:
                continue

            elif key in (ord("h"), ord("H")):
                self.home()

            elif key in (ord("b"), ord("B")):
                self.back()

            elif key in (ord("-"), curses.KEY_LEFT,
                         curses.KEY_UP):
                self.adjust(-1)

            elif key in (ord("+"), ord("="),
                         curses.KEY_RIGHT, curses.KEY_DOWN):
                self.adjust(1)

            elif key in (10, 13, curses.KEY_ENTER):
                self.confirm()


def main(screen):
    controller = OplaController(screen)
    controller.run()


# Start MQTT connection

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

client.username_pw_set(USERNAME, PASSWORD)

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

client.reconnect_delay_set(min_delay=1, max_delay=30)
client.connect(BROKER, PORT, 60)
client.loop_start()

try:
    curses.wrapper(main)

except KeyboardInterrupt:
    pass

finally:
    client.disconnect()
    client.loop_stop()
