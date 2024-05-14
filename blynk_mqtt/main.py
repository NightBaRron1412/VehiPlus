import random
import obd
import csv
import os
import threading
from playsound import playsound


LOGO = r"""
      ___  __          __
     / _ )/ /_ _____  / /__
    / _  / / // / _ \/  '_/
   /____/_/\_, /_//_/_/\_\
          /___/
"""

class Device:
    try:
        # Initial attempt to connect to the OBD-II adapter
        connection = obd.OBD()
        
        while(not connection.is_connected()):
            # Configure and connect to OBD-II adapter
            connection = obd.OBD()
    except Exception as e:
        print(f"An error occurred: {e}")
        
    try:
        original_distance_travelled = connection.query(obd.commands.DISTANCE_SINCE_DTC_CLEAR)
        while (original_distance_travelled is None):
            original_distance_travelled = connection.query(obd.commands.DISTANCE_SINCE_DTC_CLEAR)
        original_distance_travelled = original_distance_travelled.value.magnitude
    except Exception as e:
        print(f"An error occurred: {e}")
    
   
    def __init__(self, mqtt):
        self.mqtt = mqtt
        self.total_distance = self._read_total_distance()  # Read from CSV file
        print("Total distance retrieved: ", self.total_distance)
        self.rpm = 0  # Engine RPM
        self.distance_travelled = 0 # Trip Distance
        self.last_recorded_distance = 0  # Last recorded distance for incremental updates
        self.speed_kmph = 0 # Car Speed Kilometer per hour
        self.speed_limit = 0
        self.speed_alert_active = False  # This flag will control the sound alert threading
        self.fuel_level = 0 # Fuel Level
        self.fuel_limit = 0
        self.fuel_event_logged = False  # Initialize flag variable
        self.control_module_voltage = 0 # Car Control Moduel Voltage
        self.engine_run_time = 0 # Car Engine Run Time
        self.ambient_air_temp = 0 # Ambient Air Temp
        self.coolant_temp = 0 # Engine Coolant Temp
        self.fuel_type = 0 # Fuel Type

    def connected(self):
        #Get latest settings from Blynk.Cloud
        self.mqtt.publish("get/ds", "Speed Limit,Fuel Alert Limit")

        # Display Blynk logo, just for fun
        self.terminal_print(LOGO)
        self.terminal_print("Type \"help\" for the list of available commands")

    def terminal_print(self, *args):
        self.mqtt.publish("ds/Terminal", " ".join(map(str, args)) + "\n")

    def process_message(self, topic, payload):
        if topic == "downlink/ds/Speed Limit":
            self.speed_limit = int(payload)
        elif topic == "downlink/ds/Fuel Alert Limit":
            self.fuel_limit = int(payload)
        elif topic == "downlink/ds/Terminal":
            cmd = list(filter(len, payload.split()))
            if cmd[0] == "set":
                self.target_temp = int(cmd[1])
                self.mqtt.publish("ds/Set Temperature", self.target_temp)
                self.terminal_print(f"Temperature set to {self.target_temp}")
            elif cmd[0] == "on":
                self.power_on = True
                self.mqtt.publish("ds/Power", 1)
                self.terminal_print("Turned ON")
            elif cmd[0] == "off":
                self.power_on = False
                self.mqtt.publish("ds/Power", 0)
                self.terminal_print("Turned OFF")
            elif cmd[0] in ("help", "?"):
                self.terminal_print("Available commands:")
                self.terminal_print("  set N    - set target temperature")
                self.terminal_print("  on       - turn on")
                self.terminal_print("  off      - turn off")
            else:
                self.terminal_print(f"Unknown command: {cmd[0]}")

    def _update_temperature(self):
        target = self.target_temp if self.power_on else 10
        next_temp = self.current_temp + (target - self.current_temp) * 0.05
        next_temp = max(10, min(next_temp, 35))
        next_temp += (0.5 - random.uniform(0, 1)) * 0.3
        self.current_temp = next_temp
        self.mqtt.publish("ds/Current Temperature", self.current_temp)

    def _update_widget_state(self):
        if not self.power_on:
            state = 1 # OFF
        elif abs(self.current_temp - self.target_temp) < 1.0:
            state = 2 # Idle
        elif self.target_temp > self.current_temp:
            state = 3 # Heating
        elif self.target_temp < self.current_temp:
            state = 4 # Cooling

        state_colors = [None, "E4F6F7", "E6F7E4", "F7EAE4", "E4EDF7"]
        self.mqtt.publish("ds/Status", state)
        self.mqtt.publish("ds/Status/prop/color", state_colors[state])
    def _read_total_distance(self):
        # Check if the file exists and read the total distance
        if os.path.exists('VehiPlus/distance.csv'):
            with open('VehiPlus/distance.csv', newline='') as file:
                reader = csv.reader(file)
                for row in reader:
                    if row:
                        return float(row[0])
        return 0  # Return 0 if the file does not exist

    def _write_total_distance(self, distance):
        # Write the total distance to the CSV file
        with open('distance.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([distance])
            
    def _send_data(self):
        try:
            self.rpm = self.connection.query(obd.commands.RPM)  # Engine RPM
            self.distance_travelled = self.connection.query(obd.commands.DISTANCE_SINCE_DTC_CLEAR)  # Distance Since DTC Cleared
            self.speed_kmph = self.connection.query(obd.commands.SPEED) # Car Speed Kilometer per hour
            self.fuel_level = self.connection.query(obd.commands.FUEL_LEVEL) # Fuel Level
            self.control_module_voltage = self.connection.query(obd.commands.CONTROL_MODULE_VOLTAGE) # Car Control Moduel Voltage
            self.engine_run_time = self.connection.query(obd.commands.RUN_TIME) # Car Engine Run Time
            self.ambient_air_temp = self.connection.query(obd.commands.AMBIANT_AIR_TEMP) # Ambient Air Temp
            self.coolant_temp = self.connection.query(obd.commands.COOLANT_TEMP	) # Engine Coolant Temp
            self.fuel_type = self.connection.query(obd.commands.FUEL_TYPE) # Car Fuel Type
            
            
            if self.rpm.value is not None:
                self.mqtt.publish("ds/Engine Speed", self.rpm.value.magnitude)
                
            if self.speed_kmph.value is not None:
                self.mqtt.publish("ds/Speed", self.speed_kmph.value.magnitude)
            
            if self.fuel_level.value is not None:
                self.mqtt.publish("ds/Fuel Level", self.fuel_level.value.magnitude)
                self.mqtt.publish("ds/Fuel Estimated Distance", ((self.fuel_level.value.magnitude * 558) / 100))
            
            if self.control_module_voltage.value is not None:
                self.mqtt.publish("ds/Battery Voltage", self.control_module_voltage.value.magnitude)
            if self.engine_run_time.value is not None:
                self.mqtt.publish("ds/Engine Run Time", self.engine_run_time.value.magnitude)
            if self.ambient_air_temp.value is not None:
                self.mqtt.publish("ds/Ambient Air Temp", self.ambient_air_temp.value.magnitude)
            if self.coolant_temp.value is not None:
                self.mqtt.publish("ds/Coolant Temp", self.coolant_temp.value.magnitude)
            if self.fuel_type.value is not None:
                self.mqtt.publish("ds/Fuel Type", self.fuel_type.value)

            if self.distance_travelled.value is not None:
                # Calculate the incremental distance since the last recorded value
                self.distance_travelled = self.distance_travelled.value.magnitude - self.original_distance_travelled
                incremental_distance = self.distance_travelled - self.last_recorded_distance
                
                # Update the total and last recorded distances
                self.total_distance += incremental_distance
                self.last_recorded_distance = self.distance_travelled

                # Publish current and total distances
                self.mqtt.publish("ds/Current Distance", self.distance_travelled)
                self.mqtt.publish("ds/Total Distance", self.total_distance)
                
                # Save the new total distance
                self._write_total_distance(self.total_distance)
                

        except Exception as e:
            print(f"An error occurred: {e}")
        
    def _check_speed_limit(self):
        if self.speed_kmph.value is not None:
            if self.speed_kmph.value.magnitude > self.speed_limit and self.speed_limit > 0:
                if not self.speed_alert_active:
                    self.speed_alert_active = True
                    threading.Thread(target=self._play_speed_alert_sound).start()  # Start playing sound in a new thread
                self.mqtt.publish("ds/Speed Alert", 1)  # Send Speed alert to Blynk
                self.mqtt.publish("event/speed_limit_exceeded", ) # Log Event
            else:
                if self.speed_alert_active:
                    self.speed_alert_active = False  # Stop the sound alert
                self.mqtt.publish("ds/Speed Alert", 0)  # Send NO Speed alert to Blynk
            
    def _play_speed_alert_sound(self):
        # This method plays the speed alert sound every 10 seconds
        while self.speed_alert_active:
            playsound('alert_sounds/speed_alert.mp3', block=False)
            threading.Event().wait(10)  # Wait for 10 seconds before replaying
        
    def _check_fuel_level(self):
        if self.fuel_level.value is not None:
            if self.fuel_level.value.magnitude < self.fuel_limit and self.fuel_limit > 0:
                self.mqtt.publish("ds/Fuel Alert", 1)  # Send Fuel alert to Blynk
                if not self.fuel_event_logged:  # Check if event has not been logged yet
                    self.mqtt.publish("event/low_fuel", )  # Log Event
                    self.fuel_event_logged = True  # Set the flag to True
            else:
                if self.fuel_event_logged:  # Check if event has been logged previously
                    self.mqtt.publish("ds/Fuel Alert", 0)  # Send Fuel alert to Blynk
                    self.fuel_event_logged = False  # Reset the flag
            
        

    def update(self):
        #self._update_temperature()
        #self._update_widget_state()
        self._send_data()
        try:
            self._check_speed_limit()
            self._check_fuel_level()
        except Exception as e:
            print(f"An error occurred: {e}")
