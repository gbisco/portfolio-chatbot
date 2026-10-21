# TechTrack — Project Knowledge

**Project type:** Computer vision / machine learning engineering / video inference  
**Repository:** https://github.com/gbisco/techtrack  
**Primary focus:** Modular object detection, video-stream processing, detection evaluation, and model-improvement preparation through hard-negative mining.  
**Context:** Computer-vision implementation project based on a Johns Hopkins University assignment and its supporting TechTrack architecture. The repository contains completed application and utility code as well as some provided scaffolding; do not assume every component was written from scratch.

## 1. Project Overview

TechTrack is a Python-based computer-vision system for running object detection over video frames using pretrained YOLO models. Its inference service receives a video source, samples frames, runs detection with OpenCV's DNN interface, filters predictions by confidence and non-maximum suppression (NMS), and outputs annotated frames and detection information. The project is oriented toward logistics-style object-detection data, with model artifacts and sample videos supplied separately from the source repository.

The project extends beyond inference. It includes a detection-evaluation toolkit and a **rectification / retraining-preparation component** that identifies difficult examples using a YOLO-inspired loss calculation and hard-negative mining (HNM). These selected examples could be used to improve training datasets in a subsequent retraining workflow. The uploaded repository **does not implement an automatic YOLO weight-training or model-retraining loop**, so TechTrack should be described as *supporting retraining through data selection*, not autonomously retraining models.

## 2. Technology Stack

| Technology | How it is used |
| --- | --- |
| **Python** | Core implementation of the video-inference, evaluation, and rectification modules. |
| **OpenCV (`cv2`, DNN)** | Loads pretrained YOLO weights/configuration, creates image blobs, runs forward passes, reads video frames, draws detections, and saves annotated images. |
| **NumPy** | Array processing for detections, geometry, class scores, IoU, loss components, and custom class-aware NMS. |
| **Pandas** | Tabular tracking and ranking of candidate hard-negative examples by loss-related criteria. |
| **Scikit-learn** | `label_binarize` support for per-class precision–recall evaluation. |
| **YOLOv4-tiny** | Pretrained detection architecture used by the included inference runner; the runner points to separate logistics model weights, configuration, and class-label files. |
| **FFmpeg / FFplay** | Documented workflow for sending and viewing MPEG-TS video over a local UDP stream. |
| **Docker** | Python 3.12-based application image with FFmpeg and computer-vision dependencies for containerized execution. |
| **GitHub Actions / Classroom** | Repository includes an automated grading workflow with unit-level checks; no independent pass-rate or coverage figure is established from the uploaded archive. |

The requirements file also lists Matplotlib, Seaborn, SciPy, and PyArrow. Their presence in dependencies alone should not be presented as evidence that all of them drive the core runtime pipeline.

## 3. Features and Capabilities

**Video inference.** The system accepts OpenCV-compatible video sources, including the UDP stream described in the assignment. A generator yields frames at a configurable sampling interval (`drop_rate`) to reduce how many frames undergo detection. The example runner uses `drop_rate=60`.

**Object detection and visualization.** A `Detector` wraps OpenCV DNN's YOLO forward pass. Model output is converted into image-coordinate bounding boxes, predicted class IDs, objectness/confidence values, and class-score vectors. The application logs detections and saves frames with box overlays, class IDs, and confidence scores when objects are found.

**Custom NMS.** Rather than delegating to OpenCV's built-in NMS, the implementation uses NumPy to apply confidence filtering, group candidates by class, rank candidates by score, calculate bounding-box overlap, and suppress lower-ranked boxes above an IoU threshold. This is an important implementation detail: NMS reduces duplicate detections while retaining distinct objects.

**Detection evaluation.** Separate utilities measure bounding-box intersection-over-union (IoU), match predictions against annotated objects, account for false positives and missed objects, construct per-class precision–recall curves, and calculate interpolated mean average precision (mAP).

**Rectification / retraining-data selection.** The `HardNegativeMiner` runs detections against labeled images, evaluates errors using a custom loss measure, collects per-image scores in a Pandas DataFrame, and selects the highest-loss examples according to a chosen criterion. This provides a way to prioritize difficult samples for later review or model retraining.

## 4. Architecture and Technical Implementation

### 4.1 Inference pipeline

