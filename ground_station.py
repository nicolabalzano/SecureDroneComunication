import paho.mqtt.client as mqtt
import ssl
import json
import threading
import sys
import termios
import tty
import logging
import random
import time
import argparse
import uuid
import os
from datetime import datetime

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Ground station MQTT client')
parser.add_argument('--no-tls', action='store_true', help='Disable TLS encryption')
args = parser.parse_args()

# Create logs directory if it doesn't exist
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Setup logging for application
logging.basicConfig(level=logging.INFO)

# Setup timing logger to capture message transit times
current_date = datetime.now().strftime("%Y-%m-%d")
timing_log_filename = f"{LOG_DIR}/mqtt_timing_{current_date}.log"

# Configure timing logger
timing_logger = logging.getLogger("mqtt_timing")
timing_logger.setLevel(logging.INFO)

# Add file handler for timing log
timing_file_handler = logging.FileHandler(timing_log_filename)
timing_formatter = logging.Formatter('%(asctime)s - %(message)s')
timing_file_handler.setFormatter(timing_formatter)
timing_logger.addHandler(timing_file_handler)

# Add console handler for timing log (optional)
timing_console_handler = logging.StreamHandler()
timing_console_handler.setFormatter(timing_formatter)
timing_logger.addHandler(timing_console_handler)

# Dictionary to store message send times
message_times = {}

# TLS Configuration - can be disabled via command-line
USE_TLS = not args.no_tls
logging.info(f"TLS encryption: {'Enabled' if USE_TLS else 'Disabled'}")
timing_logger.info(f"Ground Station started - TLS: {'Enabled' if USE_TLS else 'Disabled'}")

# MQTT parameters
BROKER = "127.0.0.1"
PORT_TLS = 8883
PORT_NO_TLS = 1883  # Standard MQTT port without TLS
PORT = PORT_TLS if USE_TLS else PORT_NO_TLS
TOPIC_TELEMETRY = "drone/telemetry"
TOPIC_COMMAND = "drone/command"
CERT_CA = "/etc/mosquitto/ca_certificates/ca.crt"
CERT_FILE = "/etc/mosquitto/certs/client.crt"
KEY_FILE = "/etc/mosquitto/certs/client.key"

# Parameters for random positions
MAX_DISTANCE = 50  # meters
MIN_ALTITUDE = 10   # meters
MAX_ALTITUDE = 30   # meters

# Global variable to store current drone altitude
current_altitude = 0.0
relative_altitude = 0.0
# Flag to track vertical movement
vertical_movement = False
# Flag to control altitude monitoring thread
altitude_monitoring = False

# Function to generate a random position
def generate_random_position():
    x = random.uniform(-MAX_DISTANCE, MAX_DISTANCE)
    y = random.uniform(-MAX_DISTANCE, MAX_DISTANCE)
    z = random.uniform(MIN_ALTITUDE, MAX_ALTITUDE)
    return {"lat": x, "lon": y, "alt": z}

# Telemetry callback
def on_message(client, userdata, message):
    global current_altitude, relative_altitude
    try:
        telemetry_data = json.loads(message.payload.decode())
        
        # Check for message_id to calculate timing
        message_id = telemetry_data.get('message_id')
        if message_id:
            receive_time = time.time()
            message_type = telemetry_data.get('type', 'unknown')
            timing_logger.info(f"GS-RECV: Message ID {message_id} type {message_type} received at {receive_time:.6f}")
        
        if 'alt' in telemetry_data:
            current_altitude = telemetry_data['alt']
            relative_altitude = telemetry_data['relative_alt']
    except Exception as e:
        logging.error(f"Error parsing telemetry data: {e}")

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

