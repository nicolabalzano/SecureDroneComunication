import paho.mqtt.client as mqtt
import ssl
from pymavlink import mavutil
import json
import logging
import time
import threading
import argparse
import os
import datetime
import uuid
from timing_logger import TimingLogger

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Drone MQTT bridge')
parser.add_argument('--no-tls', action='store_true', help='Disable TLS encryption')
args = parser.parse_args()

# Create logs directory if it doesn't exist
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Setup logging for application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Setup timing logger to capture message transit times
current_date = datetime.datetime.now().strftime("%Y-%m-%d")
timing_log_filename = f"{LOG_DIR}/mqtt_timing_{current_date}.log"

# Configure timing logger
timing_logger = logging.getLogger("mqtt_timing")
timing_logger.setLevel(logging.INFO)

# Add file handler for timing log (only add if handler doesn't exist)
if not any(isinstance(handler, logging.FileHandler) and 
           handler.baseFilename == os.path.abspath(timing_log_filename) 
           for handler in timing_logger.handlers):
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
logger.info(f"TLS encryption: {'Enabled' if USE_TLS else 'Disabled'}")
timing_logger.info(f"Drone MQTT started - TLS: {'Enabled' if USE_TLS else 'Disabled'}")

# MQTT Configuration
BROKER = "localhost"
PORT_TLS = 8883
PORT_NO_TLS = 1883  # Standard MQTT port without TLS
PORT = PORT_TLS if USE_TLS else PORT_NO_TLS
TOPIC_TELEMETRY = "drone/telemetry"
TOPIC_COMMAND = "drone/command"
CERT_CA = "/etc/mosquitto/ca_certificates/ca.crt"
CERT_FILE = "/etc/mosquitto/certs/client.crt"
KEY_FILE = "/etc/mosquitto/certs/client.key"

# MAVLink connection
connection = None

def connect_to_vehicle():
    """Establish connection to the drone"""
    global connection
    logger.info("Attempting to connect to MAVLink vehicle...")
    
    # Try to connect with retries
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            connection = mavutil.mavlink_connection('tcp:127.0.0.1:5762')
            logger.info("MAVLink connection established")
            
            # Wait for heartbeat to ensure connection is valid
            logger.info("Waiting for heartbeat...")
            connection.wait_heartbeat()
            logger.info(f"Connected to system: {connection.target_system} component: {connection.target_component}")
            return True
        except Exception as e:
            retry_count += 1
            logger.warning(f"Connection attempt {retry_count} failed: {e}")
            time.sleep(1)
    
    logger.error("Failed to connect to MAVLink vehicle after multiple attempts")
    return False

def request_data_streams():
    """Request all needed data streams from the drone"""
    if not connection:
        logger.error("Cannot request data streams - no connection")
        return
        
    # Request position data using the SET_MESSAGE_INTERVAL command
    connection.mav.command_long_send(
        connection.target_system,
        connection.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
        0,
        mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT,
        200000,  # 5 Hz (interval in microseconds)
        0, 0, 0, 0, 0
    )
    logger.info("Requested GLOBAL_POSITION_INT at 5Hz")
    
    # Request attitude data
    connection.mav.command_long_send(
        connection.target_system,
        connection.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
        0,
        mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE,
        200000,  # 5 Hz
        0, 0, 0, 0, 0
    )
    logger.info("Requested ATTITUDE at 5Hz")
    
    # Alternative method using REQUEST_DATA_STREAM
    connection.mav.request_data_stream_send(
        connection.target_system,
        connection.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL,
        4,  # 4 Hz
        1   # Start
    )
    logger.info("Requested all data streams at 4Hz")

def on_connect(client, userdata, flags, rc):
    """Callback when MQTT client connects"""
    if rc == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(TOPIC_COMMAND)
        logger.info(f"Subscribed to {TOPIC_COMMAND}")
    else:
        logger.error(f"Failed to connect to MQTT broker, return code {rc}")

