# Drone Control via MAVLink and MQTT

This project enables remote control of a MAVLink-compatible drone (e.g., ArduPilot) over an MQTT messaging bus. It allows for sending commands to the drone and receiving telemetry data through a secure MQTT connection.


## Overview

The system consists of two main Python scripts:

1.  **`drone_mqtt.py`**: This script runs on the drone itself or a companion computer connected to the drone's flight controller.
    *   It connects to the flight controller via MAVLink (e.g., over TCP or Serial).
    *   It connects to an MQTT broker using TLS for secure communication.
    *   It subscribes to a command topic (`drone/command`) to receive instructions.
    *   It publishes drone telemetry (like position and attitude) to a telemetry topic (`drone/telemetry`).
    *   It processes commands such as mode changes, takeoff, landing, and velocity-based movement.

2.  **`ground_station.py`**: This script runs on a separate computer and acts as a remote control.
    *   It connects to the same MQTT broker using TLS.
    *   It publishes commands to the `drone/command` topic based on keyboard input.
    *   It subscribes to the `drone/telemetry` topic (currently, telemetry processing is minimal in the provided script but can be extended).

## Features

*   **Secure Communication**: Uses MQTT with TLS encryption for command and telemetry data.
*   **MAVLink Integration**: Interfaces with MAVLink-compatible flight controllers.
*   **Keyboard Control**: Simple terminal-based ground station for drone control.
*   **Core Commands Supported**:
    *   Flight mode changes (GUIDED, STABILIZE, LOITER, LAND).
    *   Automated Takeoff.
    *   Velocity-based movement in GUIDED mode (forward, backward, left, right, up, down).
    *   Stop/Hover command.
*   **Telemetry Publishing**: Drone publishes key telemetry like GPS position and attitude.

## Architecture

```
+---------------------+      MAVLink       +-------------------+      MQTT (TLS)      +-----------------------+
| Flight Controller   |<------------------>|  drone_mqtt.py    |<-------------------->| MQTT Broker (Mosquitto) |
| (ArduPilot/PX4)     |                    | (On Drone/Companion)|                    |                       |
+---------------------+                    +-------------------+                     +-----------------------+
                                                                                           ^
                                                                                           | MQTT (TLS)
                                                                                           v
                                                                                    +-----------------------+
                                                                                    | ground_station.py     |
                                                                                    | (Remote Computer)     |
                                                                                    +-----------------------+
```

## Prerequisites

*   Python 3.x
*   **Python Libraries**:
    *   `paho-mqtt`: For MQTT communication.
    *   `pymavlink`: For MAVLink communication.
*   A MAVLink-compatible drone or a simulator (e.g., ArduPilot SITL, PX4 SITL).
*   An MQTT broker, such as Mosquitto, configured to use TLS.
*   (For `ground_station.py` keyboard input): A Unix-like system (Linux, macOS) due to the use of `termios` and `tty` modules.
*    tmux for linux terminal
  
## Setup

### 1. MQTT Broker (Mosquitto with TLS)

*   Install Mosquitto on a server or your local machine.
*   Configure Mosquitto for TLS communication. This involves:
    *   Generating a Certificate Authority (CA) certificate.
    *   Generating server certificates (signed by your CA).
    *   Generating client certificates for `drone_mqtt.py` and `ground_station.py` (signed by your CA).
*   Update your `mosquitto.conf` file. Example TLS configuration:
    ```conf
    # mosquitto.conf
    listener 8883
    cafile /path/to/your/ca.crt
    certfile /path/to/your/server.crt
    keyfile /path/to/your/server.key
    require_certificate true
    tls_version tlsv1.2
    ```
*   Ensure the certificate paths defined in `drone_mqtt.py` and `ground_station.py` (constants `CERT_CA`, `CERT_FILE`, `KEY_FILE`) point to the correct client certificate files. The current default paths are `/etc/mosquitto/...`.

### 2. Python Dependencies

Install the required Python libraries:
```bash
pip install paho-mqtt pymavlink
```

### 3. MAVLink Connection

*   Ensure your drone or simulator is running and MAVLink telemetry is being output.
*   The `drone_mqtt.py` script defaults to connecting to MAVLink via `tcp:127.0.0.1:5762`. You might need to adjust this in the `connect_to_vehicle` function within `drone_mqtt.py` based on your setup (e.g., for a serial connection like `/dev/ttyUSB0` or a different UDP/TCP port).
*   **For SITL (Software In The Loop simulation):**
    Start your simulator. For example, with ArduPilot:
    ```bash
    # Example for ArduCopter
    sim_vehicle.py -v ArduCopter --map --console
    ```
    This typically makes MAVLink available on UDP port 14550 or TCP port 5760. You might need to use MAVProxy to forward MAVLink to the TCP port expected by `drone_mqtt.py` if it's not directly available.

