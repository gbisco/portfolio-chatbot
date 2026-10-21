# Shinkansen Travel Experience Hackathon — Project Knowledge

## 1. Project Overview

**Project:** Shinkansen Travel Experience Hackathon  
**Category:** Applied machine learning, binary classification, data science  
**Context:** MIT Applied AI & Data Science certification hackathon  
**Competition result:** 11th place out of 100 participants (reported by Gabriel)  
**Repository:** https://github.com/gbisco/Shinkansen-Travel-Experience-Hackathon

The project investigates passenger satisfaction on Japan's Shinkansen bullet trains. The objective was to predict whether a passenger was satisfied with their overall travel experience and examine which travel and survey attributes were informative. The target, `Overall_Experience`, is binary: **1 = satisfied**, **0 = not satisfied**. The supplied data consisted of separate travel-information and passenger-survey CSV files, with labeled training data and an unlabeled competition test set.

The repository documents multiple approaches rather than just one trained classifier: a logistic-regression baseline, an XGBoost classifier, and several fully connected neural-network classifiers combined into a weighted ensemble. The project was developed in Jupyter notebooks and produced CSV files of passenger-level predictions for submission.

## 2. Technology Stack

- **Python:** Data preparation, exploratory analysis, modeling, and prediction export.
- **Pandas and NumPy:** Reading CSVs, combining travel and survey attributes, inspecting data, transforming categorical features, and preparing model inputs.
- **Scikit-learn:** Logistic regression, stratified train/validation splits, classification reports, and evaluation utilities.
- **XGBoost:** Gradient-boosted decision-tree classification for structured passenger data.
- **TensorFlow/Keras:** Construction and training of feed-forward neural networks with Dense and Dropout layers, Adam optimization, binary cross-entropy, and early stopping.
- **SHAP and XGBoost feature importance:** Investigating feature contributions and ranking influential encoded input variables.
- **Matplotlib and Seaborn:** Exploratory visualizations, correlations, and training/model evaluation plots.
- **Jupyter Notebook:** Iterative experimentation and documentation of modeling approaches and outputs.

These tools served different purposes: tabular feature preparation, classical ML baselines, boosted-tree modeling, neural-network experimentation, interpretability, and competition submission generation.

## 3. Features & Capabilities

- Combines the provided travel and survey datasets into model-ready passenger records, taking care to avoid duplicate identifier columns.
- Inspects data shapes, columns, missing values, and numeric-feature relationships as part of exploratory analysis.
- Handles missing categorical/unknown values and transforms categorical inputs into dummy/one-hot encoded features.
- Aligns encoded training and competition-test columns to avoid mismatched feature dimensions at prediction time.
- Trains and evaluates a logistic-regression baseline.
- Trains an `XGBClassifier` and generates passenger-level predictions.
- Defines and compares neural-network architectures of varying depth and width.
- Combines predictions from multiple neural networks using accuracy-derived ensemble weights.
- Produces CSV outputs containing passenger `ID` and predicted `Overall_Experience` labels.
- Uses feature-importance visualizations and SHAP analysis to investigate the signals behind XGBoost predictions.

## 4. Architecture & Technical Implementation

### Data preparation

The repository includes separate train/test travel and survey files. Notebook workflows read the CSVs, assemble features across the two sources, and separate the labeled `Overall_Experience` target from the predictors. The main modeling paths use Pandas `get_dummies` to convert categorical attributes to numeric columns. For competition inference, training and test matrices are aligned with `DataFrame.align(..., join='left', axis=1, fill_value=0)` to keep a consistent feature schema.

For local modeling comparisons, notebooks use a **stratified 80/20 train/validation split**, preserving the distribution of satisfaction labels. This is distinct from the separately supplied, unlabeled competition test data.

### Modeling approaches

**Logistic regression:** Serves as a straightforward supervised-learning baseline. It is trained on encoded passenger features and assessed with precision, recall, F1-score, and accuracy from scikit-learn's classification report.

**XGBoost:** Uses gradient-boosted trees for structured-data classification. The XGBoost notebook configures `XGBClassifier` with a binary logistic objective, 1,500 estimators, maximum depth 35, learning rate 0.075, column subsampling of 0.8, and a fixed random seed. It trains a model, predicts the unlabeled test set, and exports predictions. The notebook also includes XGBoost feature-importance plotting and SHAP summary analysis. These are recorded settings, not proof of a completed hyperparameter search.

**Deep learning and ensemble:** The Keras notebook defines five feed-forward classification networks with differing layer counts and configurations. Layers use ReLU activations, dropout, and a final sigmoid output for binary probability prediction. Models use Adam, binary cross-entropy, and accuracy tracking. Training is configured for up to 35 epochs, batch size 32, a validation split, and `EarlyStopping(patience=7, restore_best_weights=True)`. A custom ensemble routine combines model predictions using weights derived from validation accuracies and converts the aggregate probabilities to binary labels.

