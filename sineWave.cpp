// For testing/calibrating DACs

// Arduino Due: Generate two 0.5 Hz sine waves 180° out of phase
// DAC0 and DAC1 used (pins A12, A13)

#include <Arduino.h>

// Number of samples per waveform cycle
const int NUM_SAMPLES = 200;  

// Frequency of the waveform
const float WAVE_FREQ = 50;  // Hz (period = 2 s)

// DAC resolution and limits
const int DAC_MAX = 4095;  // 12-bit DAC
const float VREF = 3.3;    // Reference voltage

// Lookup tables
uint16_t sineTable[NUM_SAMPLES];

volatile int sampleIndex = 0;

// Timer setup
void TC7_Handler(void) {
  // Clear interrupt
  TC_GetStatus(TC2, 1);

  // Write DAC values
  uint16_t val0 = sineTable[sampleIndex];                       // Sine
  uint16_t val1 = sineTable[(sampleIndex + NUM_SAMPLES/2) % NUM_SAMPLES]; // 180° shifted

  dacc_set_channel_selection(DACC_INTERFACE, 0); // DAC0
  dacc_write_conversion_data(DACC_INTERFACE, val0);

  dacc_set_channel_selection(DACC_INTERFACE, 1); // DAC1
  dacc_write_conversion_data(DACC_INTERFACE, val1);

  // Next sample
  sampleIndex++;
  if (sampleIndex >= NUM_SAMPLES) sampleIndex = 0;
}

void setup() {
  // Initialize DACs
  analogWriteResolution(12);
  pmc_enable_periph_clk(ID_DACC);
  dacc_reset(DACC_INTERFACE);
  dacc_set_transfer_mode(DACC_INTERFACE, 0);
  dacc_set_power_save(DACC_INTERFACE, 0, 0);
  dacc_set_analog_control(DACC_INTERFACE,
    DACC_ACR_IBCTLCH0(0x02) |
    DACC_ACR_IBCTLCH1(0x02) |
    DACC_ACR_IBCTLDACCORE(0x01));
  dacc_enable_channel(DACC_INTERFACE, 0); // DAC0
  dacc_enable_channel(DACC_INTERFACE, 1); // DAC1

  // Build sine table (0–4095 range)
  for (int i = 0; i < NUM_SAMPLES; i++) {
    float theta = (2.0 * PI * i) / NUM_SAMPLES;
    float s = (sin(theta) + 1.0) / 2.0;  // scale 0–1
    sineTable[i] = (uint16_t)(s * DAC_MAX);
  }

  // Configure Timer (TC2 channel 1 = TC7_Handler)
  pmc_enable_periph_clk(ID_TC7);
  Tc *tc = TC2;
  tc->TC_CHANNEL[1].TC_CCR = TC_CCR_CLKDIS;
  tc->TC_CHANNEL[1].TC_IDR = 0xFFFFFFFF;
  tc->TC_CHANNEL[1].TC_SR;
  
  // Calculate sample rate
  float sampleRate = NUM_SAMPLES * WAVE_FREQ; // samples per second
  uint32_t rc = VARIANT_MCK / 128 / sampleRate; // MCK/128 clock
  TC_Configure(tc, 1,
    TC_CMR_TCCLKS_TIMER_CLOCK4 | // MCK/128
    TC_CMR_WAVE | TC_CMR_WAVSEL_UP_RC);
  TC_SetRC(tc, 1, rc);
  tc->TC_CHANNEL[1].TC_IER = TC_IER_CPCS;
  tc->TC_CHANNEL[1].TC_CCR = TC_CCR_CLKEN | TC_CCR_SWTRG;

  NVIC_EnableIRQ(TC7_IRQn);
}

void loop() {
  // Nothing here; waveform generated in ISR
}

