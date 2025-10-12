
// Untested ChatGPT code. definitely will not work as is.


// ===== 5-Bar Linkage Control: Binary Serial → DAC1, DAC2, Pen =====
// Expects 3 bytes per update packet:
//   [0] BaseA (0–255)
//   [1] BaseB (0–255)
//   [2] pen_down (0 or 1)
//
// Example Python send:
//   ser.write(bytes([128, 200, 1]))

const int DAC1_PIN = DAC0;  // AOUT0
const int DAC2_PIN = DAC1;  // AOUT1
const int PEN_PIN = 5;

int baseA_val = 0;
int baseB_val = 0;
int pen_val   = 0;

void setup() {
  Serial.begin(115200);
  analogWriteResolution(12);  // 12-bit DAC range (0–4095)
  pinMode(PEN_PIN, OUTPUT);

  analogWrite(DAC1_PIN, 0);
  analogWrite(DAC2_PIN, 0);
  digitalWrite(PEN_PIN, LOW);

  Serial.println("Binary DAC Controller Ready");
}

void loop() {
  // Wait until 3 bytes are available
  if (Serial.available() >= 3) {
    baseA_val = Serial.read();
    baseB_val = Serial.read();
    pen_val   = Serial.read() & 0x01;  // ensure 0 or 1
  }

  // Apply current values to outputs
  analogWrite(DAC1_PIN, map(baseA_val, 0, 255, 0, 4095));
  analogWrite(DAC2_PIN, map(baseB_val, 0, 255, 0, 4095));
  digitalWrite(PEN_PIN, pen_val ? HIGH : LOW);
}
