# ADR-016: Research templates (saved presets)

Status: Accepted  
Date: 2026-08-21

## Context

New Research exposed a disabled “Save as template” control. After planner/performance/infra closure, the highest-value MODE A product gap was a reusable local preset — not billing, orgs, or fake RBAC.

## Decision

Implement local `research_templates` (name, goal, mode, output language) with CRUD API and New Research UI (EN/IT). Templates are workspace-local, not shared, and do not authorize runs by themselves. Starting research still creates a `ResearchRun` through the existing execute path.

## Security

MODE A: no multi-tenant isolation. Template text is rendered as React text (no HTML). Goal length is bounded. Templates cannot change budgets, tools, or HITL policy.
