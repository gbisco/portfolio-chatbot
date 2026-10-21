# SecureBank — Project Knowledge

**Project:** SecureBank Fraud Detection System  
**Category:** Machine Learning Engineering · Backend Development · Financial Fraud Classification  
**Repository:** https://github.com/gbisco/securebank  
**Status:** Dockerized, locally runnable machine-learning system prototype; no verified public production deployment

## 1. Project Overview

SecureBank is an end-to-end machine-learning prototype for detecting potentially fraudulent card transactions. It goes beyond training a classifier in a notebook: the repository implements a workflow for combining raw data sources, preparing model-ready features, training and evaluating fraud models, registering a selected model, serving transaction-level predictions through an API, and recording operational logs.

The prediction task is **binary classification** (`is_fraud`), with responses presented as **`legitimate`** or **`fraudulent`**. The system combines transaction attributes with customer profile information to make its decisions. Because fraud is an imbalanced classification problem, the project focuses on the trade-off between detecting fraud and minimizing false positives rather than optimizing accuracy alone.

## 2. Technology Stack

| Technology | Role in SecureBank |
| --- | --- |
| **Python** | Application and ML pipeline implementation |
| **Flask** | HTTP API for dataset generation, model training, health checks, and fraud prediction |
| **Pandas** | Multi-source data merging, cleaning, feature preparation, and tabular processing |
| **Scikit-learn** | Logistic regression baseline, `HistGradientBoostingClassifier`, dataset splitting, preprocessing utilities, and evaluation metrics |
| **PyArrow** | Reading Parquet transaction data |
| **Joblib** | Saving and loading fitted model wrappers, estimators, and feature-adapter state |
| **JSON / CSV / Parquet** | Input sources, generated datasets, model metadata, API payloads, and structured logs |
| **Docker** | Containerized Flask runtime using a Python 3.9 base image |
| **Bash / curl** | Scripts for building the container and invoking the main API workflows |

The gradient boosting implementation uses **scikit-learn's histogram-based gradient boosting**, not XGBoost or a custom neural network.

## 3. Features & Capabilities

SecureBank exposes four Flask routes:

- **`GET /`** — Reports basic service status and available endpoints.
- **`POST /create_dataset`** — Loads customer, transaction, and fraud-label sources; produces a cleaned dataset; saves a timestamped CSV; and returns a data-quality summary.
- **`POST /train_model`** — Preprocesses data, trains the configured default model, evaluates probability thresholds using validation data, evaluates the selected operating point on a test split, saves versioned artifacts and metadata, and optionally registers the model as the default.
- **`POST /predict`** — Accepts a transaction JSON payload, enriches it with customer information, loads the registered model and its selected threshold, and returns a fraud label and probability.

The API returns both a human-readable fraud verdict and structured information such as the numeric class, fraud probability, model type, and threshold. Training and inference are separate workflows: **a prediction does not retrain the model**.

## 4. Architecture & Technical Implementation

### Layered Python application

The code separates HTTP routing from business workflows and ML internals:

1. **Flask routes (`app.py`)** expose the API and delegate requests.
2. **Service layer** handles dataset generation, training/registration, and prediction responses.
3. **Training and prediction orchestrators** coordinate each ML workflow.
4. **Shared data preprocessing** validates and prepares inputs independent of the estimator.
5. **Model wrapper and adapters** handle model-specific features, fitting, inference, serialization, and consistent interfaces.
6. **Evaluation and logging modules** calculate classification metrics and write structured JSON events.

This modularity makes it possible to support multiple estimators without duplicating the entire ETL or API implementation.

### Data pipeline

The training pipeline combines three source formats: customer profiles in **CSV**, transactions in **Parquet**, and fraud labels in **JSON**. It joins fraud labels to transactions, removes duplicates, merges customer records using `cc_num`, handles optional missing values, validates required fields, and derives time-based features from transaction timestamps.

The dataset-generation service can write a cleaned CSV and summarize row/column counts, missing values, fraud-label distribution, fraud rate, unique customers, and duplicate transactions. The training pipeline then applies a configurable **train/validation/test** split. Its default random holdout allocation is approximately **70% / 10% / 20%**, using stratification by `is_fraud`; a chronological **time-based split** is also implemented.

### Model-specific feature engineering

Both estimators use a shared preprocessing foundation but different adapters:

- **Categorical features** including category, state, sex, day of week, and month are encoded into numeric indicators; the higher-cardinality `job` field uses frequency encoding.
- **Derived customer and transaction features** include approximate age from date of birth, time-of-day/week indicators, minutes since the previous transaction, and flags for repeat transactions within 5, 30, or 60 minutes.
- **Logistic regression** applies numeric scaling using `StandardScaler`; **histogram gradient boosting** uses the unscaled numeric representation.
- **Training-time feature columns and adapter state** are saved so inference reindexes incoming data to the feature layout expected by the trained model. Unknown categorical values can be handled through aligned columns or missing frequency defaults.

The time-delta features are estimated from available transaction records; a single-transaction prediction uses a training-derived fallback when preceding transaction history is unavailable. The project does **not** maintain a live per-customer transaction-history service.

### Models and inference

A common `ModelWrapper` supports two model families:

- **Logistic regression:** A scikit-learn baseline with a common probability/threshold interface and a separate feature-scaling adapter.
- **Histogram gradient boosting:** The configured default model, using scikit-learn `HistGradientBoostingClassifier` to capture nonlinear relationships across transaction and customer features.

