
import time
# from svgpathtools import svg2paths
# from collections import deque
# import numpy as np
import keyboard


# SERIAL CODE
# SERIAL CODE
# SERIAL CODE
# For controlling Arduino Due 12 bit DACs.
import serial

# SERIAL_PORT = 'Linux/thing/here'  
SERIAL_PORT = '/dev/ttyACM1'
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
            baseA = max(0, min(255, int(Aval)))
            baseB = max(0, min(255, int(Bval)))
            pd = 1 if penlift else 0
            ser.write(bytes([baseA, baseB, pd]))
        except Exception as e:
            print(f"Serial send error: {e}")




# DAC control function

# while True:
#     operate_DAC(255, 0, 0)
#     time.sleep(0.5)
#     operate_DAC(0, 255, 1)
#     time.sleep(0.5)
#     print("end loop")



# Slow back and forth 
i=0
CycleNumber = 0
sleepTime = 0.01
while True:
    CycleNumber += 1
    print("CycleNumber = ", CycleNumber)
    if i <= 255:
        while i < 255:
            operate_DAC(i, i, 0)
            i = i + 1
            time.sleep(sleepTime)
    if i >= 255:
        while i > 0:
            operate_DAC(i, i, 0)
            i = i - 1    
            time.sleep(sleepTime)


# i=0
# CycleNumber = 0
# sleepTime = 0.01
# a = 0
# b = 0
# while True:
#     # CycleNumber += 1
#     # print("CycleNumber = ", CycleNumber)
#     if keyboard.read_key() == "a":
#         a -= 1
#         operate_DAC(a, b, 0)
#     if keyboard.read_key() == "s":
#         a += 1
#         operate_DAC(a, b, 0)
#     if keyboard.read_key() == "d":
#         b -= 1
#         operate_DAC(a, b, 0)
#     if keyboard.read_key() == "f":
#         b += 1
#         operate_DAC(a, b, 0)