## Configuration

Before running the scripts, review and update the configuration constants at the beginning of both `drone_mqtt.py` and `ground_station.py`:

*   `BROKER`: IP address or hostname of your MQTT broker.
*   `PORT`: MQTT broker port (default is 8883 for TLS).
*   `TOPIC_TELEMETRY`: MQTT topic for publishing telemetry data.
*   `TOPIC_COMMAND`: MQTT topic for publishing command data.
*   `CERT_CA`, `CERT_FILE`, `KEY_FILE`: Absolute paths to your MQTT client's CA certificate, client certificate, and client key respectively.
*   **In `drone_mqtt.py`**:
    *   The MAVLink connection string in `mavutil.mavlink_connection()` within the `connect_to_vehicle` function.
*   **In `ground_station.py`**:
    *   `meter_per_second`: Default speed for velocity commands.

## Usage

1.  Run the `run_drone.sh` that startup ArduCopter drone simulator and the MQTT broker
    ```bash
    ./run_drone.sh
    ```
4.  **Run `ground_station.py`** on your remote control computer:
    ```bash
    python ground_station.py
    ```
    The terminal will display the available keyboard controls.

### Ground Station Keyboard Controls

*   **Movement (in GUIDED mode, sends velocity commands):**
    *   `W`: Move forward
    *   `S`: Move backward
    *   `A`: Move left
    *   `D`: Move right
    *   `Q`: Move up
    *   `E`: Move down
    *   `SPACE`: Stop (sends zero velocity command)
    *   `P`: Move the dron to inserted coordinates
    *   `R`: Move the drone to random coordinates
*   **Flight Commands:**
    *   `C`: Takeoff (switches to GUIDED mode, arms, and takes off to 10 meters)
    *   `X`: Land (switches to LAND mode)
*   **Mode Changes:**
    *   `M`: Switch to STABILIZE mode
    *   `L`: Switch to LOITER mode
*   **Other:**
    *   `.`: Exit the ground station script.

## Security

The communication channel between the drone script, ground station, and the MQTT broker is secured using TLS encryption. This requires proper configuration of the MQTT broker and valid certificates for both clients.

## Troubleshooting

*   **Connection Errors**:
    *   Verify MQTT broker is running and accessible.
    *   Check firewall rules on all machines.
    *   Double-check certificate paths and ensure certificates are valid and correctly signed.
    *   Ensure MAVLink source (drone/SITL) is active and accessible on the configured address/port.
*   **Drone Not Responding to Commands**:
    *   Check logs of `drone_mqtt.py` for errors in processing commands or MAVLink communication.
    *   Ensure the drone is in an appropriate flight mode to accept the type of command being sent (e.g., velocity commands typically require GUIDED mode).
    *   Verify the drone is armed for commands that require it (like movement or takeoff).
*   **"Address already in use" for MQTT**: Ensure no other process is using the MQTT port (e.g., 8883).
*   **Permission Denied for Certificates**: Ensure the scripts have read permissions for the certificate files.

## Future Improvements

*   Display real-time telemetry data (position, attitude, battery, etc.) in the ground station terminal.
*   Implement a more robust GUI for the ground station.
*   Add support for waypoint missions.
*   Allow dynamic adjustment of parameters like speed from the ground station.
*   More comprehensive error handling and user feedback for command acknowledgments.

## Prerequisites

*   Python 3.x
*   **Python Libraries**:
    *   `paho-mqtt`: For MQTT communication.
    *   `pymavlink`: For MAVLink communication.
*   A MAVLink-compatible drone or a simulator (e.g., ArduPilot SITL, PX4 SITL).
*   An MQTT broker, such as Mosquitto, configured to use TLS.
*   (For `ground_station.py` keyboard input): A Unix-like system (Linux, macOS) due to the use of `termios` and `tty` modules.

## Setup

### 1. MQTT Broker (Mosquitto with TLS)

*   Install Mosquitto on a server or your local machine.
*   Configure Mosquitto for TLS communication. This involves:
    *   Generating a Certificate Authority (CA) certificate.
    *   Generating server certificates (signed by your CA).
    *   Generating client certificates for `drone_mqtt.py` and `ground_station.py` (signed by your CA).
*   Update your `mosquitto.conf` file. Example TLS configuration:
    ```conf
    # mosquitto.conf
    listener 8883
    cafile /path/to/your/ca.crt
    certfile /path/to/your/server.crt
    keyfile /path/to/your/server.key
    require_certificate true
    tls_version tlsv1.2
    ```
