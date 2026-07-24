# LocalAI Project Overview

## Purpose

`UsingSession/localai` is a reusable personal AI infrastructure foundation.

It provides a stable local stack of services, integrations, conventions, and
development patterns that can be reused across multiple personal projects.

The main goal is to avoid rebuilding the same AI infrastructure for every new
project.

```text
localai = reusable AI foundation
specific project = workflows, prompts, configuration, and data
```

A future project should be able to connect to `localai` and reuse its chat,
automation, prompt-management, storage, retrieval, and model-access
capabilities.

## Core Philosophy

`localai` is not a single end-user application.

It is a shared platform that supports different kinds of applications and
experiments, including:

- coding assistants;
- research workflows;
- knowledge bases;
- image-prompt workflows;
- personal productivity tools;
- local model integrations;
- automation workflows;
- future AI experiments.

The platform should become more reusable, flexible, reliable, and
well-documented over time.

When a new project requires a capability, that capability should be added to
`localai` only when it can be implemented as a reusable platform feature.

## Project Scope

`localai` is responsible for reusable infrastructure and orchestration,
including:

- Docker Compose configuration;
- service networking;
- shared environment conventions;
- Open WebUI integration;
- n8n integration;
- PostgreSQL infrastructure;
- Qdrant infrastructure;
- SearXNG integration;
- Prompt Admin integration;
- local model backend integration;
- reusable workflow patterns;
- backup and restore tooling;
- developer scripts;
- local tray and control utilities;
- pinned external service versions.

The platform may provide reusable contracts, templates, and conventions for
project-specific consumers.

## Reusable vs Project-Specific Capabilities

A capability belongs in `localai` when it can support multiple future projects
without depending on one domain.

Examples:

- generic workflow routing;
- prompt retrieval through a stable API;
- shared model-backend configuration;
- reusable backup scripts;
- common request normalization;
- generic RAG infrastructure;
- shared development tooling.

A capability should remain project-specific when it depends on one use case,
domain, dataset, or output format.

Examples:

- Danbooru-specific retrieval logic;
- image-generation prompt rules;
- one project's custom n8n workflow;
- project-specific prompt records;
- project-specific Qdrant collections;
- domain-specific datasets;
- application-specific configuration.

Project-specific functionality may use `localai`, but it should not redefine the
platform's generic purpose.

## Repository Model

The ecosystem currently uses two primary repositories.

### `UsingSession/localai`

Repository:

```text
https://github.com/UsingSession/localai
```

This repository owns the infrastructure and orchestration layer.

### `UsingSession/prompt-admin`

Repository:

```text
https://github.com/UsingSession/prompt-admin
```

This repository owns the standalone Prompt Admin application.

Prompt Admin is a generic prompt-management service. It is not a
`localai`-specific image-generation application.

## Primary Use Cases

`localai` should make it possible to:

1. run a local AI stack with predictable service boundaries;
2. connect Open WebUI to reusable n8n workflows;
3. use local or remote model backends through stable integrations;
4. manage prompts, hooks, and families outside workflow definitions;
5. store structured application state in PostgreSQL;
6. store vector and RAG data in Qdrant;
7. add optional web retrieval through SearXNG;
8. reuse the same infrastructure across independent personal projects;
9. develop infrastructure services independently when necessary;
10. back up and restore critical local state.

## Design Principles

### Reusability

Prefer platform capabilities that can support more than one project.

### Clear Responsibility Boundaries

Each service, repository, and workflow layer should have a narrow and explicit
responsibility.

### Loose Coupling

Project-specific logic should depend on stable platform contracts rather than
internal implementation details.

### Reproducibility

Use pinned service and application versions where practical.

### Local-First Operation

The platform should support local execution and local model backends without
requiring cloud services for its core operation.

### Explicit State Ownership

Each type of state should have one clear source of truth.

### Incremental Evolution

Prefer small, reviewable improvements over large speculative redesigns.

### Operational Safety

Backups, secrets, migrations, and restore procedures should be treated as
first-class concerns.

### Verifiable Documentation

Documentation should describe confirmed architecture and supported behavior,
not temporary assumptions.

## Non-Goals

`localai` is not intended to:

- contain every project's business logic;
- ship domain-specific default prompts;
- own project-specific datasets;
- become a monolithic application;
- force every workflow into one implementation;
- replace the source repositories as the source of truth for code;
- expose local administrative services publicly by default;
- hide service boundaries behind unnecessary abstractions;
- depend on one model provider or one workflow domain.

## Main Decision Rule

```text
If a capability is reusable across future projects, implement it generically
in localai.

If it belongs to one project, keep it in that project's workflows, prompts,
configuration, datasets, or documentation.
```
