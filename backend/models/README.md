# Modelo de detección local

VialScan descarga automáticamente `road-damage-object-detection.onnx` la primera vez que se analizan fotos localmente. El archivo se guarda aquí y no se incluye en Git.

- Fuente y descarga: [CamThink Road Damage Object Detection](https://www.camthink.ai/developer-center/models/road-damage-object-detection/)
- Entrada: imagen 640 × 640.
- Clases: bache, grieta longitudinal, transversal, tipo cocodrilo, borde, bloque y grieta genérica.
- El sitio del modelo declara licencia MIT; el archivo ONNX también contiene metadatos AGPL-3.0. Revisar esas condiciones antes de redistribuir el modelo o usarlo comercialmente.
- Es un detector de daños, no un modelo de certificación vial; un resultado sin detecciones no prueba que la calle esté en buen estado.
