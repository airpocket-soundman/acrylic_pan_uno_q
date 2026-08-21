#include "apan_capture.h"

#include <limits.h>

ApanCapture::ApanCapture(uint16_t jerkThreshold, uint16_t levelThreshold)
    : jerkThreshold_(jerkThreshold), levelThreshold_(levelThreshold) {}

uint16_t ApanCapture::magnitude(int16_t value) {
  if (value == INT16_MIN) return 32768U;
  return static_cast<uint16_t>(value < 0 ? -value : value);
}

void ApanCapture::pushHistory(int16_t sample) {
  history_[historyWrite_] = sample;
  historyWrite_ = (historyWrite_ + 1U) % APAN_PRETRIGGER_SAMPLES;
  if (historyCount_ < APAN_PRETRIGGER_SAMPLES) ++historyCount_;
}

void ApanCapture::beginEvent(int16_t triggerSample) {
  uint16_t read = historyWrite_;
  for (size_t i = 0; i < APAN_PRETRIGGER_SAMPLES; ++i) {
    event_.samples[i] = history_[read];
    read = (read + 1U) % APAN_PRETRIGGER_SAMPLES;
  }
  event_.triggerIndex = APAN_PRETRIGGER_SAMPLES;
  event_.samples[APAN_PRETRIGGER_SAMPLES] = triggerSample;
  event_.peakAbs = magnitude(triggerSample);
  eventWrite_ = APAN_PRETRIGGER_SAMPLES + 1U;
  collecting_ = true;
}

void ApanCapture::feed(int16_t sample) {
  if (ready_) return;

  if (collecting_) {
    event_.samples[eventWrite_++] = sample;
    event_.peakAbs = max(event_.peakAbs, magnitude(sample));
    if (eventWrite_ == APAN_EVENT_SAMPLES) {
      collecting_ = false;
      ready_ = true;
    }
  } else if (historyCount_ == APAN_PRETRIGGER_SAMPLES && hasPreviousSample_) {
    int32_t difference = static_cast<int32_t>(sample) - previousSample_;
    if (difference < 0) difference = -difference;
    if (difference >= jerkThreshold_ && magnitude(sample) >= levelThreshold_) {
      beginEvent(sample);
    }
  }

  pushHistory(sample);
  previousSample_ = sample;
  hasPreviousSample_ = true;
}

bool ApanCapture::ready() const { return ready_; }

const ApanEvent& ApanCapture::event() const { return event_; }

void ApanCapture::release() {
  ready_ = false;
  eventWrite_ = 0;
  event_.peakAbs = 0;
}

void ApanCapture::setThresholds(uint16_t jerkThreshold, uint16_t levelThreshold) {
  jerkThreshold_ = jerkThreshold;
  levelThreshold_ = levelThreshold;
}
