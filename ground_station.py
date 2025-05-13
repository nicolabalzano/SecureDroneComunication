import paho.mqtt.client as mqtt
import ssl
import json
import threading
import sys
import termios
import tty
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Parametri MQTT
BROKER = "127.0.0.1"
PORT = 8883
TOPIC_TELEMETRY = "drone/telemetry"
TOPIC_COMMAND = "drone/command"
CERT_CA = "/etc/mosquitto/ca_certificates/ca.crt"
CERT_FILE = "/etc/mosquitto/certs/client.crt"
KEY_FILE = "/etc/mosquitto/certs/client.key"

# Callback telemetria
def on_message(client, userdata, message):
    logging.info(f"Telemetry received: {message.payload.decode()}")

# Lettura tasti senza invio
def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# Thread gestione input tastiera
def keyboard_loop(client):
    logging.info("Controllo drone: WASD per pitch/roll, Q/E throttle, C takeoff, X land.")
    while True:
        key = getch().lower()
        cmd = {}
        # Map tasti a comando JSON
        if key == 'w':
            cmd = {'rc_override': {1: 1500, 2: 1600}}
        elif key == 's':
            cmd = {'rc_override': {1: 1500, 2: 1400}}
        elif key == 'a':
            cmd = {'rc_override': {1: 1400, 2: 1500}}
        elif key == 'd':
            cmd = {'rc_override': {1: 1600, 2: 1500}}
        elif key == 'q':
            cmd = {'rc_override': {3: 1600}}
        elif key == 'e':
            cmd = {'rc_override': {3: 1400}}
        elif key == 'c':
            cmd = {'mode': 'GUIDED', 'takeoff_alt': 10}
        elif key == 'x':
            cmd = {'mode': 'LAND'}
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
logging.info(f"Ground Station connessa, sottoscritto a {TOPIC_TELEMETRY}")

# Avvia thread tastiera
keyboard_thread = threading.Thread(target=keyboard_loop, args=(client,))
keyboard_thread.daemon = True
keyboard_thread.start()

# Mantieni in vita
try:
    while True:
        pass
except KeyboardInterrupt:
    logging.info("Chiusura Ground Station")
    client.loop_stop()
    sys.exit(0)
