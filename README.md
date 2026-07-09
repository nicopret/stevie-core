# Stevie

Stevie is an event-driven media orchestration platform designed to provide a unified interface for televisions, streaming services, media devices, and smart home integrations.

Rather than individual clients communicating directly with hardware or online services, every interaction flows through Stevie's kernel, event bus, and telemetry pipeline.

---

# Current Architecture

```
                     Stevie Kernel
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
 Configuration         Event Bus         Telemetry
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                     Device Services
                           │
                    Samsung TV Service
```

## Design Principles

* Event-driven architecture
* Fully asynchronous (`asyncio`)
* Service/component based
* Transport independent
* Extensible through drivers and integrations
* Strongly typed identifiers using `StrEnum`
* Structured telemetry pipeline
* Designed for Home Assistant, mobile applications, CAN bus and custom hardware

---

# Current Components

## Configuration

Loads application settings from `.env`.

Configuration is registered with the kernel as a component and accessed by services when required.

---

## Event Bus

The Event Bus is Stevie's internal messaging backbone.

Responsibilities:

* Publish events
* Subscribe to events
* Wildcard subscriptions
* Asynchronous dispatch
* Synchronous dispatch
* Handler isolation
* Telemetry integration

---

## Telemetry

Telemetry is responsible for operational reporting throughout Stevie.

Services never write directly to the logger. Instead they emit telemetry messages.

Current outputs:

* Local structured JSON logging (Structlog)

Future outputs:

* Grafana / Loki
* Mobile notifications
* Home Assistant notifications
* Smart Mirror
* CAN Bus displays
* Email / SMS alerts

Telemetry messages contain:

* Message identifier
* Level
* Category
* Description
* Grafana key
* Context

---

## Samsung TV

Current capabilities:

* Secure WebSocket connection
* Token management
* Remote key presses
* Channel selection
* Event publishing
* Telemetry integration

---

# Identifiers

Stevie avoids magic strings by using strongly typed identifiers.

Current identifier groups:

```
identifiers/

    services.py
    topics.py
    telemetry.py
```

These define:

* Service names
* Event topics
* Telemetry levels
* Telemetry categories
* Telemetry messages

---

# Development

## Requirements

* Python 3.13+
* uv
* Raspberry Pi OS Lite (recommended)

Install dependencies:

```bash
uv sync
```

Create your environment file:

```bash
cp .env.example .env
```

Run Stevie:

```bash
uv run python -m stevie.main
```

---

# Sandbox

Experimental code and architecture validation live in:

```
sandbox/
```

Nothing inside the sandbox is considered production code.

Use the sandbox to test:

* Event Bus
* Samsung TV integration
* Telemetry
* Future drivers

---

# Current Features

* ✅ Kernel
* ✅ Component Registry
* ✅ Service Lifecycle
* ✅ Event Bus
* ✅ Configuration Component
* ✅ Samsung TV Driver
* ✅ Structured Telemetry
* ✅ Strongly Typed Identifiers

---

# Planned Features

## Core

* FastAPI server
* WebSocket API
* Scheduler
* Device abstraction layer
* Plugin system

## Media

* Samsung TV
* EE TV Box
* Netflix
* Prime Video
* BBC iPlayer
* XMLTV support

## Clients

* Home Assistant integration
* Mobile application
* Interactive Pi Zero remote
* Smart Mirror
* CAN Bus integration

## Infrastructure

* SQLite
* DynamoDB (optional cloud backend)
* Grafana dashboards
* Loki logging
* GitHub Actions CI/CD

---

# Philosophy

Stevie is designed around one central idea:

> Every client communicates with Stevie.
>
> Stevie communicates with the devices.

This allows multiple front-ends—including Home Assistant, mobile applications, dashboards, CAN bus devices, and dedicated hardware—to share the same services, event model, and automation logic without duplicating functionality.
