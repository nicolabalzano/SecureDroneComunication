import paho.mqtt.client as mqtt
import ssl
from pymavlink import mavutil
import json
import logging
import subprocess
import os
import threading
import time
# Setup logging
logging.basicConfig(level=logging.INFO)

print("Before Mavlink connection")
while True:
    try:
        connection = mavutil.mavlink_connection('tcp:127.0.0.1:5762')
        break
    except ConnectionRefusedError as e:
        continue
print("After Mavlink connection")
#connection.wait_heartbeat()
logging.info("Drone connesso a SITL!")

# Parametri MQTT
BROKER = "localhost"
PORT = 8883
TOPIC_TELEMETRY = "drone/telemetry"
TOPIC_COMMAND = "drone/command"
CERT_CA = "/etc/mosquitto/ca_certificates/ca.crt"
CERT_FILE = "/etc/mosquitto/certs/client.crt"
KEY_FILE = "/etc/mosquitto/certs/client.key"



# Callback per comandi ricevuti
def on_command(client, userdata, msg):
    logging.info(f"Received raw command message: {msg.payload}")
    try:
        data = json.loads(msg.payload.decode())
        logging.info(f"Decoded command payload: {data}")
        # Controllo pilotaggio via RC_OVERRIDE
        if 'rc_override' in data:
            overrides = data['rc_override']
            channels = [overrides.get(i, 0) for i in range(1, 9)]
            connection.mav.rc_channels_override_send(
                connection.target_system,
                connection.target_component,
                *channels
            )
            logging.info(f"Sent RC_OVERRIDE: {channels}")

        # Cambio modalità
        if 'mode' in data:
            mode = data['mode']
            connection.set_mode(mode)
            logging.info(f"Set mode: {mode}")

        # Comando di takeoff
        if 'takeoff_alt' in data:
            alt = data['takeoff_alt']
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0,0,0,0,0,0,alt
            )
            logging.info(f"Takeoff to {alt}m")
    except json.JSONDecodeError:
        logging.error("Payload comando non valido JSON")

# Setup MQTT client
def setup_mqtt():
    client = mqtt.Client()
    client.tls_set(
        ca_certs=CERT_CA,
        certfile=CERT_FILE,
        keyfile=KEY_FILE,
        tls_version=ssl.PROTOCOL_TLSv1_2
    )
    client.on_message = on_command
    client.connect(BROKER, PORT, 60)
    client.subscribe(TOPIC_COMMAND)
    client.loop_start()
    logging.info(f"MQTT client connesso e sottoscritto a {TOPIC_COMMAND}")
    return client

mqtt_client = setup_mqtt()

# Loop di pubblicazione telemetria
while True:
    msg = connection.recv_match(blocking=True, timeout=5.0) # Ricevi QUALSIASI messaggio con un timeout
    print(msg)
    if msg:
        logging.info(f"Received message type: {msg.get_type()}")
        if msg.get_type() == 'GLOBAL_POSITION_INT':
            print("---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
            # ... la tua logica attuale ...
        # Altrimenti, puoi decidere cosa fare o semplicemente loggarlo per ora
    else:
        logging.warning("No MAVLink message received in the last 5 seconds.")
        continue
    """
    if not msg:
        continue
    altitude = msg.alt / 1000.0  # in metri
    payload = json.dumps({'altitude': altitude})
    mqtt_client.publish(TOPIC_TELEMETRY, payload)
    logging.info(f"Sent telemetry: {payload}")"""