*   Ensure the certificate paths defined in `drone_mqtt.py` and `ground_station.py` (constants `CERT_CA`, `CERT_FILE`, `KEY_FILE`) point to the correct client certificate files. The current default paths are `/etc/mosquitto/...`.

### 2. Python Dependencies

Install the required Python libraries:
```bash
pip install paho-mqtt pymavlink
```

### 3. MAVLink Connection

*   Ensure your drone or simulator is running and MAVLink telemetry is being output.
*   The `drone_mqtt.py` script defaults to connecting to MAVLink via `tcp:127.0.0.1:5762`. You might need to adjust this in the `connect_to_vehicle` function within `drone_mqtt.py` based on your setup (e.g., for a serial connection like `/dev/ttyUSB0` or a different UDP/TCP port).
*   **For SITL (Software In The Loop simulation):**
    Start your simulator. For example, with ArduPilot:
    ```bash
    # Example for ArduCopter
    sim_vehicle.py -v ArduCopter --map --console
    ```
    This typically makes MAVLink available on UDP port 14550 or TCP port 5760. You might need to use MAVProxy to forward MAVLink to the TCP port expected by `drone_mqtt.py` if it's not directly available.

## Configuration

Before running the scripts, review and update the configuration constants at the beginning of both `drone_mqtt.py` and `ground_station.py`:

*   `BROKER`: IP address or hostname of your MQTT broker.
*   `PORT`: MQTT broker port (default is 8883 for TLS).
*   `TOPIC_TELEMETRY`: MQTT topic for publishing telemetry data.
*   `TOPIC_COMMAND`: MQTT topic for publishing command data.
*   `CERT_CA`, `CERT_FILE`, `KEY_FILE`: Absolute paths to your MQTT client's CA certificate, client certificate, and client key respectively.
*   **In `drone_mqtt.py`**:
    *   The MAVLink connection string in `mavutil.mavlink_connection()` within the `connect_to_vehicle` function.
*   **In `ground_station.py`**:
    *   `meter_per_second`: Default speed for velocity commands.

## Usage

1.  **Start your MQTT Broker** (if not already running).
2.  **Start your Drone/Simulator** and ensure its MAVLink interface is active.
3.  **Run `drone_mqtt.py`** on the drone or its companion computer:
    ```bash
    python drone_mqtt.py
    ```
    Check the console output for successful MAVLink and MQTT connection messages.

4.  **Run `ground_station.py`** on your remote control computer:
    ```bash
    python ground_station.py
    ```
    The terminal will display the available keyboard controls.

### Ground Station Keyboard Controls

*   **Movement (in GUIDED mode, sends velocity commands):**
    *   `W`: Move forward
    *   `S`: Move backward
    *   `A`: Move left
    *   `D`: Move right
    *   `Q`: Move up
    *   `E`: Move down
    *   `SPACE`: Stop (sends zero velocity command)
*   **Flight Commands:**
    *   `C`: Takeoff (switches to GUIDED mode, arms, and takes off to 10 meters)
    *   `X`: Land (switches to LAND mode)
*   **Mode Changes:**
    *   `M`: Switch to STABILIZE mode
    *   `L`: Switch to LOITER mode
*   **Other:**
    *   `.`: Exit the ground station script.

## Security

The communication channel between the drone script, ground station, and the MQTT broker is secured using TLS encryption. This requires proper configuration of the MQTT broker and valid certificates for both clients.

## Troubleshooting

*   **Connection Errors**:
    *   Verify MQTT broker is running and accessible.
    *   Check firewall rules on all machines.
    *   Double-check certificate paths and ensure certificates are valid and correctly signed.
    *   Ensure MAVLink source (drone/SITL) is active and accessible on the configured address/port.
*   **Drone Not Responding to Commands**:
    *   Check logs of `drone_mqtt.py` for errors in processing commands or MAVLink communication.
    *   Ensure the drone is in an appropriate flight mode to accept the type of command being sent (e.g., velocity commands typically require GUIDED mode).
    *   Verify the drone is armed for commands that require it (like movement or takeoff).
*   **"Address already in use" for MQTT**: Ensure no other process is using the MQTT port (e.g., 8883).
*   **Permission Denied for Certificates**: Ensure the scripts have read permissions for the certificate files.

## Future Improvements

*   Display real-time telemetry data (position, attitude, battery, etc.) in the ground station terminal.
*   Implement a more robust GUI for the ground station.
*   Add support for waypoint missions.
*   Allow dynamic adjustment of parameters like speed from the ground station.
*   More comprehensive error handling and user feedback for command acknowledgments.

## License

Specify your license here (e.g., MIT, GPL, etc.). If not specified, it's typically under standard copyright.