def on_command(client, userdata, msg):
    """Handle commands received from ground station via MQTT"""
    try:
        # Record receive time immediately
        receive_time = time.time()
        
        logger.info(f"Received command: {msg.payload}")
        command = json.loads(msg.payload.decode())
        
        # Extract message ID for timing if present
        message_id = command.get('message_id')
        
        # Try to determine message type
        message_type = "unknown"
        if 'mode' in command:
            message_type = f"mode_{command['mode']}"
        elif 'velocity' in command:
            message_type = "velocity"
        elif 'position' in command:
            message_type = "position"
        elif 'rc_override' in command:
            message_type = "rc_override"
        elif 'takeoff_alt' in command:
            message_type = "takeoff"
        elif 'arm' in command:
            message_type = "arm"
        
        # Log receive time if message has ID
        if message_id:
            timing_logger.info(f"DRONE-RECV: Message ID {message_id} type {message_type} received at {receive_time:.6f}")
            
            # Process start time
            process_start = time.time()
        
        if not connection:
            logger.error("Cannot process command - no MAVLink connection")
            return
        
        # RC override command
        if 'rc_override' in command:
            overrides = command['rc_override']
            channels = [overrides.get(str(i), 0) for i in range(1, 9)]
            connection.mav.rc_channels_override_send(
                connection.target_system,
                connection.target_component,
                *channels
            )
            logger.info(f"Sent RC_OVERRIDE: {channels}")
        
        # Mode change command
        if 'mode' in command:
            mode = command['mode']
            mode_mapping = {
                'STABILIZE': 0,
                'GUIDED': 4,
                'LOITER': 5, 
                'RTL': 6,
                'AUTO': 3,
                'LAND': 9
            }
            
            if isinstance(mode, str) and mode in mode_mapping:
                # Set mode by name
                connection.mav.set_mode_send(
                    connection.target_system,
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                    mode_mapping.get(mode, 0)
                )
                logger.info(f"Setting flight mode to {mode}")
            else:
                # Try direct mode number
                try:
                    mode_id = int(mode)
                    connection.mav.set_mode_send(
                        connection.target_system,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        mode_id
                    )
                    logger.info(f"Setting flight mode to ID {mode_id}")
                except ValueError:
                    logger.error(f"Unknown flight mode: {mode}")
        
        # Arm/disarm command
        if 'arm' in command:
            arm = int(bool(command['arm']))
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                arm, 0, 0, 0, 0, 0, 0
            )
            logger.info(f"{'Arming' if arm else 'Disarming'} vehicle")
        
        # Takeoff command
        if 'takeoff_alt' in command:
            alt = float(command['takeoff_alt'])
            # First make sure we're in GUIDED mode
            connection.mav.set_mode_send(
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                4  # GUIDED mode
            )
            time.sleep(1)  # Give time for mode change
            
            # Then arm if needed
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1, 0, 0, 0, 0, 0, 0  # 1 = arm
            )
            time.sleep(1)  # Give time for arming
            
            # Then takeoff
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0, 0, 0, 0, 0, 0, alt
            )
            logger.info(f"Takeoff command sent - target altitude: {alt}m")
        
        # Position command (new format with position object)
        if 'position' in command:
            pos = command['position']
            if all(k in pos for k in ['lat', 'lon', 'alt']):
                lat = float(pos['lat'])
                lon = float(pos['lon']) 
                alt = float(pos['alt'])
                
                # First switch to GUIDED mode
                connection.mav.set_mode_send(
                    connection.target_system,
                    connection.target_component,
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                    4  # GUIDED mode
                )
                time.sleep(0.5)
                
                # Send waypoint using mission_item command
                connection.mav.mission_item_send(
                    connection.target_system,
                    connection.target_component,
                    0,   # seq
                    0,   # frame
                    mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    2,   # current (2 means guided mode)
                    0,   # autocontinue
                    0,   # param1: hold time
                    0,   # param2: accept radius
                    0,   # param3: pass radius
                    0,   # param4: yaw
                    lat, # param5: lat
                    lon, # param6: lon
                    alt  # param7: alt
                )
                
                # Alternative method using MISSION_ITEM_INT for better precision
                connection.mav.mission_item_int_send(
                    connection.target_system,
                    connection.target_component,
                    0,   # seq
                    0,   # frame
                    mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    2,   # current
                    0,   # autocontinue
                    0,   # param1: hold time
                    0,   # param2: accept radius
                    0,   # param3: pass radius
                    0,   # param4: yaw
                    int(lat * 1e7),  # param5: lat (scaled to int)
                    int(lon * 1e7),  # param6: lon (scaled to int)
                    alt   # param7: alt
                )
                
                logger.info(f"Sent position command: lat={lat}, lon={lon}, alt={alt}")
            else:
                logger.error("Incomplete position data in command")
        
        # Go to location command (old format, lat, lon, alt at top level)
        elif all(k in command for k in ['lat', 'lon', 'alt']):
            lat = float(command['lat'])
            lon = float(command['lon']) 
            alt = float(command['alt'])
            
            connection.mav.set_mode_send(
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                4  # GUIDED mode
            )
            time.sleep(0.5)
            
            # Send waypoint
            connection.mav.mission_item_send(
                connection.target_system,
                connection.target_component,
                0,   # seq
                0,   # frame
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                2,   # current (2 means guided mode)
                0,   # autocontinue
                0,   # param1: hold time
                0,   # param2: accept radius
                0,   # param3: pass radius
                0,   # param4: yaw
                lat, # param5: lat
                lon, # param6: lon
                alt  # param7: alt
            )
            logger.info(f"Sent waypoint command: lat={lat}, lon={lon}, alt={alt}")
        
        # Velocity command
        if 'velocity' in command:
            vel = command['velocity']
            vx = float(vel.get('vx', 0.0))
            vy = float(vel.get('vy', 0.0))
            vz = float(vel.get('vz', 0.0))
            
            # Set velocity using SET_POSITION_TARGET_LOCAL_NED
            connection.mav.set_position_target_local_ned_send(
                0,       # timestamp (ignorato)
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,  # coordinate frame relativo al drone
                0b0000111111000111,  # type mask (solo velocità abilitate)
                0, 0, 0,             # posizione x, y, z (ignorata)
                vx, vy, vz,          # velocità x, y, z in m/s
                0, 0, 0,             # accelerazione (ignorata)
                0, 0                 # yaw, yaw_rate (ignorati)
            )
            logger.info(f"Sent velocity command: vx={vx}, vy={vy}, vz={vz}")
            
        # Log execution completion and timing if message has ID
        if message_id:
            execute_time = time.time()
            processing_time_ms = (execute_time - process_start) * 1000
            transit_time_ms = (receive_time - message_times.get(message_id, receive_time)) * 1000 if message_id in message_times else 0
            total_time_ms = (execute_time - message_times.get(message_id, receive_time)) * 1000 if message_id in message_times else processing_time_ms
            
            timing_logger.info(f"DRONE-EXEC: Message ID {message_id} type {message_type} executed - "
                            f"Transit: {transit_time_ms:.2f}ms, Processing: {processing_time_ms:.2f}ms, "
                            f"Total: {total_time_ms:.2f}ms, TLS: {USE_TLS}")
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in command payload")
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}")

