cd ~/ardupilot/ArduCopter
python ~/scripts/drone_mqtt.py & ../Tools/autotest/sim_vehicle.py --map --console --out=tcp:127.0.0.1:5762 
