#include "apan_capture.h"

#include <limits.h>

ApanCapture::ApanCapture(uint16_t jerkThreshold, uint16_t levelThreshold,
                         uint16_t confirmationThreshold, uint16_t confirmationSamples)
    : jerkThreshold_(jerkThreshold), levelThreshold_(levelThreshold),
      confirmationThreshold_(confirmationThreshold), confirmationSamples_(confirmationSamples) {}

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
  int32_t baselineSum = 0;
  uint16_t read = historyWrite_;
  for (size_t i = 0; i < APAN_PRETRIGGER_SAMPLES; ++i) {
    event_.samples[i] = history_[read];
    baselineSum += history_[read];
    read = (read + 1U) % APAN_PRETRIGGER_SAMPLES;
  }
  candidateBaseline_ = static_cast<int16_t>(baselineSum / APAN_PRETRIGGER_SAMPLES);
  int32_t initialDeviation = static_cast<int32_t>(triggerSample) - candidateBaseline_;
  if (initialDeviation < 0) initialDeviation = -initialDeviation;
  candidateConfirmed_ = static_cast<uint32_t>(initialDeviation) >= confirmationThreshold_;
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
    int32_t deviation = static_cast<int32_t>(sample) - candidateBaseline_;
    if (deviation < 0) deviation = -deviation;
    if (static_cast<uint32_t>(deviation) >= confirmationThreshold_) candidateConfirmed_ = true;
    if (!candidateConfirmed_ &&
        eventWrite_ >= APAN_PRETRIGGER_SAMPLES + confirmationSamples_) {
      collecting_ = false;
      eventWrite_ = 0;
      event_.peakAbs = 0;
    }
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
  candidateConfirmed_ = false;
  eventWrite_ = 0;
  event_.peakAbs = 0;
}

void ApanCapture::setThresholds(uint16_t jerkThreshold, uint16_t levelThreshold,
                                uint16_t confirmationThreshold) {
  jerkThreshold_ = jerkThreshold;
  levelThreshold_ = levelThreshold;
  confirmationThreshold_ = confirmationThreshold;
}
