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
    #logging.info(f"Telemetry received: {message.payload.decode()}")
    pass

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
    logging.info("Drone control: WASD per movimento, Q/E su/giù, C takeoff, X land, SPAZIO per fermare.")
    while True:
        key = getch().lower()
        cmd = {}
        
        # Comandi di velocità per modalità GUIDED
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
        elif key == ' ':  # Spazio per fermarsi
            cmd = {'velocity': {"vx": 0.0, "vy": 0.0, "vz": 0.0}}  # Stop
            
        # Modalità e comandi esistenti
        elif key == 'c':
            cmd = {'mode': 'GUIDED', 'takeoff_alt': 10}
        elif key == 'm':
            cmd = {'mode': 'STABILIZE'}
        elif key == 'l':
            cmd = {'mode': 'LOITER'}
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
    logging.info("Closing Ground Station")
    client.loop_stop()
    sys.exit(0)
