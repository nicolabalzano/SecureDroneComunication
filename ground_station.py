import paho.mqtt.client as mqtt
import ssl
import json
import threading
import sys
import termios
import tty
import logging
import random

# Setup logging
logging.basicConfig(level=logging.INFO)

# MQTT parameters
BROKER = "127.0.0.1"
PORT = 8883
TOPIC_TELEMETRY = "drone/telemetry"
TOPIC_COMMAND = "drone/command"
CERT_CA = "/etc/mosquitto/ca_certificates/ca.crt"
CERT_FILE = "/etc/mosquitto/certs/client.crt"
KEY_FILE = "/etc/mosquitto/certs/client.key"

# Parameters for random positions
MAX_DISTANCE = 50  # meters
MIN_ALTITUDE = 10   # meters
MAX_ALTITUDE = 30   # meters

# Function to generate a random position
def generate_random_position():
    x = random.uniform(-MAX_DISTANCE, MAX_DISTANCE)
    y = random.uniform(-MAX_DISTANCE, MAX_DISTANCE)
    z = random.uniform(MIN_ALTITUDE, MAX_ALTITUDE)
    return {"lat": x, "lon": y, "alt": z}

# Telemetry callback
def on_message(client, userdata, message):
    #logging.info(f"Telemetry received: {message.payload.decode()}")
    pass

# Read keys without enter
def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# Keyboard input management thread
def keyboard_loop(client):
    logging.info("Drone control: WASD for movement, Q/E up/down, C takeoff, X land, SPACE to stop.")
    logging.info("G to enter manual coordinates, R to generate random position.")
    while True:
        key = getch().lower()
        cmd = {}
        
        # Speed commands for GUIDED mode
        meter_per_second = 5.0
        if key == 'w':
            cmd = {'velocity': {"vx": meter_per_second, "vy": 0.0, "vz": 0.0}} 
        elif key == 's':
            cmd = {'velocity': {"vx": -meter_per_second, "vy": 0.0, "vz": 0.0}} 
        elif key == 'a':
            cmd = {'velocity': {"vx": 0.0, "vy": -meter_per_second, "vz": 0.0}} 
        elif key == 'd':
            cmd = {'velocity': {"vx": 0.0, "vy": meter_per_second, "vz": 0.0}}
        elif key == 'q':
            cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": -meter_per_second/2}}
        elif key == 'e':
            cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": meter_per_second/2}}
        elif key == ' ':  # Space to stop
            cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": 0.0}}  # Stop
            
        # Existing modes and commands
        elif key == 'c':
            cmd = {'mode': 'GUIDED', 'takeoff_alt': 10}
        elif key == 'm':
            cmd = {'mode': 'STABILIZE'}
        elif key == 'l':
            cmd = {'mode': 'LOITER'}
        elif key == 'x':
            cmd = {'mode': 'LAND'}
        elif key == 'h':
            cmd = {'return_home': True}
            logging.info("Return to home command")
        # New commands for autonomous navigation
        elif key == 'p':
            try:
                print("\nEnter destination coordinates")
                lat = float(input("Latitude: "))
                lon = float(input("Longitude: "))
                alt = float(input("Altitude (m): "))
                cmd = {'position': {"lat": lat, "lon": lon, "alt": alt}}
                print("Sending position command...")
            except ValueError:
                logging.error("Invalid input. Use numeric values.")
                continue
        elif key == 'r':
            random_pos = generate_random_position()
            cmd = {'position': random_pos}
            logging.info(f"Generated random position: {random_pos}")
        elif key == '.':
            exit(1)
        else:
            continue

        payload = json.dumps(cmd)
        client.publish(TOPIC_COMMAND, payload)
        logging.info(f"Sent command: {payload}")

# Setup MQTT
client = mqtt.Client()
client.tls_set(
    ca_certs=CERT_CA,
    certfile=CERT_FILE,
    keyfile=KEY_FILE,
    tls_version=ssl.PROTOCOL_TLSv1_2
)
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.subscribe(TOPIC_TELEMETRY)
client.loop_start()
logging.info(f"Ground Station connected, subscribed to {TOPIC_TELEMETRY}")

# Start keyboard thread
keyboard_thread = threading.Thread(target=keyboard_loop, args=(client,))
keyboard_thread.daemon = True
keyboard_thread.start()

# Keep alive
try:
    while True:
        pass
except KeyboardInterrupt:
    logging.info("Closing Ground Station")
    client.loop_stop()
    sys.exit(0)