The gradient boosting model supports configurable boosting iterations, learning rate, tree capacity, minimum samples per leaf, L2 regularization, class weighting, and random seed. Inference loads the saved estimator and fitted adapter via Joblib, then compares `predict_proba` fraud scores against the **registered threshold**.

### Model artifacts and registration

Training saves a timestamped `.joblib` model and JSON metadata containing model type, configuration, selected threshold, split strategy, and evaluation results. A `default_model.json` pointer tells the prediction workflow which model and threshold to load. This is lightweight **file-based model versioning/registration**, not an external model registry.

## 5. Engineering Decisions & Challenges

**End-to-end ML system design.** The primary engineering contribution is integrating data processing, training, evaluation, model registration, and API serving into a repeatable workflow rather than stopping at a fitted estimator.

**Separation of generic and model-specific preprocessing.** Shared cleaning/schema validation happens before adapter-specific transformations. This reduces duplication between logistic regression and gradient boosting and helps maintain consistent inference behavior.

**Class-imbalance-aware threshold selection.** The training service evaluates a set of probability thresholds on validation data. It selects the highest-F1 result satisfying configured minimum precision and recall targets (both default to **0.70**), with a highest-F1 fallback if none qualifies. The chosen threshold is then evaluated on the test split and stored for serving. This explicitly connects modeling metrics to false-positive versus missed-fraud trade-offs.

**Reproducibility and operational continuity.** Fixed-seed holdout splitting, saved feature transformations, versioned artifacts, and registered threshold metadata support repeatable training and inference. The separate dataset and training endpoints allow an operator to refresh the model using updated source files, though refresh is not automatically scheduled.

## 6. Testing & Evaluation

The repository includes **automated unit and integration testing**. Test implementations, coverage, and pass rates were not inspected for this knowledge summary.

The evaluation module implements **accuracy, balanced accuracy, precision, recall, F1, ROC AUC, average precision, confusion-matrix counts, false-positive rate, false-negative rate, and specificity**. For rare-event fraud classification, precision, recall, F1, and average precision are more informative than accuracy alone.

The system report documents staged tuning of histogram gradient boosting against a logistic-regression baseline, including learning rate, boosting iterations, tree capacity, regularization, and the operating threshold. **The strongest documented run** used a probability threshold of **0.60** and achieved approximately **96.0% precision, 72.8% recall, and 82.8% F1** on the held-out test split. These are documented evaluation results, not metrics independently recalculated during this review.

The central evaluation takeaway is that the gradient-boosting implementation produced a better reported precision–recall balance than logistic regression, whose high-recall thresholds incurred many false positives.

## 7. Deployment, Logging & Project Status

The repository provides a **Dockerized local Flask API** and Bash/curl scripts for starting the service, generating datasets, training a model, and submitting example predictions. The runtime uses **Python 3.9** and exposes port **5000**. Model artifacts, processed datasets, and logs are stored on the filesystem.

A `JsonLogger` records timestamped JSON files for workflow status, API activity, response metadata, and errors. This is a foundation for observability, **not a live monitoring dashboard or implemented automatic drift-detection system**. The system report proposes future monitoring of production precision/recall, feature drift, prediction drift, review outcomes, and customer impact, but these should not be described as implemented.

The project is a **prototype rather than a verified production banking deployment**. The included Flask routes do not implement administrator authentication, and the current request logging can contain transaction input details; production use would require stronger access controls, privacy-aware logging, and more robust operational infrastructure. No public hosted service, cloud model registry, scheduled retraining, or automated model-drift response is established by the inspected repository.

## 8. Skills & Engineering Takeaways

SecureBank demonstrates applied experience across **machine learning engineering and Python backend development**:

- Building an end-to-end tabular ML pipeline with heterogeneous CSV/Parquet/JSON inputs.
- Designing reusable preprocessing, schemas, model adapters, service layers, and orchestrators.
- Engineering categorical, demographic, temporal, and transaction-frequency features.
- Implementing logistic regression and histogram gradient boosting with scikit-learn.
- Working with imbalanced-class metrics and validation-driven decision thresholds.
- Separating model training from inference and preserving fitted preprocessing state.
- Saving versioned models, evaluation metadata, and an active-model pointer.
- Serving ML predictions through Flask JSON endpoints and packaging the workflow with Docker.
- Designing structured logging and testable interfaces for an ML service.

**Project distinction:** SecureBank is best described as a **Dockerized, API-served fraud detection ML system prototype**. Its strongest engineering story is the integration of data preparation, feature adaptation, model selection, threshold optimization, artifact management, and prediction serving—not merely the performance of one classification model.

---

## Sources & Verification (for maintaining this knowledge file)

Primary sources inspected: `README.md`, `securebank/System_Report.md`, `securebank/app.py`, `securebank/requirements.txt`, `securebank/Dockerfile`, `securebank/executables/`, and the source modules under `securebank/modules/data/`, `models/`, `train/`, `predict/`, `services/`, `evaluation/`, and `log/`.

**Intentionally excluded:** raw datasets, data exploration images, and `test/` implementations. Reported numerical results are taken from repository documentation, not independently recalculated.

**Result selection:** The project includes several training runs. This summary reports only the strongest documented run from `System_Report.md`, as identified by the project author.
