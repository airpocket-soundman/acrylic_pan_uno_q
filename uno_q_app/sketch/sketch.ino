#include <Arduino_RouterBridge.h>
#include <SPI.h>

constexpr uint8_t CS_PIN = 10, INT_PIN = 8;
constexpr uint32_t SAMPLE_RATE_HZ = 4000;
constexpr size_t EVENT_SAMPLES = 80, PRETRIGGER_SAMPLES = 10;
// Same physical thresholds and confirmation window as acrylic_pan's KX134
// capture (700/200/3000 counts at 1024 counts/g, 16 samples at 25.6 kHz),
// converted to MPU9250 +/-16 g counts and 4 kHz timing.
constexpr int DEFAULT_JERK_THRESHOLD = 1400;
constexpr int DEFAULT_LEVEL_THRESHOLD = 400;
constexpr int CONFIRMATION_THRESHOLD = 6000;
constexpr size_t CONFIRMATION_SAMPLES = 3;
SPISettings mpuSpi(8000000, MSBFIRST, SPI_MODE3);
volatile uint32_t irqCount = 0;
bool sensorReady = false, capturing = false, hasPreviousSample = false;
bool candidateConfirmed = false, acceptedEventExists = false;
uint32_t consumedIrqCount = 0, missedDataReady = 0;
uint32_t eventSequence = 0, nextStatusAt = 0, lastAcceptedEventMs = 0;
int levelThreshold = DEFAULT_LEVEL_THRESHOLD, jerkThreshold = DEFAULT_JERK_THRESHOLD;
int confirmationThreshold = CONFIRMATION_THRESHOLD, eventPeak = 0;
uint16_t retriggerGuardMs = 80;
int16_t candidateBaseline = 0;
int candidatePeakDeviation = 0;
int16_t previousZ = 0, ringX[10] = {}, ringY[10] = {}, ringZ[10] = {};
int16_t eventX[80] = {}, eventY[80] = {}, eventZ[80] = {};
size_t ringCursor = 0, ringCount = 0, eventCount = 0;