### Interpretability

The XGBoost notebook uses model feature-importance plots and `shap.Explainer` to explore which encoded passenger attributes contribute to predictions. The project objective included understanding factors associated with positive passenger feedback; the archived materials demonstrate the analysis methods, but this knowledge summary does not assert an unsupported ranked list of the most influential features.

## 5. Engineering Decisions & Challenges

**Multiple modeling families:** Comparing logistic regression, gradient-boosted trees, and dense neural networks provided distinct baselines for the same tabular classification task instead of assuming one model architecture would perform best.

**Feature-schema consistency:** One-hot encoding training and test sets separately can produce different columns. The notebook explicitly aligns those matrices before inference, addressing a practical issue in end-to-end tabular ML workflows.

**Class-aware validation:** Stratified splitting helps maintain representative proportions of satisfied and dissatisfied passengers when comparing classifiers.

**Neural ensemble:** The ensemble work includes reusable model builders, repeated training, early stopping, validation-based weighting, and aggregation of probability outputs. This demonstrates implementation beyond a single off-the-shelf neural network.

**Explainability:** XGBoost importance and SHAP analysis extend the project from classification to examining the relationship between input attributes and model predictions.

The archived notebooks document *what* was implemented; personal motivations for individual choices and the exact final competition submission are not independently established by the code.

## 6. Testing & Evaluation

The competition's stated evaluation metric was **classification accuracy**: the proportion of correctly classified passengers. The notebooks also use precision, recall, F1-score, confusion-matrix/evaluation utilities, and neural-network training/validation metrics.

Representative notebook results include:

- **Logistic-regression baseline:** Approximately **90% validation accuracy** on a stratified validation split; class-level precision, recall, and F1 are reported.
- **Neural-network weighted ensemble:** **0.949036 accuracy (~94.90%)** on the notebook's validation set, with five models contributing predictions.
- **XGBoost:** The repository documents model training, inference, and feature-importance analysis, and its README states XGBoost was the best approach in its comparison. A directly comparable validated XGBoost score or official competition submission score was not established from the inspected notebook outputs.
- **Competition placement:** **11th out of 100 participants**, as reported by Gabriel; this is separate from local validation accuracy.

Do not present local validation accuracy as a competition leaderboard score, or assume all model versions used identical processing and evaluation conditions.

## 7. Execution & Project Status

The repository is a **notebook-based data science hackathon project**, not a deployed prediction service. It contains three main modeling notebooks and four source CSV datasets: travel/survey data for training and competition testing. The notebooks can generate CSV submissions with passenger identifiers and predictions. There is no evidence in the supplied archive of a production prediction API, automated deployment pipeline, or serving infrastructure.

Potential follow-up improvements, rather than claimed completed features, include systematically tuning hyperparameters, consolidating preprocessing into reusable pipelines, and comparing model families under a single consistent validation protocol.

## 8. Skills & Engineering Takeaways

This project provides evidence of practical experience with:

- **End-to-end tabular ML:** Joining heterogeneous source datasets, addressing missing values, encoding categories, aligning feature matrices, and generating competition predictions.
- **Supervised classification:** Training and comparing interpretable linear models, boosted trees, and neural networks.
- **Model evaluation:** Stratified validation and measurement of accuracy, precision, recall, and F1-score.
- **Deep learning:** Building configurable Keras classification architectures, controlling training with early stopping, and implementing a weighted ensemble.
- **Model interpretability:** Using feature importance and SHAP to investigate drivers of predictions.
- **Applied data science communication:** Relating model outputs to a business-oriented question about passenger experience and satisfaction.

The distinguishing aspects are the **breadth of modeling approaches**, the handling of real mixed-type tabular inputs, the ensemble implementation, and the competition result—not a production deployment claim.

---

## Source and Verification Notes (for maintainers)

- `README.md`: Problem definition, target coding, accuracy criterion, and author's note about XGBoost.
- `Hackathon_notebook_Data_analysis_and_Regression_Gabriel_Bisco.ipynb`: Logistic regression baseline, preprocessing, validation reports, and CSV export.
- `Hackathon_notebook_Deep_Learning_Gabriel_Bisco_Reinato.ipynb`: Keras architectures, ensemble logic, evaluation output, and submission workflow.
- `Hackathon_notebook_XGBoost_Gabriel_Bisco_Reinato_v2.ipynb`: XGBoost configuration, inference, SHAP, and feature importance.
- `Traveldata_train.csv`, `Surveydata_train.csv`, `Traveldata_test.csv`, `Surveydata_test.csv`: Provided input datasets; avoid incorporating individual passenger records into chatbot knowledge.
- **11th-place finish:** Supplied directly by Gabriel; not independently established by the repository.