The repository separates video capture (`modules/inference/preprocessing.py`), detection (`modules/inference/model.py`), suppression (`modules/inference/nms.py`), and orchestration (`app.py`). The typical data flow is:

```text
FFmpeg/video source → OpenCV frame capture → frame sampling
  → YOLOv4-tiny forward pass → detection decoding / confidence filtering
  → per-class NumPy NMS → detection logging and annotated-image output
```

In `Detector.predict()`, frames are converted to **416 × 416** image blobs with pixel values scaled by **1/255** and RGB channel ordering before the OpenCV DNN forward pass. `post_process()` reads raw YOLO outputs, extracts the most likely class, filters low-confidence detections, and converts normalized center-based coordinates into pixel-space `[x, y, width, height]` boxes. The example runner configures a **0.5 confidence threshold** and **0.4 NMS IoU threshold**; these are example settings, not experimentally established optimal values.

`InferenceService.run()` coordinates the components rather than implementing each operation directly. The design makes video sampling, detector behavior, and NMS logically separable and testable.

### 4.2 Metrics and evaluation

The evaluation module distinguishes localization and classification performance. `calculate_iou()` evaluates overlap between predicted and ground-truth boxes. `match_detections()` matches detections to annotations using an IoU threshold and prepares true labels and prediction scores, with scoring modes for **objectness**, **class scores**, or their **combined** product. The precision–recall utility calculates class-specific curves across score thresholds; the mAP helper uses **11-point interpolated average precision** by default.

These utilities are valuable for evaluating and comparing detectors, but **the archive does not contain a verified benchmark table or numerical mAP result for the trained YOLO models**. The project should not claim a specific detection accuracy, FPS, or mAP without separately documented evaluation results.

### 4.3 Rectification and preparation for retraining

The repository's `modules/rectification/` and `modules/utils/loss.py` provide the model-improvement side of the project:

1. **Candidate collection:** `HardNegativeMiner` iterates over image files and matching text annotation files in a dataset directory, loads each image, and runs the detector.
2. **Error measurement:** The `Loss` class extracts prediction boxes, objectness scores, and class-score vectors, aligns detections with ground truth using IoU, and computes a modified YOLO-style error breakdown.
3. **Loss components:** The calculation separately tracks **bounding-box localization error**, **objectness error for matched detections**, **no-object confidence error for unmatched predictions**, and **class-prediction error**. Configurable `lambda` weights combine these into `total_loss`.
4. **Hard-example selection:** The miner records the loss components for each candidate in a DataFrame, sorts descending by a requested metric (for example, `total_loss`), and returns the top-N highest-error samples.
5. **Potential retraining use:** The ranked images and annotations can inform which examples should receive attention in a subsequent dataset-curation or training pass.

This is not merely an inference-only project: **hard-negative mining and loss-based sample selection are implemented**. However, the archive's augmentation file defines transformation methods—horizontal flip, Gaussian blur, resize, brightness adjustment, and composite transforms—as **unimplemented stubs**. No integrated optimizer, training loop, or weights-update pipeline is present. Therefore, data augmentation and end-to-end retraining should be described as *possible extensions*, not completed features.

## 5. Engineering Decisions and Technical Challenges

- **Modular responsibilities:** Frame acquisition, model execution, NMS, scoring, and hard-negative selection are separate components instead of one monolithic detection script.
- **Throughput control:** Generator-based frame sampling permits the application to process selected frames from a video source rather than running every frame through detection.
- **Custom detection postprocessing:** NumPy-based, per-class NMS demonstrates implementation of ranking, bounding-box geometry, and overlap suppression, not only use of a pretrained model's predictions.
- **Evaluation beyond accuracy:** IoU, precision–recall, and mAP provide a more appropriate basis for examining object detection than simple classification accuracy.
- **Feedback-oriented ML engineering:** The loss breakdown and HNM ranking address an important problem after deploying a detector: identifying the images on which the model performs poorly so future training effort can be targeted.
- **Explicit model boundaries:** The project loads external pretrained YOLO weights. It does not establish that a new YOLO architecture was trained from scratch or that an autonomous retraining pipeline was deployed.

These are technical characteristics supported by the implementation; the repository does not independently document the author's personal motivation for every design choice.

## 6. Testing and Evaluation

