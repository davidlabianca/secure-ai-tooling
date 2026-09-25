# Persona corpus fixture

**This is test input, not CoSAI Risk Map content.** It is a small, hand-authored, purpose-built
stand-in for `risk-map/yaml/personas.yaml`. None of the personas below exists in the real corpus. It
must not be cited, validated, or consumed as if it were real Risk Map content. It is refreshed only if
the persona entity shape changes structurally, never in response to the real corpus growing.

The four entries below are the complete persona set for any case that names this file.

```yaml
id: personaSyntheticDatasetCurationProvider
title: Synthetic Dataset Curation Provider
description:
  - >
    Actors that clean, deduplicate, label, and package raw data into
    general-purpose, reusable training datasets for consumers other than
    themselves, including other teams within their own organization. The
    work also covers documenting provenance and licensing terms and
    versioning curated releases. This persona covers the general-purpose
    preparation and packaging step in the data lifecycle, not the
    acquisition of raw data itself or the data handling a model trainer
    performs solely for its own training runs. It does not cover building
    a dataset to a single client's task specification.
  - >
    Actors that acquire, license, or generate raw data from its original
    source, without cleaning, deduplicating, or labeling it, are covered by
    Synthetic Data Sourcing Provider instead.
  - >
    Actors that prepare or check data solely for their own training runs,
    or consume a prepared dataset to train or fine-tune a model, are
    covered by Synthetic Model Training Consumer instead.
mappings:
  iso-22989:
    - AI Partner (data supplier)@2022
responsibilities:
  - Raw data cleaning, deduplication, and normalization for training-dataset preparation
  - Data labeling and annotation for general-purpose training datasets
  - Dataset provenance, lineage, and licensing-compliance documentation
  - Curated dataset versioning and release management
identificationQuestions:
  - Do you clean, deduplicate, or label raw data and package the result into a reusable, general-purpose training dataset for consumers other than yourself, including other teams within your own organization?
  - Do you label or annotate data (e.g., classification tags, bounding boxes, or transcripts) for inclusion in a dataset that others will reuse?
  - Do you compile provenance documentation covering the aggregated sources in a packaged dataset (e.g., source list, licensing terms, or collection process), for the downstream recipients of that package?
  - Do you version the curated dataset releases you make available to other consumers separately from the raw data they were derived from?
  - Are you responsible for confirming, before you release a packaged dataset, that you hold the licence and data-subject consent needed to redistribute its data to its recipients inside or outside your organization?
  - Do you prepare data for reuse by others after it has been acquired or generated, whether your own team or another party (e.g., another organization or a data broker) acquired it?
```

```yaml
id: personaSyntheticDataSourcingProvider
title: Synthetic Data Sourcing Provider
description:
  - >
    Actors that acquire, license, generate, or collect raw data from its
    original source (e.g., web scraping, sensor collection, or synthetic
    data generation) for eventual use in AI training, without cleaning,
    deduplicating, or labeling the data themselves. Acquisition and
    licensing of raw data is this persona's boundary; once data has been
    acquired, general-purpose cleaning, deduplication, and labeling for
    redistribution is covered by Synthetic Dataset Curation Provider
    instead.
mappings:
  iso-22989:
    - AI Partner (data supplier)@2022
responsibilities:
  - Lawful acquisition, licensing negotiation, and consent capture at the point of collection
  - Original chain-of-custody recording for data as it first enters the organization
  - Source-system access control and collection-pipeline integrity
identificationQuestions:
  - Do you acquire, license, or generate raw data from its original source (e.g., web scraping, sensor collection, or synthetic data generation)?
  - Do you negotiate or manage data licensing agreements with third-party data providers, rather than confirming that an already-packaged dataset's redistribution complies with licences another party negotiated?
  - Does your organization operate data collection infrastructure (e.g., sensors, scrapers, or survey tools) to generate raw data at the source?
  - Are you responsible for the initial chain-of-custody record when raw data first enters your organization's systems, rather than compiling lineage documentation for downstream recipients of a packaged, curated dataset?
  - Do you hand off acquired raw data to a separate team or organization for cleaning, deduplication, or labeling, rather than performing that preparation yourself?
```

```yaml
id: personaSyntheticModelTrainingConsumer
title: Synthetic Model Training Consumer
description:
  - >
    Actors that train or fine-tune a model on data for their own use: a
    dataset prepared or packaged by another party, or data they prepare
    solely for their own training runs, including task-specific quality
    checks before a training run. This persona covers preparing and using
    data for one's own training, not the cleaning, deduplication,
    labeling, or packaging of datasets for other consumers to reuse,
    which is covered by Synthetic Dataset Curation Provider instead.
responsibilities:
  - Data preparation and quality checks for the actor's own training runs
  - Training-run configuration, hyperparameter, and checkpoint management
  - Selection of which curated dataset release to consume for a given run
identificationQuestions:
  - Do you train or fine-tune a model using a dataset prepared or packaged by another party, or data you prepared solely for your own training runs?
  - Do you prepare or check data only for training runs you are conducting, rather than preparing datasets for other parties?
  - Do you select which curated dataset release or version to use for a specific training run?
  - Are you responsible for the model's training configuration and hyperparameters?
  - Do you evaluate model performance after training it?
```

```yaml
id: personaSyntheticModelHostingProvider
title: Synthetic Model Hosting Provider
description:
  - >
    Actors that operate the runtime infrastructure that serves a trained
    model's predictions to applications or end users. This persona covers
    runtime serving of an already-trained model, not the preparation of
    training data or the training process itself.
responsibilities:
  - Runtime inference endpoint operation and availability
  - Serving-time request authentication and rate limiting
  - Deployed model artifact integrity verification at load time
identificationQuestions:
  - Do you operate the runtime service that serves a trained model's predictions to applications or end users?
  - Do you manage inference endpoints, load balancing, or request routing for a deployed model?
  - Do you monitor model-serving infrastructure for uptime, latency, or capacity?
  - Does your organization scale model-serving infrastructure up or down based on inference traffic?
  - Are you responsible for the runtime environment's security configuration during model inference?
  - Do you fine-tune the models you serve on customer data before deploying them to your inference endpoints?
```