# Function to monitor and display altitude in real time
def monitor_altitude():
    global altitude_monitoring, vertical_movement
    altitude_monitoring = True
    previous_alt = current_altitude
    previous_rel_alt = relative_altitude
    
    while altitude_monitoring:
        if vertical_movement:
            # Only log if altitude has changed significantly
            if abs(current_altitude - previous_alt) > 0.1 or abs(relative_altitude - previous_rel_alt) > 0.1:
                print(f"\033[2K\rAltitude update - absolute: {current_altitude:.1f}m, relative: {relative_altitude:.1f}m", end='')
                sys.stdout.flush()
                previous_alt = current_altitude
                previous_rel_alt = relative_altitude
        time.sleep(0.5)

# Keyboard input management thread
def keyboard_loop(client):
    global vertical_movement, altitude_monitoring
    logging.info("Drone control: WASD for movement, Q/E up/down, C takeoff, X land, SPACE to stop.")
    logging.info("G to enter manual coordinates, R to generate random position.")
    meter_per_second = 5.0
    
    # Start altitude monitoring thread
    alt_thread = threading.Thread(target=monitor_altitude)
    alt_thread.daemon = True
    alt_thread.start()
    
    while True:
        key = getch().lower()
        cmd = {}
        
        # Speed commands for GUIDED mode
        if key == '+':
            meter_per_second += 1.0
            logging.info(f"Speed increased to {meter_per_second} m/s")
        elif key == '-':
            meter_per_second -= 1.0
            if meter_per_second < 0:
                meter_per_second = 0
            logging.info(f"Speed decreased to {meter_per_second} m/s")
        elif key == 'w':
            cmd = {'velocity': {"vx": meter_per_second, "vy": 0.0, "vz": 0.0}} 
        elif key == 's':
            cmd = {'velocity': {"vx": -meter_per_second, "vy": 0.0, "vz": 0.0}} 
        elif key == 'a':
            cmd = {'velocity': {"vx": 0.0, "vy": -meter_per_second, "vz": 0.0}} 
        elif key == 'd':
            cmd = {'velocity': {"vx": 0.0, "vy": meter_per_second, "vz": 0.0}}
        elif key == 'q':
            cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": -meter_per_second/2}}
            vertical_movement = True
            logging.info(f"Moving down, starting from altitude - absolute: {current_altitude:.1f}m, relative: {relative_altitude:.1f}m")
        elif key == 'e':
            cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": meter_per_second/2}}
            vertical_movement = True
            logging.info(f"Moving up, starting from altitude - absolute: {current_altitude:.1f}m, relative: {relative_altitude:.1f}m")
        elif key == ' ':  # Space to stop
            cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": 0.0}}  # Stop
            vertical_movement = False
            logging.info(f"Stopped at altitude - absolute: {current_altitude:.1f}m, relative: {relative_altitude:.1f}m")
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
            cmd = {'mode': 'RTL'}
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

        # Add unique message ID for timing tracking
        message_id = str(uuid.uuid4())
        cmd['message_id'] = message_id
        
        # Log send time
        send_time = time.time()
        message_times[message_id] = send_time
        
        # Determine message type for logging
        message_type = "unknown"
        if 'velocity' in cmd:
            message_type = "velocity"
        elif 'mode' in cmd:
            message_type = f"mode_{cmd['mode']}"
        elif 'position' in cmd:
            message_type = "position"
        elif 'takeoff_alt' in cmd:
            message_type = "takeoff"
        
        payload = json.dumps(cmd)
        client.publish(TOPIC_COMMAND, payload)
        
        # Log the timing information
        timing_logger.info(f"GS-SEND: Message ID {message_id} type {message_type} sent at {send_time:.6f}")
        logging.info(f"Sent command: {payload}")

# Setup MQTT
client = mqtt.Client()

# Apply TLS settings only if enabled
if USE_TLS:
    logging.info("Configuring MQTT with TLS security")
    client.tls_set(
        ca_certs=CERT_CA,
        certfile=CERT_FILE,
        keyfile=KEY_FILE,
        tls_version=ssl.PROTOCOL_TLSv1_2
    )
else:
    logging.info("Configuring MQTT without TLS security")
    
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
    altitude_monitoring = False  # Stop altitude monitoring thread
    client.loop_stop()
    sys.exit(0)
