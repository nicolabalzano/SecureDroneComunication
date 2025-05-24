#cd ~/ardupilot/ArduCopter
#python ~/scripts/drone_mqtt.py & ../Tools/autotest/sim_vehicle.py --map --console --out=tcp:127.0.0.1:5762 
#!/bin/bash

# Default options
TLS_OPTION=""
TEST_OPTION=""

# Check parameters
for arg in "$@"
do
    if [ "$arg" == "--no-tls" ]; then
        TLS_OPTION="--no-tls"
        echo "Running with TLS disabled"
    elif [ "$arg" == "--test-time-encryption" ]; then
        TEST_OPTION="--test-time-encryption"
        echo "Running with automated encryption timing test"
    fi
done

run_with_tmux() {
    tmux new-session -d -s drone_sim
    tmux split-window -t drone_sim:0
    tmux split-window -t drone_sim:0
    tmux send-keys -t drone_sim:0.0 "cd ~/ardupilot/ArduCopter && ../Tools/autotest/sim_vehicle.py --map --console --out=tcp:127.0.0.1:5762" C-m
    tmux send-keys -t drone_sim:0.1 "python /home/nikba/DrivenDroneMQTT/drone_mqtt.py $TLS_OPTION" C-m
    tmux send-keys -t drone_sim:0.2 "python /home/nikba/DrivenDroneMQTT/ground_station.py $TLS_OPTION $TEST_OPTION" C-m
    tmux attach-session -t drone_sim
}

run_with_tmux