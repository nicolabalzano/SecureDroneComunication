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
import os
from datetime import datetime
import uuid

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Ground station MQTT client')
parser.add_argument('--no-tls', action='store_true', help='Disable TLS encryption')
parser.add_argument('--automated', action='store_true', help='Run in automated mode')
parser.add_argument('--test-time-encryption', action='store_true', help='Run automated test for encryption timing analysis')
args = parser.parse_args()

# Create logs directory if it doesn't exist
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Setup logging for application
logging.basicConfig(level=logging.INFO)

# Setup timing logger to capture message transit times
current_date = datetime.now().strftime("%Y-%m-%d")
tls_suffix = "with_tls" if not args.no_tls else "no_tls"
timing_log_filename = f"{LOG_DIR}/mqtt_timing_{current_date}_{tls_suffix}.log"

# Configure timing logger
timing_logger = logging.getLogger("mqtt_timing")
timing_logger.setLevel(logging.INFO)
timing_logger.propagate = False  # Prevent propagation to root logger

# Clear any existing handlers to avoid duplicates
timing_logger.handlers.clear()

# Add file handler for timing log
timing_file_handler = logging.FileHandler(timing_log_filename)
timing_formatter = logging.Formatter('%(asctime)s - %(message)s')
timing_file_handler.setFormatter(timing_formatter)
timing_logger.addHandler(timing_file_handler)

# Dictionary to store message send times
message_times = {}

# TLS Configuration - can be disabled via command-line
USE_TLS = not args.no_tls
AUTOMATED_MODE = args.automated or args.test_time_encryption
TEST_TIME_ENCRYPTION = args.test_time_encryption
logging.info(f"TLS encryption: {'Enabled' if USE_TLS else 'Disabled'}")
logging.info(f"Automated mode: {'Enabled' if AUTOMATED_MODE else 'Disabled'}")
if TEST_TIME_ENCRYPTION:
    logging.info("Test time encryption mode: Enabled")
timing_logger.info(f"Ground Station started - TLS: {'Enabled' if USE_TLS else 'Disabled'} - Automated: {'Enabled' if AUTOMATED_MODE else 'Disabled'} - Test: {'Enabled' if TEST_TIME_ENCRYPTION else 'Disabled'}")

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

def automated_sequence(client):
    global vertical_movement, altitude_monitoring, current_altitude, relative_altitude
    logging.info("Starting automated sequence...")
    meter_per_second = 5.0
    
    # Wait 2 minutes (120 seconds)
    logging.info("Waiting 1 minutes before starting sequence...")
    time.sleep(60)
    
    # Press C 1 times (move down)
    logging.info("Executing C command (GUIDED mode)")
    cmd = {'mode': 'GUIDED', 'takeoff_alt': 10}
    vertical_movement = True
    send_command(client, cmd, f"mode_{cmd['mode']}")
    
    # Wait 10 seconds
    logging.info("Waiting 30 seconds...")
    time.sleep(30)

    # Press Q 2 times (move down)
    logging.info("Executing Q command 2 times (move down)")
    for i in range(2):
        cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": -meter_per_second/2}}
        vertical_movement = True
        send_command(client, cmd, "velocity_down")
        logging.info(f"Q command {i+1}/2 - Moving down from altitude - absolute: {current_altitude:.1f}m, relative: {relative_altitude:.1f}m")
        time.sleep(1)  # Small delay between commands
    
    # Wait 10 seconds
    logging.info("Waiting 10 seconds...")
    time.sleep(10)
    
    # Press W 10 times (move forward)
    logging.info("Executing W command 10 times (move forward)")
    for i in range(10):
        cmd = {'velocity': {"vx": meter_per_second, "vy": 0.0, "vz": 0.0}}
        send_command(client, cmd, "velocity_forward")
        logging.info(f"W command {i+1}/10")
        time.sleep(1)
    
    # Wait 10 seconds
    logging.info("Waiting 10 seconds...")
    time.sleep(10)
    
    # Press D 10 times (move right)
    logging.info("Executing D command 10 times (move right)")
    for i in range(10):
        cmd = {'velocity': {"vx": 0.0, "vy": meter_per_second, "vz": 0.0}}
        send_command(client, cmd, "velocity_right")
        logging.info(f"D command {i+1}/10")
        time.sleep(1)
    
    # Wait 10 seconds
    logging.info("Waiting 10 seconds...")
    time.sleep(10)
    
    # Press S (move backward)
    logging.info("Executing S command (move backward)")
    cmd = {'velocity': {"vx": -meter_per_second, "vy": 0.0, "vz": 0.0}}
    send_command(client, cmd, "velocity_backward")
    
    # Wait 10 seconds
    logging.info("Waiting 10 seconds...")
    time.sleep(10)
    
    # Press W 25 times (move forward)
    logging.info("Executing W command 25 times (move forward)")
    for i in range(25):
        cmd = {'velocity': {"vx": meter_per_second, "vy": 0.0, "vz": 0.0}}
        send_command(client, cmd, "velocity_forward")
        logging.info(f"W command {i+1}/25")
        time.sleep(1)
    
    # Press space (stop)
    logging.info("Executing SPACE command (stop)")
    cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": 0.0}}
    vertical_movement = False
    send_command(client, cmd, "velocity_stop")
    
    # Terminate program
    logging.info("Automated sequence completed. Terminating program...")
    altitude_monitoring = False
    client.loop_stop()
    sys.exit(0)
    
def send_command(client, cmd, command_type="unknown"):
    global message_times, timing_logger, TOPIC_COMMAND
    message_id = str(uuid.uuid4())
    cmd['message_id'] = message_id
    
    send_time = time.time()
    message_times[message_id] = send_time
    
    payload = json.dumps(cmd)
    client.publish(TOPIC_COMMAND, payload)
    
    timing_logger.info(f"GS-SEND: Message ID {message_id} type {command_type} sent at {send_time:.6f}")


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
# Automated sequence function


# Keyboard input management thread
def keyboard_loop(client):
    global vertical_movement, altitude_monitoring
    
    # Check if automated mode is enabled
    if AUTOMATED_MODE:
        automated_sequence(client)
        return
    
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

        # Send command using the new function
        message_type = "unknown"
        if 'velocity' in cmd:
            message_type = "velocity"
        elif 'mode' in cmd:
            message_type = f"mode_{cmd['mode']}"
        elif 'position' in cmd:
            message_type = "position"
        elif 'takeoff_alt' in cmd:
            message_type = "takeoff"
        
        send_command(client, cmd, message_type)

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
