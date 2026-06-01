"""Agent Blueprint Catalog — scalable registry of 120+ agent blueprints.

This module is PURE DATA. It defines what agents COULD do without
executing anything. No network, no file writes, no LLM calls, no env reads.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


# ── Blueprint dataclass ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentBlueprint:
    """One agent blueprint — a declarative description of what an agent can do.

    A blueprint is a PROPOSAL, not an execution. Instantiation requires
    an explicit decisicion from the selector/executor layer.
    """

    id: str
    name: str
    category: str
    purpose: str
    activation_keywords: tuple[str, ...] = ()
    risk_level: str = "low"
    default_enabled: bool = True
    requires_approval: bool = False
    estimated_cost_level: str = "low"
    tools_allowed: tuple[str, ...] = ()


# ── Risk helpers ─────────────────────────────────────────────────────────────────────


def _high(level: str) -> bool:
    """Return True if the risk level requires user approval."""
    return level in ("high", "critical")


def _approval_required(risk: str) -> bool:
    """Determine if a blueprint requires user approval based on risk level."""
    return risk in ("high", "critical")


# ── Catalog builder ──────────────────────────────────────────────────────────────────


def _build_catalog() -> list[AgentBlueprint]:
    """Build the complete blueprint catalog.

    Pure function. No side effects. All data is static and deterministic.
    """
    blueprints: list[AgentBlueprint] = []

    # ════════════════════════════════════════════════════════════════════════════════
    # category: code (14)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="code.refactor", name="Code Refactor Agent",
        category="code", risk_level="medium", requires_approval=False,
        estimated_cost_level="medium",
        purpose="Propose and apply code refactoring to improve structure without changing behavior.",
        activation_keywords=("refactor", "restructure", "reorganize", "clean up"),
        tools_allowed=("read", "edit", "glob", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.formatter", name="Code Formatter Agent",
        category="code", risk_level="low",
        purpose="Apply code formatting (ruff, black, prettier) according to project standards.",
        activation_keywords=("format", "lint", "style", "prettify"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.linter", name="Lint Fixer Agent",
        category="code", risk_level="low",
        purpose="Analyze and fix lint warnings and errors across the codebase.",
        activation_keywords=("lint", "ruff", "flake8", "pylint"),
        tools_allowed=("read", "edit", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.type_checker", name="Type Checker Agent",
        category="code", risk_level="low",
        purpose="Add or fix type annotations to improve static type safety.",
        activation_keywords=("type", "mypy", "annotation", "typing"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.importer", name="Import Optimizer Agent",
        category="code", risk_level="low",
        purpose="Optimize and organize imports (remove unused, sort, merge).",
        activation_keywords=("import", "unused import", "organize imports"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.docstring", name="Docstring Generator Agent",
        category="code", risk_level="low",
        purpose="Generate or improve docstrings for functions, classes, and modules.",
        activation_keywords=("docstring", "documentation", "doc", "comment"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.dead_code", name="Dead Code Remover Agent",
        category="code", risk_level="medium", requires_approval=False,
        estimated_cost_level="medium",
        purpose="Detect and remove dead code, unused variables, and unreachable paths.",
        activation_keywords=("dead code", "unused", "remove", "cleanup"),
        tools_allowed=("read", "edit", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.deprecation", name="Deprecation Migrator Agent",
        category="code", risk_level="medium", requires_approval=False,
        estimated_cost_level="medium",
        purpose="Replace deprecated API calls with their modern equivalents.",
        activation_keywords=("deprecated", "migrate", "upgrade", "legacy"),
        tools_allowed=("read", "edit", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.error_handling", name="Error Handling Agent",
        category="code", risk_level="low",
        purpose="Add or improve error handling, try/except blocks, and fallback logic.",
        activation_keywords=("error", "exception", "try", "catch", "fallback"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.logging", name="Logging Agent",
        category="code", risk_level="low",
        purpose="Add structured logging to critical paths and error branches.",
        activation_keywords=("log", "logging", "debug", "trace"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.performance", name="Performance Optimizer Agent",
        category="code", risk_level="medium", requires_approval=False,
        estimated_cost_level="medium",
        purpose="Identify and apply performance optimizations (algorithm, cache, I/O).",
        activation_keywords=("performance", "slow", "optimize", "bottleneck", "latency"),
        tools_allowed=("read", "edit", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.concurrency", name="Concurrency Agent",
        category="code", risk_level="high", requires_approval=True,
        estimated_cost_level="high",
        purpose="Introduce or fix async/threading/parallelism patterns safely.",
        activation_keywords=("async", "thread", "concurrent", "parallel", "lock"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.api_client", name="API Client Agent",
        category="code", risk_level="medium", requires_approval=False,
        estimated_cost_level="medium",
        purpose="Generate or update API client code from OpenAPI/specs.",
        activation_keywords=("api", "client", "endpoint", "openapi", "swagger"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="code.migration", name="Code Migration Agent",
        category="code", risk_level="high", requires_approval=True,
        estimated_cost_level="high",
        purpose="Automate large-scale code migrations across the codebase.",
        activation_keywords=("migration", "transform", "rewrite", "convert"),
        tools_allowed=("read", "edit", "glob", "grep"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: test (11)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="test.unit", name="Unit Test Agent",
        category="test", risk_level="low",
        purpose="Generate unit tests for functions and classes using pytest.",
        activation_keywords=("unit test", "pytest", "test coverage", "test case"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.integration", name="Integration Test Agent",
        category="test", risk_level="low",
        purpose="Design and write integration tests across module boundaries.",
        activation_keywords=("integration", "end to end", "e2e"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.fixture", name="Test Fixture Agent",
        category="test", risk_level="low",
        purpose="Create reusable test fixtures, factories, and mock setups.",
        activation_keywords=("fixture", "mock", "factory", "stub"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.coverage", name="Coverage Gap Analyzer Agent",
        category="test", risk_level="low",
        purpose="Analyze test coverage reports and recommend new tests for uncovered paths.",
        activation_keywords=("coverage", "uncovered", "gap", "codecov"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.property", name="Property-Based Test Agent",
        category="test", risk_level="low",
        purpose="Design property-based (hypothesis) tests for edge cases.",
        activation_keywords=("property", "hypothesis", "fuzz", "edge case"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.regression", name="Regression Test Agent",
        category="test", risk_level="low",
        purpose="Capture regression tests from bug reports and fixes.",
        activation_keywords=("regression", "bug fix", "reproduce"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.performance_test", name="Performance Test Agent",
        category="test", risk_level="low",
        purpose="Design benchmarks and load tests for performance-sensitive paths.",
        activation_keywords=("benchmark", "load test", "stress", "perf test"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.snapshot", name="Snapshot Test Agent",
        category="test", risk_level="low",
        purpose="Create or update snapshot/approval tests for deterministic outputs.",
        activation_keywords=("snapshot", "approval", "golden", "expected"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.mutation", name="Mutation Test Agent",
        category="test", risk_level="low",
        purpose="Run mutation testing to evaluate test suite quality.",
        activation_keywords=("mutation", "mutant", "test quality"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.cross_platform", name="Cross-Platform Test Agent",
        category="test", risk_level="low",
        purpose="Ensure tests pass across Python versions and platforms.",
        activation_keywords=("cross platform", "compatibility", "platform", "version"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="test.contract", name="Contract Test Agent",
        category="test", risk_level="low",
        purpose="Verify API contracts and data shapes between services.",
        activation_keywords=("contract", "schema", "validation", "pact"),
        tools_allowed=("read", "edit"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: security (11)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="security.audit", name="Security Audit Agent",
        category="security", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Audit the codebase for security vulnerabilities (injection, XSS, CSRF, etc.).",
        activation_keywords=("audit", "vulnerability", "cve", "injection", "xss", "csrf"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.secrets_scan", name="Secrets Scanner Agent",
        category="security", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="medium",
        purpose="Scan for hardcoded secrets, API keys, tokens, and credentials in the codebase.",
        activation_keywords=("secret", "token", "api key", "credential", "password"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.auth", name="Authentication Reviewer Agent",
        category="security", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Review authentication and authorization logic for flaws.",
        activation_keywords=("auth", "login", "oauth", "jwt", "permission", "rbac"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.dependency", name="Dependency Vulnerabilities Agent",
        category="security", risk_level="medium", default_enabled=False,
        requires_approval=True, estimated_cost_level="medium",
        purpose="Scan dependencies for known CVEs and recommend updates.",
        activation_keywords=("dependency", "cve", "package", "vulnerable", "safety"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.network", name="Network Security Agent",
        category="security", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Review network configurations, port exposure, and firewall rules.",
        activation_keywords=("network", "port", "firewall", "expose", "ingress"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.crypto", name="Cryptography Reviewer Agent",
        category="security", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Review cryptographic implementations (hashing, encryption, signing).",
        activation_keywords=("crypto", "encrypt", "hash", "sign", "tls", "ssl"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.input_validation", name="Input Validation Agent",
        category="security", risk_level="medium",
        requires_approval=True, estimated_cost_level="medium",
        purpose="Audit input validation, sanitization, and parameter parsing.",
        activation_keywords=("input", "sanitize", "validate", "parameter", "injection"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.compliance", name="Compliance Checker Agent",
        category="security", risk_level="medium", default_enabled=False,
        requires_approval=True, estimated_cost_level="medium",
        purpose="Check code for compliance with security standards (OWASP, SOC2, GDPR).",
        activation_keywords=("compliance", "gdpr", "soc2", "owasp", "regulation"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.session", name="Session Management Agent",
        category="security", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="medium",
        purpose="Review session handling, cookie security, and token lifecycle.",
        activation_keywords=("session", "cookie", "token", "jwt", "refresh"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.access_control", name="Access Control Agent",
        category="security", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="medium",
        purpose="Review role-based access control and privilege escalation paths.",
        activation_keywords=("access", "role", "privilege", "permission", "acl"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="security.secure_config", name="Secure Config Agent",
        category="security", risk_level="medium",
        requires_approval=True, estimated_cost_level="medium",
        purpose="Review configuration files for insecure defaults or exposed secrets.",
        activation_keywords=("config", "setting", "configuration", "env", "dotenv"),
        tools_allowed=("read", "grep"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: devops (11)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="devops.deploy", name="Deployment Agent",
        category="devops", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Plan and execute deployments to staging or production environments.",
        activation_keywords=("deploy", "release", "rollout", "ship"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.docker", name="Docker Agent",
        category="devops", risk_level="medium",
        requires_approval=True, estimated_cost_level="medium",
        purpose="Create or optimize Dockerfiles and docker-compose configurations.",
        activation_keywords=("docker", "container", "dockerfile", "compose"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.ci_cd", name="CI/CD Pipeline Agent",
        category="devops", risk_level="medium",
        requires_approval=True, estimated_cost_level="medium",
        purpose="Design and maintain CI/CD pipeline configurations (GitHub Actions, GitLab CI).",
        activation_keywords=("ci", "cd", "pipeline", "github action", "gitlab"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.monitoring", name="Monitoring Agent",
        category="devops", risk_level="low",
        purpose="Set up or update monitoring dashboards, alerts, and metrics.",
        activation_keywords=("monitor", "alert", "metric", "grafana", "prometheus"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.server", name="Server Config Agent",
        category="devops", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Configure server software (systemd, nginx, caddy, supervisor).",
        activation_keywords=("server", "systemd", "nginx", "caddy", "supervisor"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.backup", name="Backup & Recovery Agent",
        category="devops", risk_level="medium",
        requires_approval=True, estimated_cost_level="medium",
        purpose="Design and verify backup and disaster recovery procedures.",
        activation_keywords=("backup", "recovery", "restore", "disaster"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.scaling", name="Scaling Agent",
        category="devops", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Analyze and recommend scaling strategies (horizontal, vertical, auto-scaling).",
        activation_keywords=("scale", "auto scale", "load", "capacity", "throughput"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.kubernetes", name="Kubernetes Agent",
        category="devops", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Create or update Kubernetes manifests and Helm charts.",
        activation_keywords=("kubernetes", "k8s", "helm", "pod", "deployment"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.dns", name="DNS & Domain Agent",
        category="devops", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="medium",
        purpose="Manage DNS records, domain configuration, and SSL certificates.",
        activation_keywords=("dns", "domain", "ssl", "certificate", "certbot"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.db_migration", name="DB Migration Agent",
        category="devops", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Design and review database schema migrations and rollback plans.",
        activation_keywords=("migration", "database", "schema", "alembic", "rollback"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="devops.rollback", name="Rollback Agent",
        category="devops", risk_level="high", default_enabled=False,
        requires_approval=True, estimated_cost_level="high",
        purpose="Plan and execute safe rollbacks of deployments or migrations.",
        activation_keywords=("rollback", "revert", "undo", "restore"),
        tools_allowed=("read", "bash"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: research (10)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="research.library", name="Library Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research third-party libraries for a given task and compare alternatives.",
        activation_keywords=("library", "package", "dependency", "pypi", "npm"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.pattern", name="Pattern Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research design patterns and idiomatic solutions for a problem.",
        activation_keywords=("pattern", "best practice", "idiom", "convention"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.github", name="GitHub Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Search GitHub repos for reference implementations and examples.",
        activation_keywords=("github", "repo", "reference", "example", "source code"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.tech_stack", name="Tech Stack Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research and compare technology stacks, frameworks, and tools.",
        activation_keywords=("framework", "technology", "stack", "compare", "vs"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.protocol", name="Protocol Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research communication protocols and data interchange formats.",
        activation_keywords=("protocol", "format", "serialization", "rpc", "rest"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.algorithm", name="Algorithm Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research algorithms, complexity analysis, and data structures.",
        activation_keywords=("algorithm", "complexity", "data structure", "sort", "search"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.standard", name="Standards Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research industry standards, RFCs, and specification documents.",
        activation_keywords=("standard", "rfc", "specification", "spec"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.security_research", name="Security Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research security advisories, CVEs, and secure implementation guides.",
        activation_keywords=("cve", "advisory", "security research", "exploit"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.competitor", name="Competitor Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research competitor products, features, and positioning.",
        activation_keywords=("competitor", "market", "landscape", "analysis"),
        tools_allowed=("web_search", "web_fetch"),
    ))
    blueprints.append(AgentBlueprint(
        id="research.api_docs", name="API Documentation Research Agent",
        category="research", risk_level="low", default_enabled=False,
        requires_approval=False, estimated_cost_level="medium",
        purpose="Research API documentation and usage patterns for integration work.",
        activation_keywords=("api doc", "sdk", "integration", "endpoint"),
        tools_allowed=("web_search", "web_fetch"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: product (10)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="product.feature_spec", name="Feature Spec Agent",
        category="product", risk_level="low",
        purpose="Write detailed feature specifications and acceptance criteria.",
        activation_keywords=("spec", "feature", "requirement", "acceptance"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="product.user_story", name="User Story Agent",
        category="product", risk_level="low",
        purpose="Translate requirements into structured user stories.",
        activation_keywords=("user story", "story", "epic", "backlog"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="product.prd", name="Product Requirements Agent",
        category="product", risk_level="low",
        purpose="Draft product requirements documents with clear scope and goals.",
        activation_keywords=("prd", "requirements", "product", "scope"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="product.roadmap", name="Roadmap Agent",
        category="product", risk_level="low",
        purpose="Plan and visualize product roadmaps with milestones.",
        activation_keywords=("roadmap", "milestone", "timeline", "plan"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="product.changelog", name="Changelog Agent",
        category="product", risk_level="low",
        purpose="Generate changelogs from git history and release notes.",
        activation_keywords=("changelog", "release notes", "version"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="product.priority", name="Priority Agent",
        category="product", risk_level="low",
        purpose="Analyze and recommend task prioritization using impact-effort matrices.",
        activation_keywords=("priority", "impact", "effort", "triage", "ice"),
        tools_allowed=("read",),
    ))
    blueprints.append(AgentBlueprint(
        id="product.a_b_test", name="A/B Test Agent",
        category="product", risk_level="low",
        purpose="Design A/B testing experiments and analyze results.",
        activation_keywords=("a/b test", "experiment", "split test", "variant"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="product.feedback", name="Feedback Analyzer Agent",
        category="product", risk_level="low",
        purpose="Analyze user feedback and suggest product improvements.",
        activation_keywords=("feedback", "survey", "user input", "nps"),
        tools_allowed=("read",),
    ))
    blueprints.append(AgentBlueprint(
        id="product.metrics", name="Product Metrics Agent",
        category="product", risk_level="low",
        purpose="Define and track product KPIs and business metrics.",
        activation_keywords=("metric", "kpi", "dashboard", "analytics"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="product.goals", name="OKR Agent",
        category="product", risk_level="low",
        purpose="Draft and track OKRs aligned with product strategy.",
        activation_keywords=("okr", "objective", "key result", "goal"),
        tools_allowed=("read", "edit"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: docs (10)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="docs.readme", name="README Agent",
        category="docs", risk_level="low",
        purpose="Generate or improve project README files.",
        activation_keywords=("readme", "readme.md"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.api", name="API Documentation Agent",
        category="docs", risk_level="low",
        purpose="Generate API reference documentation from code.",
        activation_keywords=("api doc", "reference", "endpoint doc"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.setup", name="Setup Guide Agent",
        category="docs", risk_level="low",
        purpose="Write setup, installation, and configuration guides.",
        activation_keywords=("setup", "install", "getting started", "guide"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.contributing", name="Contributing Guide Agent",
        category="docs", risk_level="low",
        purpose="Create or update CONTRIBUTING guides for open-source projects.",
        activation_keywords=("contributing", "contribute", "guidelines", "pr"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.architecture", name="Architecture Docs Agent",
        category="docs", risk_level="low",
        purpose="Document architectural decisions (ADRs) and system design.",
        activation_keywords=("architecture", "adr", "design doc", "system"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.tutorial", name="Tutorial Builder Agent",
        category="docs", risk_level="low",
        purpose="Create step-by-step tutorials and walkthroughs.",
        activation_keywords=("tutorial", "walkthrough", "how to", "example"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.faq", name="FAQ Agent",
        category="docs", risk_level="low",
        purpose="Generate and maintain FAQ documentation from common questions.",
        activation_keywords=("faq", "question", "common issue", "troubleshoot"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.release", name="Release Notes Agent",
        category="docs", risk_level="low",
        purpose="Draft release notes from git log and changelog data.",
        activation_keywords=("release notes", "release", "version notes"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.style_guide", name="Style Guide Agent",
        category="docs", risk_level="low",
        purpose="Create or maintain documentation style guides.",
        activation_keywords=("style guide", "voice", "tone", "writing"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="docs.schema", name="Schema Documentation Agent",
        category="docs", risk_level="low",
        purpose="Document database schemas, data models, and entity relationships.",
        activation_keywords=("schema", "erd", "data model", "entity"),
        tools_allowed=("read", "edit"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: data (10)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="data.validation", name="Data Validation Agent",
        category="data", risk_level="low",
        purpose="Validate data against schemas, constraints, and business rules.",
        activation_keywords=("validate", "data quality", "clean", "integrity"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.transformation", name="Data Transformation Agent",
        category="data", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Design and apply data transformations, ETL pipelines, and normalization.",
        activation_keywords=("transform", "etl", "normalize", "convert", "parse"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.migration", name="Data Migration Agent",
        category="data", risk_level="high",
        requires_approval=True, estimated_cost_level="high",
        purpose="Plan and execute data migrations between stores or formats.",
        activation_keywords=("data migration", "transfer", "export", "import"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.anonymization", name="Data Anonymization Agent",
        category="data", risk_level="high",
        requires_approval=True, estimated_cost_level="medium",
        purpose="Anonymize or mask sensitive data for testing and analysis.",
        activation_keywords=("anonymize", "mask", "redact", "pii", "gdpr"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.schema_design", name="Schema Design Agent",
        category="data", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Design database schemas, indexes, and constraints.",
        activation_keywords=("schema", "table", "index", "constraint", "ddl"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.query_optimizer", name="Query Optimizer Agent",
        category="data", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Analyze and optimize database queries for performance.",
        activation_keywords=("query", "sql", "slow", "optimize", "explain"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.report", name="Report Generator Agent",
        category="data", risk_level="low",
        purpose="Generate data reports, summaries, and aggregations.",
        activation_keywords=("report", "summary", "aggregation", "dashboard"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.pipeline", name="Data Pipeline Agent",
        category="data", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Design and maintain data processing pipelines.",
        activation_keywords=("pipeline", "stream", "batch", "processing"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.cache", name="Caching Strategy Agent",
        category="data", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Design caching strategies (Redis, Memcached, CDN) for data access.",
        activation_keywords=("cache", "redis", "memcached", "ttl", "invalidate"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="data.warehouse", name="Data Warehouse Agent",
        category="data", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Design data warehouse schemas (star, snowflake) and ETL strategies.",
        activation_keywords=("warehouse", "olap", "star schema", "snowflake"),
        tools_allowed=("read", "edit"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: ux (10)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="ux.accessibility", name="Accessibility Agent",
        category="ux", risk_level="low",
        purpose="Audit and improve UI accessibility (a11y, ARIA, contrast).",
        activation_keywords=("accessibility", "a11y", "aria", "contrast", "screen reader"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.usability", name="Usability Agent",
        category="ux", risk_level="low",
        purpose="Analyze and suggest UI/UX improvements for usability.",
        activation_keywords=("usability", "ux", "user experience", "ease of use"),
        tools_allowed=("read",),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.wireframe", name="Wireframe Agent",
        category="ux", risk_level="low",
        purpose="Generate wireframe descriptions and layout suggestions.",
        activation_keywords=("wireframe", "layout", "mockup", "prototype"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.design_system", name="Design System Agent",
        category="ux", risk_level="low",
        purpose="Document and maintain design system components and tokens.",
        activation_keywords=("design system", "component", "token", "ui kit"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.responsive", name="Responsive Design Agent",
        category="ux", risk_level="low",
        purpose="Audit and fix responsive layout issues across screen sizes.",
        activation_keywords=("responsive", "mobile", "breakpoint", "viewport"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.animation", name="Animation Agent",
        category="ux", risk_level="low",
        purpose="Design UI animation specs and transitions for smooth interactions.",
        activation_keywords=("animation", "transition", "motion", "css animation"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.error_messages", name="Error Message Agent",
        category="ux", risk_level="low",
        purpose="Improve error messages, empty states, and user-facing feedback.",
        activation_keywords=("error message", "empty state", "toast", "notification"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.onboarding", name="Onboarding Agent",
        category="ux", risk_level="low",
        purpose="Design onboarding flows and first-run experiences.",
        activation_keywords=("onboarding", "first run", "welcome", "tutorial"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.localization", name="Localization Agent",
        category="ux", risk_level="low",
        purpose="Prepare UI for i18n/l10n — extract strings, manage translations.",
        activation_keywords=("localization", "i18n", "translation", "locale"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="ux.loading", name="Loading UX Agent",
        category="ux", risk_level="low",
        purpose="Design loading states, skeletons, and progress indicators.",
        activation_keywords=("loading", "skeleton", "spinner", "progress", "placeholder"),
        tools_allowed=("read", "edit"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: business (10)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="business.proposal", name="Business Proposal Agent",
        category="business", risk_level="low",
        purpose="Draft business proposals, pitches, and investment memos.",
        activation_keywords=("proposal", "pitch", "business", "investment"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.plan", name="Business Plan Agent",
        category="business", risk_level="low",
        purpose="Create structured business plans with financial projections.",
        activation_keywords=("business plan", "strategy", "projection"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.cost", name="Cost Analysis Agent",
        category="business", risk_level="low",
        purpose="Analyze costs, ROI, and total cost of ownership.",
        activation_keywords=("cost", "roi", "tco", "budget", "pricing"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.market", name="Market Analysis Agent",
        category="business", risk_level="low",
        purpose="Analyze market trends, size, and growth opportunities.",
        activation_keywords=("market", "tam", "sam", "som", "trend"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.risk", name="Risk Analysis Agent",
        category="business", risk_level="low",
        purpose="Identify and assess business risks and mitigation strategies.",
        activation_keywords=("risk", "mitigation", "swot", "threat"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.kpi", name="KPI Dashboard Agent",
        category="business", risk_level="low",
        purpose="Design KPI dashboards and business performance metrics.",
        activation_keywords=("kpi", "dashboard", "metric", "performance"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.report", name="Business Report Agent",
        category="business", risk_level="low",
        purpose="Generate executive summaries, status reports, and board decks.",
        activation_keywords=("report", "executive summary", "board", "quarterly"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.competitive", name="Competitive Analysis Agent",
        category="business", risk_level="low",
        purpose="Analyze competitive landscape, positioning, and differentiation.",
        activation_keywords=("competitive", "competitor", "positioning", "differentiation"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.pricing", name="Pricing Strategy Agent",
        category="business", risk_level="low",
        purpose="Model pricing strategies, tiers, and monetization approaches.",
        activation_keywords=("pricing", "monetization", "tier", "subscription"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="business.timeline", name="Project Timeline Agent",
        category="business", risk_level="low",
        purpose="Plan project timelines, milestones, and resource allocation.",
        activation_keywords=("timeline", "gantt", "milestone", "schedule"),
        tools_allowed=("read", "edit"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: seo (9)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="seo.audit", name="SEO Audit Agent",
        category="seo", risk_level="low",
        purpose="Audit website SEO — meta tags, headings, structure, performance.",
        activation_keywords=("seo", "search", "meta", "rank", "google"),
        tools_allowed=("read", "web_search"),
    ))
    blueprints.append(AgentBlueprint(
        id="seo.keyword", name="Keyword Research Agent",
        category="seo", risk_level="low",
        purpose="Research keywords, search volume, and competition analysis.",
        activation_keywords=("keyword", "search volume", "long tail"),
        tools_allowed=("web_search",),
    ))
    blueprints.append(AgentBlueprint(
        id="seo.content", name="SEO Content Agent",
        category="seo", risk_level="low",
        purpose="Optimize written content for search engines while maintaining readability.",
        activation_keywords=("content", "optimize", "readability", "seo content"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="seo.link", name="Link Building Agent",
        category="seo", risk_level="low",
        purpose="Suggest internal and external link strategies for SEO.",
        activation_keywords=("link", "backlink", "internal link"),
        tools_allowed=("read",),
    ))
    blueprints.append(AgentBlueprint(
        id="seo.technical", name="Technical SEO Agent",
        category="seo", risk_level="low",
        purpose="Review technical SEO — sitemaps, robots.txt, canonical URLs, structured data.",
        activation_keywords=("sitemap", "robots", "canonical", "structured data", "schema.org"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="seo.meta", name="Meta Tag Agent",
        category="seo", risk_level="low",
        purpose="Generate and optimize meta titles, descriptions, and Open Graph tags.",
        activation_keywords=("meta tag", "title", "description", "og", "open graph"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="seo.performance", name="SEO Performance Agent",
        category="seo", risk_level="low",
        purpose="Optimize page speed, Core Web Vitals, and mobile performance.",
        activation_keywords=("core web vital", "page speed", "lcp", "cls", "fid"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="seo.redirect", name="Redirect Agent",
        category="seo", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Plan and implement URL redirects to preserve SEO equity.",
        activation_keywords=("redirect", "301", "302", "url mapping"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="seo.analytics", name="SEO Analytics Agent",
        category="seo", risk_level="low",
        purpose="Analyze search console data and suggest SEO improvements.",
        activation_keywords=("analytics", "search console", "traffic", "impression"),
        tools_allowed=("read",),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: qa (9)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="qa.test_plan", name="Test Plan Agent",
        category="qa", risk_level="low",
        purpose="Design comprehensive test plans covering all test levels.",
        activation_keywords=("test plan", "test strategy", "qa plan"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="qa.bug_triage", name="Bug Triage Agent",
        category="qa", risk_level="low",
        purpose="Triage incoming bug reports — classify, prioritize, route.",
        activation_keywords=("triage", "bug", "issue", "priority", "severity"),
        tools_allowed=("read",),
    ))
    blueprints.append(AgentBlueprint(
        id="qa.regression", name="Regression Tester Agent",
        category="qa", risk_level="low",
        purpose="Identify regression risk areas and suggest targeted test suites.",
        activation_keywords=("regression", "retest", "impact", "affected"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="qa.exploratory", name="Exploratory Testing Agent",
        category="qa", risk_level="low",
        purpose="Guide exploratory testing sessions with heuristics and checklists.",
        activation_keywords=("exploratory", "heuristic", "checklist", "session"),
        tools_allowed=("read",),
    ))
    blueprints.append(AgentBlueprint(
        id="qa.uat", name="UAT Agent",
        category="qa", risk_level="low",
        purpose="Prepare user acceptance test scenarios and sign-off criteria.",
        activation_keywords=("uat", "user acceptance", "sign off", "acceptance"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="qa.smoke", name="Smoke Test Agent",
        category="qa", risk_level="low",
        purpose="Define smoke test suites for quick build verification.",
        activation_keywords=("smoke", "sanity", "build verification"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="qa.load", name="Load Test Agent",
        category="qa", risk_level="low",
        purpose="Design load and stress test scenarios with realistic user patterns.",
        activation_keywords=("load", "stress", "concurrency", "throughput"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="qa.compatibility", name="Compatibility Tester Agent",
        category="qa", risk_level="low",
        purpose="Test across browsers, devices, OS versions, and configurations.",
        activation_keywords=("compatibility", "browser", "cross browser", "device"),
        tools_allowed=("read", "bash"),
    ))
    blueprints.append(AgentBlueprint(
        id="qa.security_test", name="Security Test Agent",
        category="qa", risk_level="medium",
        requires_approval=True, estimated_cost_level="medium",
        purpose="Design security test cases (penetration, fuzzing, boundary).",
        activation_keywords=("penetration", "fuzz", "boundary", "security test"),
        tools_allowed=("read",),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: architecture (8)
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="architecture.design", name="System Design Agent",
        category="architecture", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Propose system designs, component diagrams, and data flow.",
        activation_keywords=("system design", "architecture", "component", "diagram"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="architecture.review", name="Architecture Review Agent",
        category="architecture", risk_level="low",
        purpose="Review existing architecture for consistency, scalability, and trade-offs.",
        activation_keywords=("review", "audit", "architecture review"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="architecture.adr", name="ADR Agent",
        category="architecture", risk_level="low",
        purpose="Document architecture decisions with context and consequences.",
        activation_keywords=("adr", "decision", "decision record"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="architecture.module", name="Module Design Agent",
        category="architecture", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Design module boundaries, interfaces, and dependency graphs.",
        activation_keywords=("module", "interface", "dependency", "boundary"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="architecture.microservices", name="Microservices Agent",
        category="architecture", risk_level="high",
        requires_approval=True, estimated_cost_level="high",
        purpose="Design microservice boundaries, communication patterns, and data ownership.",
        activation_keywords=("microservice", "service", "bounded context", "domain"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="architecture.event", name="Event-Driven Architecture Agent",
        category="architecture", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Design event-driven patterns — topics, subscriptions, dead-letter queues.",
        activation_keywords=("event", "message", "queue", "pub/sub", "kafka"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="architecture.security_arch", name="Security Architecture Agent",
        category="architecture", risk_level="high",
        requires_approval=True, estimated_cost_level="high",
        purpose="Design security architecture — threat models, trust boundaries, defense-in-depth.",
        activation_keywords=("threat model", "trust boundary", "security architecture"),
        tools_allowed=("read", "edit"),
    ))
    blueprints.append(AgentBlueprint(
        id="architecture.scalability", name="Scalability Architecture Agent",
        category="architecture", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Design for scale — partitioning, replication, caching, load balancing.",
        activation_keywords=("scalability", "partition", "replica", "load balance"),
        tools_allowed=("read", "edit"),
    ))

    # ════════════════════════════════════════════════════════════════════════════════
    # category: general (3) — catch-all cross-cutting
    # ════════════════════════════════════════════════════════════════════════════════
    blueprints.append(AgentBlueprint(
        id="general.task_executor", name="General Task Executor",
        category="general", risk_level="medium",
        requires_approval=False, estimated_cost_level="medium",
        purpose="Execute general-purpose development tasks not covered by specific blueprints.",
        activation_keywords=("task", "execute", "implement", "build"),
        tools_allowed=("read", "edit", "bash", "grep", "glob"),
    ))
    blueprints.append(AgentBlueprint(
        id="general.debugger", name="Debug Assistant Agent",
        category="general", risk_level="low",
        purpose="Analyze runtime errors, stack traces, and debug logs to identify root causes.",
        activation_keywords=("debug", "error", "crash", "traceback", "stack"),
        tools_allowed=("read", "grep"),
    ))
    blueprints.append(AgentBlueprint(
        id="general.reviewer", name="Code Reviewer Agent",
        category="general", risk_level="low",
        purpose="Review code changes for correctness, style, and potential issues.",
        activation_keywords=("review", "pr", "pull request", "diff"),
        tools_allowed=("read", "grep"),
    ))

    return blueprints


# ── Cached catalog ──────────────────────────────────────────────────────────────────


_CATALOG: list[AgentBlueprint] | None = None


def get_agent_blueprint_catalog() -> list[AgentBlueprint]:
    """Return the full blueprint catalog.

    Returns a defensive copy so callers cannot mutate the cached list.
    """
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = _build_catalog()
    return list(_CATALOG)


def get_blueprint_count() -> int:
    """Return the total number of blueprints in the catalog."""
    return len(get_agent_blueprint_catalog())


# ── Query functions ─────────────────────────────────────────────────────────────────


def list_blueprints(category: str | None = None) -> list[AgentBlueprint]:
    """Return blueprints, optionally filtered by category."""
    catalog = get_agent_blueprint_catalog()
    if category is None:
        return list(catalog)
    return [b for b in catalog if b.category == category]


def get_categories() -> list[str]:
    """Return sorted list of all blueprint categories."""
    cats: set[str] = set()
    for b in get_agent_blueprint_catalog():
        cats.add(b.category)
    return sorted(cats)


def find_blueprint(agent_id: str) -> AgentBlueprint | None:
    """Find a blueprint by its unique id."""
    for b in get_agent_blueprint_catalog():
        if b.id == agent_id:
            return b
    return None


def search_blueprints(task_text: str, max_results: int = 10) -> list[AgentBlueprint]:
    """Search blueprints by matching keywords and purpose against task text.

    Case-insensitive. Sorts by keyword-match score descending.
    No LLM calls, no network.
    """
    lower = task_text.lower()
    token_set = set(re.findall(r"[a-z0-9_]+", lower))

    scored: list[tuple[int, AgentBlueprint]] = []
    for bp in get_agent_blueprint_catalog():
        score = _score_blueprint(bp, lower, token_set)
        if score > 0:
            scored.append((score, bp))

    # Sort by score descending, then by id for stability
    scored.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [bp for _, bp in scored[:max_results]]


def propose_blueprints_for_task(
    task_text: str,
    max_results: int = 5,
) -> list[AgentBlueprint]:
    """Propose the best blueprints for a task.

    Returns only PROPOSALS — no execution, no side effects.
    High-risk blueprints can appear in results but will carry
    requires_approval=True so the caller can gate on it.

    Delegates to search_blueprints and respects max_results.
    """
    candidates = search_blueprints(task_text, max_results=max_results)

    # Ensure high-risk blueprints are approval-aware
    for bp in candidates:
        assert bp.risk_level not in ("high", "critical") or bp.requires_approval, (
            f"Blueprint {bp.id} is {bp.risk_level} risk but requires_approval=False"
        )

    return candidates


# ── Internal scoring ────────────────────────────────────────────────────────────────


def _keyword_score(keywords: tuple[str, ...], lower_text: str) -> float:
    """Score how well keywords match the task text (0.0 to 1.0)."""
    if not keywords:
        return 0.0
    matched = sum(1 for kw in keywords if kw in lower_text)
    return matched / len(keywords)


def _purpose_score(purpose: str, token_set: set[str]) -> float:
    """Score how well purpose words overlap with task tokens."""
    purpose_tokens = set(re.findall(r"[a-z0-9_]+", purpose.lower()))
    if not purpose_tokens:
        return 0.0
    intersection = purpose_tokens & token_set
    return len(intersection) / len(purpose_tokens)


def _score_blueprint(bp: AgentBlueprint, lower_text: str, token_set: set[str]) -> float:
    """Compute a combined relevance score for a blueprint against task text."""
    kw = _keyword_score(bp.activation_keywords, lower_text) * 3.0  # keyword matches are strong signals
    purp = _purpose_score(bp.purpose, token_set) * 1.0
    cat = _purpose_score(bp.category, token_set) * 0.5
    return kw + purp + cat
