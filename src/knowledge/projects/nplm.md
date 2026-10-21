# Neural Probabilistic Language Model (NPLM)

## 1. Project Overview

**Category:** Deep Learning, Natural Language Processing, Machine Learning Engineering  
**Repository:** https://github.com/gbisco/PNL-model  
**Status:** Completed local research and experimentation project; not a deployed service.

Implemented a **Neural Probabilistic Language Model (NPLM)** inspired by Bengio et al. (2003), together with an end-to-end pipeline for preparing text, training tokenizers, fitting neural networks, evaluating predictions, and automating experiments. The model predicts the next token from a fixed window of preceding tokens using learned embeddings and a feed-forward neural network. The project explores how model size, context length, training budget, and tokenization influence language-model behavior.

The emphasis is on building and evaluating the underlying machine-learning system, not serving a conversational language model or text-generation application.

## 2. Technology Stack

| Technology | Role in the project |
| --- | --- |
| **Python** | Implementation of the data-processing, training, evaluation, and experiment workflows; command-line entry points. |
| **PyTorch** | Model layers, embeddings, tensor operations, optimization, batching, checkpointing, and CPU/GPU training. |
| **Hugging Face `datasets`** | Retrieval of the WikiText-2 corpus. |
| **Hugging Face `tokenizers`** | Training a project-specific byte-pair encoding (BPE) tokenizer. |
| **PyYAML** | Loading reusable experiment and model configuration files. |
| **Matplotlib** | Visualizing training and validation perplexity histories. |
| **Docker Compose** | Reproducible local execution with optional GPU support. |
| **tqdm** | Progress reporting during tokenizer preparation. |

The project implements its own word-level tokenizer workflow and uses the Hugging Face library for BPE training; it does **not** implement the BPE algorithm from scratch. It also does not use a pretrained transformer as its language model.

## 3. Features and Capabilities

- **End-to-end dataset pipeline:** Downloads WikiText-2 text, normalizes records, removes empty documents, performs reproducible 80/10/10 train/validation/test splits with a fixed seed, and writes JSONL shards.
- **Interchangeable tokenization:** Supports word-level tokenization with vocabulary filtering and unknown-token handling, alongside a BPE tokenizer trained on the same project corpus. Tokenizer artifacts can be saved and reused.
- **Configurable model training:** Runs fixed-context next-token training with configurable model dimensions, context length, optimization settings, batch size, and step budgets.
- **Evaluation and checkpoints:** Records training/validation metrics, restores the best validation checkpoint during training, and evaluates saved models using perplexity.
- **Experiment automation:** Runs model-configuration grids, writes structured metrics, supports skipping previously completed results, and produces comparison summaries.

## 4. Architecture and Technical Implementation

### Modular pipeline

The codebase separates **interfaces, factories, orchestrators, and CLI scripts**. Factories choose the relevant downloader, tokenizer, or model implementation from YAML configuration. Orchestrators connect data processing, window construction, training, and evaluation; CLI modules provide entry points for individual stages. This allows experiments to vary important settings without rewriting the pipeline.

### Neural model

The implemented NPLM is a **feed-forward next-token predictor**:

1. Take a fixed-length context of preceding token IDs.
2. Map tokens to learned embeddings.
3. Concatenate and flatten the context embeddings.
4. Apply a linear hidden layer, **Tanh** activation, and dropout.
5. Project to vocabulary-sized logits for next-token prediction.

This is a classic neural language-model architecture, **not a transformer**. Configurations vary context sizes and embedding/hidden dimensions.

### Text preparation and training

Text is tokenized into document-specific sequences, and fixed-size prediction windows are constructed **without crossing document boundaries**. Windows are materialized as PyTorch tensors and batched through `DataLoader`.

Training is **step-based** and uses cross-entropy loss. The documented experiment configurations use Adam, gradient clipping, and periodic evaluation on the validation split. Training records perplexity and restores the checkpoint with the lowest validation perplexity. Checkpoints preserve model weights and the architecture metadata needed to reconstruct a model for evaluation.

### Experiment orchestration

YAML-driven runs systematically vary context size, embedding and hidden dimensions, and training budgets. The automation records outputs as JSON and allows previous results to be reused rather than unnecessarily repeating completed runs. Word-level and BPE tokenizers are evaluated through the same general training pipeline.

## 5. Engineering Decisions and Tradeoffs

- **Configuration-driven experimentation:** Model and training parameters are represented in YAML instead of being scattered through training code, making comparisons easier to reproduce.
- **Component separation:** Interfaces, factories, and orchestration separate model-specific behavior from shared pipeline stages.
- **Reproducible preprocessing:** A fixed random seed and a consistent corpus-processing procedure support comparison within the project. The project creates its own WikiText-2 splits, so its numbers should not be presented as official leaderboard results.
- **Controlled tokenizer experiments:** Both tokenizers are built from the project corpus. Because word-level and BPE tokens represent different units, their raw perplexity values are **not directly comparable**.
- **Memory tradeoff:** Precomputing all context windows simplifies batching and training, but assumes the resulting tensors fit in available memory.
- **Validation-based checkpoints:** Restoring the best validation checkpoint limits dependence on the final training step. The experiment-grid report appears to rank candidate architectures by *test* perplexity; this should be described transparently rather than treating those results as untouched final-test estimates.

These are observable design characteristics and tradeoffs; undocumented personal motivations should not be inferred from them.

## 6. Testing, Evaluation, and Metrics

The project includes **automated unit and integration testing**; test coverage and pass rates have not been independently verified for this knowledge document.

Its ML evaluation uses **cross-entropy and perplexity**, with training time recorded for experiment comparisons. The main word-level grid included **18 configurations**, spanning:

- Context lengths: **3, 5, and 7 tokens**.
- Embedding/hidden sizes: **32/64, 64/128, and 128/256**.
- Training budgets: **500 (`tiny`) and 5,000 (`medium`) steps**.

The best reported word-level experiment used **context length 5**, **128-dimensional embeddings**, **256 hidden units**, and **5,000 training steps**, reaching **255.04 test perplexity**. Larger model dimensions and longer training generally performed better in the word-level grid; a longer context did not consistently help. Additional exploratory runs examined longer contexts and generalization gaps.

The most important outcome is the **repeatable ML experimentation workflow**, not the standalone perplexity score.

## 7. Execution, Status, and Limitations

The project is a **local, container-supported research implementation**. It can run through Docker Compose or a compatible local Python environment, and it supports GPU execution where available. Models are saved as local checkpoint files; run metrics and summaries are saved as structured artifacts.

There is no supported evidence of a hosted inference API, cloud deployment, or interactive text-generation service. The architecture uses fixed context windows and in-memory materialization, so it is not designed as a large-scale production language model. Performance numbers are specific to this dataset, preprocessing, and experiment setup.

## 8. Skills and Engineering Takeaways

This project provides concrete evidence of experience with:

- **PyTorch and deep learning:** Implementing embeddings, neural layers, optimization, training loops, and checkpoint recovery.
- **NLP engineering:** Dataset preparation, vocabulary management, word/subword tokenization, context-window generation, and next-token prediction.
- **ML experimentation:** Configurable hyperparameters, automated runs, quantitative evaluation, and careful interpretation of perplexity.
- **Python software design:** Modular abstractions, factories, orchestrators, CLI entry points, and reusable configuration.
- **Reproducible workflows:** Fixed data splits, saved tokenizer/model artifacts, metrics logging, and Docker-based execution.

**Project distinction:** This is an end-to-end implementation and experimental study of a foundational neural language model, combining practical ML development with structured software engineering.
