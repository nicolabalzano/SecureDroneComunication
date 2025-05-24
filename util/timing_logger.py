import time
import logging
import os
import datetime
import json
from threading import Lock

class TimingLogger:
    _instance = None
    _lock = Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TimingLogger, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, log_dir="logs", component_name="unknown"):
        if self._initialized:
            return
            
        # Create logs directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        self.component_name = component_name
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        self.log_filename = f"{log_dir}/mqtt_timing_{current_date}.log"
        
        # Configure logger
        self.logger = logging.getLogger("mqtt_timing")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # Prevent propagation to root logger
        
        # Clear any existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Add file handler for log
        file_handler = logging.FileHandler(self.log_filename)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        self.message_times = {}
        self._initialized = True
        
        # Log start of this component
        self.logger.info(f"Component {component_name} started logging")
    
    def record_send(self, message_id, message_type):
        """Record when a message is sent"""
        timestamp = time.time()
        self.message_times[message_id] = timestamp
        self.logger.info(f"SEND: [{self.component_name}] Message ID {message_id} type {message_type} sent at {timestamp:.6f}")
        return timestamp
    
    def record_receive(self, message_id, message_type):
        """Record when a message is received"""
        timestamp = time.time()
        self.logger.info(f"RECV: [{self.component_name}] Message ID {message_id} type {message_type} received at {timestamp:.6f}")
        return timestamp
    
    def record_execute(self, message_id, message_type, additional_info=""):
        """Record when a message is executed and calculate elapsed time"""
        timestamp = time.time()
        send_time = self.message_times.get(message_id)
        
        if send_time:
            elapsed = (timestamp - send_time) * 1000  # Convert to milliseconds
            self.logger.info(f"EXEC: [{self.component_name}] Message ID {message_id} type {message_type} executed - "
                           f"Total time: {elapsed:.2f}ms {additional_info}")
            
            # Clean up to avoid memory leaks
            del self.message_times[message_id]
            return elapsed
        else:
            self.logger.info(f"EXEC: [{self.component_name}] Message ID {message_id} type {message_type} executed - "
                           f"No send time found {additional_info}")
            return None
