"""Locust load testing for LLM Agent Platform.

Three user classes simulate normal, peak, and stress traffic patterns.
All requests go through /v1/chat/completions with Bearer auth.

Safety: MAX_REQUESTS_PER_CLASS caps total requests to prevent runaway costs.
Override via LOCUST_MAX_REQUESTS env var.
"""

from __future__ import annotations

import os
import random
import threading

from locust import HttpUser, between, events, task

# --- Configuration ---

MASTER_TOKEN = os.getenv("MASTER_TOKEN", "test-master-token")
MAX_REQUESTS_PER_CLASS = int(os.getenv("LOCUST_MAX_REQUESTS", "200"))

SHORT_PROMPTS = [
    "Say hello in one word",
    "What is 2+2?",
    "Name a color",
    "Say yes or no",
    "Count to three",
    "Name a fruit",
    "What day is today?",
    "Say goodbye",
    "Pick a number",
    "Name an animal",
]

FREE_MODELS = [
    "stepfun/step-3.5-flash",
    "nvidia/nemotron-3-super",
]

MID_MODELS = [
    "deepseek/deepseek-chat",
    "openai/gpt-oss-120b",
]

ALL_MODELS = FREE_MODELS + MID_MODELS + [
    "x-ai/grok-4.1-fast",
    "google/gemini-2.5-flash-lite",
]


class _RequestCounter:
    """Thread-safe per-class request counter with safety cap."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def increment(self, class_name: str) -> bool:
        """Increment counter. Returns True if under limit, False if cap reached."""
        with self._lock:
            current = self._counts.get(class_name, 0)
            if current >= MAX_REQUESTS_PER_CLASS:
                return False
            self._counts[class_name] = current + 1
            return True

    def get(self, class_name: str) -> int:
        with self._lock:
            return self._counts.get(class_name, 0)


_counter = _RequestCounter()


def _make_payload(model: str) -> dict:
    return {
        "model": model,
        "messages": [
            {"role": "user", "content": random.choice(SHORT_PROMPTS)},
        ],
        "max_tokens": 10,
    }


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {MASTER_TOKEN}"}


class NormalUser(HttpUser):
    """Normal traffic: 10-15 concurrent users, free models, relaxed pacing."""

    wait_time = between(1, 3)
    weight = 3

    @task
    def chat_completion(self) -> None:
        class_name = type(self).__name__
        if not _counter.increment(class_name):
            self.environment.runner.quit()
            return

        model = random.choice(FREE_MODELS)
        self.client.post(
            "/v1/chat/completions",
            json=_make_payload(model),
            headers=_auth_headers(),
            name=f"/v1/chat/completions [{model}]",
        )


class PeakUser(HttpUser):
    """Peak traffic: mixed models, faster request rate."""

    wait_time = between(0.5, 1.5)
    weight = 2

    @task
    def chat_completion(self) -> None:
        class_name = type(self).__name__
        if not _counter.increment(class_name):
            self.environment.runner.quit()
            return

        model = random.choice(FREE_MODELS + MID_MODELS)
        self.client.post(
            "/v1/chat/completions",
            json=_make_payload(model),
            headers=_auth_headers(),
            name=f"/v1/chat/completions [{model}]",
        )


class StressUser(HttpUser):
    """Stress test: all models, maximum throughput, provoke 429 errors."""

    wait_time = between(0.1, 0.5)
    weight = 1

    @task
    def chat_completion(self) -> None:
        class_name = type(self).__name__
        if not _counter.increment(class_name):
            self.environment.runner.quit()
            return

        model = random.choice(ALL_MODELS)
        self.client.post(
            "/v1/chat/completions",
            json=_make_payload(model),
            headers=_auth_headers(),
            name=f"/v1/chat/completions [{model}]",
        )

    @task(1)
    def health_check(self) -> None:
        """Periodic health check during stress."""
        self.client.get("/health", name="/health")


@events.quitting.add_listener
def _print_summary(environment, **_kwargs) -> None:  # noqa: ANN001
    for cls_name in ("NormalUser", "PeakUser", "StressUser"):
        count = _counter.get(cls_name)
        cap = MAX_REQUESTS_PER_CLASS
        print(f"  {cls_name}: {count}/{cap} requests")  # noqa: T201
