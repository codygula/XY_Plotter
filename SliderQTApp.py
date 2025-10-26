# Create a Python program that uses two vertical sliders in a GUI using PyQT. 
# There should be a while loop in the program that continuously runs a function 
# with the integer values of the two sliders, which should be between 0-255.


import sys
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QSlider, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, QThread, pyqtSignal

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



#12 bit function
def operate_DAC(baseA_val, baseB_val, pen_down): 
    """
    Send 12-bit DAC values and pen state over serial to the Arduino Due.

    Args:
        baseA_val (int): Value for DAC1 (0–4095)
        baseB_val (int): Value for DAC2 (0–4095)
        pen_down (bool or int): 1 if pen is down, 0 if up
        ser (serial.Serial): Open serial connection to Arduino
    """
    print(baseA_val, baseB_val, pen_down)
    if ser and ser.is_open:
        try:
            # Clamp to valid 12-bit range
            # baseA_val = max(0, min(4095, int(baseA_val)))
            # baseB_val = max(0, min(4095, int(baseB_val)))
            baseA_val = max(0, min(4095, int(baseA_val)))
            baseB_val = max(0, min(4095, int(baseB_val)))
            pen_state = 1 if pen_down else 0

            # === Option 1: ASCII protocol (readable, easy to debug) ===
            # Format: "baseA,baseB,pen\n"
            msg = f"{baseA_val},{baseB_val},{pen_state}\n"
            ser.write(msg.encode('ascii'))

            # === Option 2 (optional): binary protocol (faster, compact) ===
            # If you want binary 12-bit transmission instead:
            # packet = struct.pack('<HHB', baseA_val, baseB_val, pen_state)
            # ser.write(packet)

            # === Debug output ===
            print(f"Sent to Arduino → A:{baseA_val:4d}  B:{baseB_val:4d}  Pen:{pen_state}")
        except Exception as e:
            print(f"Serial send error: {e}")


# Worker thread that continuously runs a function with slider values
class Worker(QThread):
    # Signals to send values from the GUI to the thread
    update_values = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.value1 = 0
        self.value2 = 0
        self.running = True
        self.update_values.connect(self.set_values)

    def set_values(self, v1, v2):
        self.value1 = v1
        self.value2 = v2

    def run(self):
        while self.running:
            # Call your function here
            self.process_values(self.value1, self.value2)
            time.sleep(0.1)  # Adjust the loop rate (10Hz)

    def process_values(self, v1, v2):
        # Example function using the slider values
        # print(f"Slider 1: {v1}, Slider 2: {v2}")
        operate_DAC(v1, v2, 1) 

        # if ser and ser.is_open:
        #     try:
        #         baseA = max(0, min(255, int(v1)))
        #         baseB = max(0, min(255, int(v2)))
        #         pd = 1 
        #         ser.write(bytes([baseA, baseB, pd]))
        #         print(f"Slider 1: {v1}, Slider 2: {v2}")
        #     except Exception as e:
        #         print(f"Serial send error: {e}")

    def stop(self):
        self.running = False
        self.wait()


class SliderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Two Vertical Sliders (0–255)")
        self.setGeometry(200, 200, 300, 300)

        # Layout
        layout = QHBoxLayout()

        # Slider 1
        self.slider1 = QSlider(Qt.Vertical)
        self.slider1.setRange(0, 4095)
        self.slider1.setValue(4095)

        # Slider 2
        self.slider2 = QSlider(Qt.Vertical)
        self.slider2.setRange(0, 4095)
        self.slider2.setValue(4095)

        # Labels
        self.label1 = QLabel("0")
        self.label2 = QLabel("0")

        vbox1 = QVBoxLayout()
        vbox1.addWidget(self.slider1)
        vbox1.addWidget(self.label1)

        vbox2 = QVBoxLayout()
        vbox2.addWidget(self.slider2)
        vbox2.addWidget(self.label2)

        layout.addLayout(vbox1)
        layout.addLayout(vbox2)
        self.setLayout(layout)

        # Connect sliders to label updates
        self.slider1.valueChanged.connect(self.update_labels)
        self.slider2.valueChanged.connect(self.update_labels)

        # Start worker thread
        self.worker = Worker()
        self.worker.start()

        # Send initial values to thread
        self.update_labels()

    def update_labels(self):
        v1 = self.slider1.value()
        v2 = self.slider2.value()
        self.label1.setText(str(v1))
        self.label2.setText(str(v2))
        self.worker.update_values.emit(v1, v2)

    def closeEvent(self, event):
        # Cleanly stop the thread when closing
        self.worker.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SliderApp()
    window.show()
    sys.exit(app.exec_())
