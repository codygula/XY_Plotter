
import pygame, math, time
from svgpathtools import svg2paths
from collections import deque
import numpy as np


# SERIAL CODE
# SERIAL CODE
# SERIAL CODE
# For controlling Arduino Due 12 bit DACs.
import serial

# SERIAL_PORT = 'Linux/thing/here'  
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200
ENABLE_SERIAL = True 

# SERIAL SETUP 
ser = None
if ENABLE_SERIAL:
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0)
        time.sleep(2)  # Give the Arduino time to reset
        print(f"Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"Serial error: {e}")
        ser = None

# END SERIAL CODE
# END SERIAL CODE
# END SERIAL CODE




def operate_DAC(Aval, Bval, penlift=False):
    print(Aval, Bval, penlift)
    if ser and ser.is_open:
        try:
            baseA = max(0, min(255, int(baseA_val)))
            baseB = max(0, min(255, int(baseB_val)))
            pd = 1 if pen_down else 0
            ser.write(bytes([baseA, baseB, pd]))
        except Exception as e:
            print(f"Serial send error: {e}")




# DAC control function
operate_DAC(baseA_val, baseB_val, pen_down)