def setup_mqtt():
    """Set up MQTT client with optional TLS security"""
    try:
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_command
        
        if USE_TLS:
            logger.info("Configuring MQTT with TLS security")
            client.tls_set(
                ca_certs=CERT_CA,
                certfile=CERT_FILE,
                keyfile=KEY_FILE,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
        else:
            logger.info("Configuring MQTT without TLS security")
        
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        return client
    except Exception as e:
        logger.error(f"MQTT setup failed: {e}")
        return None

def telemetry_loop():
    """Main loop for receiving MAVLink messages and publishing telemetry"""
    global connection
    
    last_pos_time = 0
    last_attitude_time = 0
    
    while True:
        try:
            if not connection:
                logger.warning("No MAVLink connection, attempting to reconnect...")
                if connect_to_vehicle():
                    request_data_streams()
                else:
                    time.sleep(5)
                    continue
            
            # Receive MAVLink message with timeout
            msg = connection.recv_match(blocking=True, timeout=1.0)
            if not msg:
                continue
                
            # Skip heartbeats and other common messages to reduce log noise
            if msg.get_type() == 'HEARTBEAT':
                continue
                
            # Debug info for position messages
            if ('POSITION' in msg.get_type()) or ('GLOBAL' in msg.get_type()):
                logger.debug(f"Received position message: {msg.get_type()}")
                
            # Process GLOBAL_POSITION_INT messages
            if msg.get_type() == 'GLOBAL_POSITION_INT':
                # Rate limit to avoid flooding MQTT
                current_time = time.time()
                if current_time - last_pos_time < 0.5:  # max 2Hz publishing
                    continue
                last_pos_time = current_time
                
                # Extract position data
                lat = msg.lat / 1e7  # Convert to degrees
                lon = msg.lon / 1e7
                alt = msg.alt / 1000.0  # Convert to meters
                relative_alt = msg.relative_alt / 1000.0
                
                # Add message ID for timing tracking
                message_id = str(uuid.uuid4())
                send_time = time.time()
                message_times[message_id] = send_time
                
                payload = json.dumps({
                    'type': 'position',
                    'timestamp': int(time.time() * 1000),
                    'message_id': message_id,
                    'lat': lat,
                    'lon': lon,
                    'alt': alt,
                    'relative_alt': relative_alt,
                    'heading': msg.hdg / 100.0,  # Convert to degrees
                    'vx': msg.vx / 100.0,  # Convert to m/s
                    'vy': msg.vy / 100.0,
                    'vz': msg.vz / 100.0
                })
                
                # Log send timing info
                timing_logger.info(f"DRONE-SEND: Message ID {message_id} type position sent at {send_time:.6f}")
                
                mqtt_client.publish(TOPIC_TELEMETRY, payload)
                logger.debug(f"Published position: lat={lat:.6f}, lon={lon:.6f}, alt={alt:.1f}m")
                
            # Process ATTITUDE messages
            elif msg.get_type() == 'ATTITUDE':
                # Rate limit
                current_time = time.time()
                if current_time - last_attitude_time < 0.5:
                    continue
                last_attitude_time = current_time
                
                # Convert radians to degrees
                roll = msg.roll * 57.2958
                pitch = msg.pitch * 57.2958
                yaw = msg.yaw * 57.2958
                
                # Add message ID for timing tracking
                message_id = str(uuid.uuid4())
                send_time = time.time()
                message_times[message_id] = send_time
                
                payload = json.dumps({
                    'type': 'attitude',
                    'timestamp': int(time.time() * 1000),
                    'message_id': message_id,
                    'roll': roll,
                    'pitch': pitch,
                    'yaw': yaw,
                    'rollspeed': msg.rollspeed,
                    'pitchspeed': msg.pitchspeed,
                    'yawspeed': msg.yawspeed
                })
                
                # Log send timing info
                timing_logger.info(f"DRONE-SEND: Message ID {message_id} type attitude sent at {send_time:.6f}")
                
                mqtt_client.publish(TOPIC_TELEMETRY, payload)
                logger.debug(f"Published attitude: roll={roll:.1f}, pitch={pitch:.1f}, yaw={yaw:.1f}")
                
        except KeyboardInterrupt:
            logger.info("Telemetry loop stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in telemetry loop: {str(e)}")
            time.sleep(1)

if __name__ == "__main__":
    logger.info("Starting MAVLink to MQTT bridge")
    
    # Connect to drone
    if connect_to_vehicle():
        # Set up MQTT
        mqtt_client = setup_mqtt()
        if mqtt_client:
            # Request data streams from vehicle
            request_data_streams()
            
            # Start telemetry loop
            try:
                telemetry_loop()
            except KeyboardInterrupt:
                logger.info("Program terminated by user")
            finally:
                # Clean shutdown
                if mqtt_client:
                    mqtt_client.loop_stop()
                    mqtt_client.disconnect()
                logger.info("MQTT client disconnected")
        else:
            logger.error("Failed to set up MQTT client. Exiting.")
    else:
        logger.error("Failed to connect to drone. Exiting.")
