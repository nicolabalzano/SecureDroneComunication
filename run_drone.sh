#cd ~/ardupilot/ArduCopter
#python ~/scripts/drone_mqtt.py & ../Tools/autotest/sim_vehicle.py --map --console --out=tcp:127.0.0.1:5762 
#!/bin/bash

run_with_tmux() {
    tmux new-session -d -s drone_sim
    tmux split-window -t drone_sim:0
    tmux send-keys -t drone_sim:0.0 "cd ~/ardupilot/ArduCopter && ../Tools/autotest/sim_vehicle.py --map --console --out=tcp:127.0.0.1:5762" C-m
    tmux send-keys -t drone_sim:0.1 "python /home/nikba/DrivenDroneMQTT/drone_mqtt.py" C-m
    tmux attach-session -t drone_sim
}


run_with_tmux