void onDataReady() { ++irqCount; }
uint8_t readRegister(uint8_t address) {
  SPI.beginTransaction(mpuSpi); digitalWrite(CS_PIN, LOW); SPI.transfer(address | 0x80);
  uint8_t value = SPI.transfer(0); digitalWrite(CS_PIN, HIGH); SPI.endTransaction(); return value;
}
void writeRegister(uint8_t address, uint8_t value) {
  SPI.beginTransaction(mpuSpi); digitalWrite(CS_PIN, LOW); SPI.transfer(address & 0x7F); SPI.transfer(value);
  digitalWrite(CS_PIN, HIGH); SPI.endTransaction();
}
void readAxes(int16_t& x, int16_t& y, int16_t& z) {
  SPI.beginTransaction(mpuSpi); digitalWrite(CS_PIN, LOW); SPI.transfer(0x3B | 0x80);
  x = static_cast<int16_t>((SPI.transfer(0) << 8) | SPI.transfer(0));
  y = static_cast<int16_t>((SPI.transfer(0) << 8) | SPI.transfer(0));
  z = static_cast<int16_t>((SPI.transfer(0) << 8) | SPI.transfer(0));
  digitalWrite(CS_PIN, HIGH); SPI.endTransaction(); readRegister(0x3A);
}
bool beginMpu9250() {
  pinMode(CS_PIN, OUTPUT); digitalWrite(CS_PIN, HIGH); pinMode(INT_PIN, INPUT); SPI.begin(); delay(20);
  if (readRegister(0x75) != 0x71) return false;
  writeRegister(0x6B, 0x80); delay(100); writeRegister(0x6B, 0x01); delay(10);
  writeRegister(0x6C, 0x07); writeRegister(0x6A, 0x10); writeRegister(0x19, 0x00);
  writeRegister(0x1C, 0x18); writeRegister(0x1D, 0x08); writeRegister(0x37, 0x00); writeRegister(0x38, 0x01);
  attachInterrupt(digitalPinToInterrupt(INT_PIN), onDataReady, RISING); return readRegister(0x75) == 0x71;
}
void setThresholds(int jerk, int level, int confirmation) {
  jerkThreshold = constrain(jerk, 1, 32767); levelThreshold = constrain(level, 1, 32767);
  confirmationThreshold = constrain(confirmation, 1, 32767);
}
void setRetriggerGuard(int milliseconds) {
  retriggerGuardMs = static_cast<uint16_t>(constrain(milliseconds, 0, 500));
  acceptedEventExists = false;
}
int magnitude16(int16_t value) {
  return value == INT16_MIN ? 32768 : abs(static_cast<int>(value));
}
int differenceMagnitude(int16_t a, int16_t b) {
  return abs(static_cast<int>(a) - static_cast<int>(b));
}
void pushHistory(int16_t x, int16_t y, int16_t z) {
  ringX[ringCursor] = x; ringY[ringCursor] = y; ringZ[ringCursor] = z;
  ringCursor = (ringCursor + 1) % PRETRIGGER_SAMPLES;
  if (ringCount < PRETRIGGER_SAMPLES) ++ringCount;
}
void beginEvent(int16_t x, int16_t y, int16_t z) {
  int32_t baselineSum = 0;
  for (size_t i = 0; i < PRETRIGGER_SAMPLES; ++i) {
    const size_t source = (ringCursor + i) % PRETRIGGER_SAMPLES;
    eventX[i] = ringX[source]; eventY[i] = ringY[source]; eventZ[i] = ringZ[source];
    baselineSum += ringZ[source];
  }
  candidateBaseline = static_cast<int16_t>(baselineSum / static_cast<int32_t>(PRETRIGGER_SAMPLES));
  candidatePeakDeviation = differenceMagnitude(z, candidateBaseline);
  candidateConfirmed = candidatePeakDeviation >= confirmationThreshold;
  eventX[PRETRIGGER_SAMPLES] = x; eventY[PRETRIGGER_SAMPLES] = y; eventZ[PRETRIGGER_SAMPLES] = z;
  eventCount = PRETRIGGER_SAMPLES + 1; eventPeak = magnitude16(z); capturing = true;
}
void rejectCandidate() {
  capturing = false; candidateConfirmed = false; eventCount = 0; eventPeak = 0;
}
bool acceptEventNow() {
  const uint32_t now = millis();
  if (!acceptedEventExists || now - lastAcceptedEventMs >= retriggerGuardMs) {
    acceptedEventExists = true; lastAcceptedEventMs = now; return true;
  }
  return false;
}
void sendEvent() {
  if (!acceptEventNow()) { rejectCandidate(); return; }
  ++eventSequence;
  for (size_t i = 0; i < EVENT_SAMPLES; ++i) {
    Bridge.notify("on_capture_sample", static_cast<int>(eventSequence), static_cast<int>(i),
                  static_cast<int>(eventX[i]), static_cast<int>(eventY[i]), static_cast<int>(eventZ[i]),
                  static_cast<int>(PRETRIGGER_SAMPLES), eventPeak, static_cast<int>(irqCount));
  }
  rejectCandidate();
}
void feedSample(int16_t rawX, int16_t rawY, int16_t rawZ) {
  if (capturing) {
    const int deviation = differenceMagnitude(rawZ, candidateBaseline);
    eventX[eventCount] = rawX; eventY[eventCount] = rawY; eventZ[eventCount] = rawZ;
    eventPeak = max(eventPeak, magnitude16(rawZ));
    candidatePeakDeviation = max(candidatePeakDeviation, deviation);
    if (deviation >= confirmationThreshold) candidateConfirmed = true;
    ++eventCount;
    if (!candidateConfirmed && eventCount >= PRETRIGGER_SAMPLES + CONFIRMATION_SAMPLES) {
      rejectCandidate();
    } else if (eventCount == EVENT_SAMPLES) {
      pushHistory(rawX, rawY, rawZ); previousZ = rawZ; hasPreviousSample = true;
      sendEvent(); return;
    }
  } else if (ringCount == PRETRIGGER_SAMPLES && hasPreviousSample &&
             differenceMagnitude(rawZ, previousZ) >= jerkThreshold &&
             magnitude16(rawZ) >= levelThreshold) {
    beginEvent(rawX, rawY, rawZ);
  }
  pushHistory(rawX, rawY, rawZ); previousZ = rawZ; hasPreviousSample = true;
}
void setup() {
  Bridge.begin(); Bridge.provide("set_thresholds", setThresholds);
  Bridge.provide("set_retrigger_guard", setRetriggerGuard); sensorReady = beginMpu9250();
  Bridge.notify("on_sensor_status", sensorReady, static_cast<int>(readRegister(0x75)));
  Bridge.notify("on_runtime_status", sensorReady ? "sensor" : "error", sensorReady);
  if (sensorReady) {
    noInterrupts(); consumedIrqCount = irqCount; interrupts();
    nextStatusAt = millis() + 2000;
  }
}
void loop() {
  if (!sensorReady) { delay(1000); return; }
  if (static_cast<int32_t>(millis() - nextStatusAt) >= 0) {
    Bridge.notify("on_sensor_status", true, 0x71); Bridge.notify("on_runtime_status", "sensor", true); nextStatusAt = millis() + 5000;
  }
  uint32_t readyCount;
  noInterrupts(); readyCount = irqCount; interrupts();
  if (readyCount != consumedIrqCount) {
    const uint32_t elapsed = readyCount - consumedIrqCount;
    if (elapsed > 1) missedDataReady += elapsed - 1;
    consumedIrqCount = readyCount;
    int16_t x, y, z; readAxes(x, y, z); feedSample(x, y, z);
  }
}
