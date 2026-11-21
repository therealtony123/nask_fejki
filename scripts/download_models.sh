#!/usr/bin/env bash
# Pobiera modele twarzy (YuNet + SFace) z OpenCV Zoo do kfk/models/.
# Potrzebne raz; bez nich pipeline działa dalej (cecha 'wizerunki' nieaktywna).
set -e
cd "$(dirname "$0")/.."
mkdir -p kfk/models
curl -sL -o kfk/models/face_detection_yunet_2023mar.onnx \
  "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
curl -sL -o kfk/models/face_recognition_sface_2021dec.onnx \
  "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
ls -la kfk/models/
echo "OK — modele pobrane."
