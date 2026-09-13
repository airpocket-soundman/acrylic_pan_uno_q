# Third-party notices

This project combines original application code and artwork with third-party runtimes, libraries, and media. Each dependency remains subject to its own upstream license.

## GeneralUser GS

- Author: S. Christian Collins
- Project page: https://schristiancollins.com/generaluser.php
- Bundled file: `uno_q_app/python/soundfonts/GeneralUserGS.sf3`
- Complete bundled notice: `uno_q_app/python/soundfonts/LICENSE.GeneralUser-GS.txt`
- Packaging source used by this project: https://github.com/spessasus/SpessaSynth

The SoundFont is used to render instrument notes on Arduino UNO Q. Do not remove its bundled notice when redistributing the application.

## FluidSynth and pyFluidSynth

- FluidSynth: https://www.fluidsynth.org/
- pyFluidSynth: https://github.com/nwhitehead/pyfluidsynth

FluidSynth provides SoundFont rendering on the UNO Q Linux side. `pyFluidSynth` supplies the Python binding.

## TensorFlow Lite / LiteRT

- TensorFlow: https://github.com/tensorflow/tensorflow
- LiteRT: https://ai.google.dev/edge/litert

The trained `.tflite` artifacts execute the temporal and embedded-FFT position models. Model training uses TensorFlow CPU on the development PC.

## Arduino UNO Q and App Lab

- Arduino: https://www.arduino.cc/

The application uses the Arduino sketch runtime, Arduino Bridge, App Lab application format, and official video brick. Refer to the installed Arduino components and their upstream distributions for the applicable notices.

## Python dependencies

Runtime and training packages are listed in:

- `uno_q_app/python/requirements.txt`
- `requirements-model-training.txt`
- `requirements.txt`

Their inclusion in an environment does not change their upstream licenses.