The repository contains `test/` modules and a GitHub Classroom workflow configured to run checks on inference behavior, NMS, metrics, loss calculations, hard-negative mining, and other expected functionality. The assignment documentation also defines model-comparison and robustness-analysis tasks. However, those assignment instructions should **not** be mistaken for completed experiments: the inspected archive does not include a completed case-analysis report or reproducible benchmark metrics.

The implemented measurement mechanisms include IoU-based matching, precision–recall curve generation, interpolated mAP, and per-image loss-component scoring. Their primary value for a portfolio discussion is evidence of working with **object-detection validation and error analysis**, rather than a claim of a particular benchmark score.

## 7. Runtime, Deployment, and Project Status

The repository includes a Dockerfile for a Python 3.12 image, FFmpeg installation, Python dependencies, and an `app.py` entry point. The assignment documents using FFmpeg to stream MPEG-TS video over UDP to a locally running inference service, and the runner points to separately downloaded YOLO weights, configuration, and labels. Annotated frames are written to a local output directory.

This supports describing TechTrack as a **containerized, locally runnable computer-vision workflow**, not as a publicly deployed inference API or cloud-hosted service. Model weights and datasets are downloaded separately and are not included in the supplied source archive. The `techtrack/README.md` in this snapshot is essentially a placeholder, while the assignment Markdown files explain the intended setup and architecture.

**Implementation status:** Video sampling, YOLO inference, confidence filtering, custom NMS, visualization, evaluation utilities, loss-based scoring, and hard-negative selection are present. Automatic retraining and image-augmentation methods are not completed in this snapshot.

## 8. Engineering Skills Demonstrated

TechTrack provides concrete examples of:

- **Computer vision and deep-learning inference:** Running pretrained YOLO detectors through OpenCV DNN and interpreting model outputs.
- **Python/NumPy engineering:** Implementing class-aware NMS, bounding-box transformations, thresholding, and loss/metric calculations.
- **Video processing:** Receiving streams, sampling frames, and generating annotated images.
- **ML evaluation:** IoU, false-positive/false-negative accounting, precision–recall curves, and mAP calculations.
- **ML error analysis and retraining preparation:** Measuring where models struggle and using hard-negative mining to select informative examples for future training.
- **Data processing:** Using Pandas to organize, rank, and filter model-error observations.
- **Modular software design:** Integrating separable components into an inference service with a Docker runtime and automated test infrastructure.

**Concise portfolio description:** TechTrack is a modular Python computer-vision project that processes video streams using pretrained YOLOv4-tiny object detection. It implements custom NumPy-based non-maximum suppression, evaluates detections with IoU/precision–recall/mAP utilities, and includes a loss-based hard-negative mining component to identify difficult examples for future retraining. The inference workflow is packaged for local containerized execution with OpenCV, Docker, and FFmpeg.

---

## Source Notes — For Maintaining This Knowledge Document

The project summary was prepared from the uploaded `techtrack-main(1).zip` snapshot; the repository URL above was provided separately by the project owner. Specific implementation evidence includes:

- `IMPLEMENTATION_ASSIGNMENT.md` and `ANALYSIS_DESIGN_ASSIGNMENT.md` — assignment scope, expected functionality, and intended rectification architecture.
- `techtrack/app.py` — inference orchestration, frame processing, logging, and annotated-frame output.
- `techtrack/modules/inference/preprocessing.py` — video frame capture and sampling.
- `techtrack/modules/inference/model.py` — pretrained YOLO DNN loading, 416 × 416 blob construction, prediction parsing.
- `techtrack/modules/inference/nms.py` — custom class-aware NMS with NumPy.
- `techtrack/modules/utils/metrics.py` — IoU, detection matching, precision–recall, and mAP.
- `techtrack/modules/utils/loss.py` — modified YOLO loss component calculation and weighting.
- `techtrack/modules/rectification/hard_negative_mining.py` — hard-example tabulation, ranking, and selection.
- `techtrack/modules/rectification/augmentation.py` — defined augmentation interface with methods not yet implemented.
- `techtrack/Dockerfile`, `techtrack/requirements.txt`, `techtrack/README.md`, `.github/workflows/classroom.yml` — environment and test scaffolding.

Do not present assignment requirements, supplied pretrained weights, or unimplemented augmentation/retraining methods as features independently verified to be complete.
