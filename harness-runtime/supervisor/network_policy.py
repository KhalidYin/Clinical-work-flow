"""Trusted, generic network capability policy registry.

Product requests select a policy ID and provide identity context.  They never
provide Docker networks, proxy addresses, or an endpoint allowlist.  Runtime
availability is separate from definition so a policy can be frozen before its
gateway implementation is enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal
from urllib.parse import urlsplit

from contracts.receipt import NetworkPolicyEvidence

from .service_contracts import (
    ModelEgressBinding,
    SupervisorAttemptRequest,
    canonical_sha256,
)


class NetworkPolicyDenied(Exception):
    """A sanitized fail-closed policy decision."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class NetworkRuntimeBinding:
    """Trusted deployment binding for one externally enabled policy."""

    policy_id: str
    internal_network_id: str
    proxy_url: str
    gateway_identity: str
    gateway_config_sha256: str

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", self.policy_id) is None:
            raise ValueError("network runtime policy ID is invalid")
        if re.fullmatch(r"[0-9a-f]{64}", self.internal_network_id) is None:
            raise ValueError("network runtime Docker identity is invalid")
        if re.fullmatch(r"[0-9a-f]{64}", self.gateway_config_sha256) is None:
            raise ValueError("gateway config hash is invalid")
        if not self.gateway_identity or len(self.gateway_identity) > 160:
            raise ValueError("gateway identity is invalid")
        parsed = urlsplit(self.proxy_url)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError("gateway proxy URL is invalid") from None
        if (
            parsed.scheme != "http"
            or parsed.hostname is None
            or port is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("gateway proxy URL is invalid")


@dataclass(frozen=True)
class NetworkCapabilityPolicy:
    """Supervisor-owned policy definition, not product-supplied input."""

    policy_id: str
    kind: Literal["none", "model_endpoint", "capability_scoped"]
    allowed_endpoints: tuple[str, ...] = ()
    required_secret_refs: tuple[str, ...] = ()
    allowed_secret_refs: tuple[str, ...] = ()
    model_egress: ModelEgressBinding | None = None

    def policy_sha256(self) -> str:
        return canonical_sha256(
            {
                "policy_id": self.policy_id,
                "kind": self.kind,
                "allowed_endpoints": self.allowed_endpoints,
                "required_secret_refs": self.required_secret_refs,
                "allowed_secret_refs": self.allowed_secret_refs,
                "model_egress": (
                    self.model_egress.model_dump(mode="json")
                    if self.model_egress is not None
                    else None
                ),
            }
        )


class NetworkPolicyRegistry:
    """Resolve only definitions that the current runtime explicitly enables."""

    def __init__(
        self,
        policies: tuple[NetworkCapabilityPolicy, ...],
        *,
        available_policy_ids: frozenset[str],
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}
        if len(self._policies) != len(policies):
            raise ValueError("network policy IDs must be unique")
        unknown = available_policy_ids.difference(self._policies)
        if unknown:
            raise ValueError("available policy IDs must have trusted definitions")
        self._available_policy_ids = available_policy_ids

    def authorize(self, request: SupervisorAttemptRequest) -> NetworkPolicyEvidence:
        policy = self._policies.get(request.network_policy_id)
        if policy is None or policy.policy_id not in self._available_policy_ids:
            raise NetworkPolicyDenied(
                "network_policy_not_available",
                "requested network policy is not available",
            )

        if policy.model_egress != request.model_egress:
            raise NetworkPolicyDenied(
                "network_policy_binding_mismatch",
                "model identity or data boundary does not match network policy",
            )
        permitted_opaque_refs = set(policy.allowed_secret_refs).union(
            policy.required_secret_refs
        )
        if any(
            reference.startswith("secret://")
            and reference not in permitted_opaque_refs
            for reference in request.secret_refs
        ):
            raise NetworkPolicyDenied(
                "secret_reference_not_allowed",
                "secret reference is not allowed by network policy",
            )
        if policy.required_secret_refs and (
            tuple(request.secret_refs) != policy.required_secret_refs
        ):
            raise NetworkPolicyDenied(
                "secret_reference_not_allowed",
                "secret reference is not allowed by network policy",
            )

        return NetworkPolicyEvidence(
            policy_id=policy.policy_id,
            policy_sha256=policy.policy_sha256(),
            kind=policy.kind,
            allowed_endpoints=policy.allowed_endpoints,
        )


def none_network_policy_evidence() -> NetworkPolicyEvidence:
    """Stable evidence for the offline default used by low-level execution."""

    policy = NetworkCapabilityPolicy(
        policy_id="none",
        kind="none",
        allowed_secret_refs=("secret://p15-openai-mock",),
    )
    return NetworkPolicyEvidence(
        policy_id=policy.policy_id,
        policy_sha256=policy.policy_sha256(),
        kind=policy.kind,
        allowed_endpoints=(),
    )


def p16_network_policy_registry(
    *,
    available_policy_ids: frozenset[str] = frozenset({"none"}),
) -> NetworkPolicyRegistry:
    """Build the frozen P16 policies; DeepSeek stays unavailable until P3."""

    return NetworkPolicyRegistry(
        (
            NetworkCapabilityPolicy(
                policy_id="none",
                kind="none",
                allowed_secret_refs=("secret://p15-openai-mock",),
            ),
            NetworkCapabilityPolicy(
                policy_id="model-deepseek-v1",
                kind="model_endpoint",
                allowed_endpoints=("api.deepseek.com:443",),
                required_secret_refs=("secret://deepseek-api-key",),
                model_egress=ModelEgressBinding(
                    profile_id="deepseek-v4-flash-extractor",
                    profile_version="1.0.0",
                    provider="deepseek",
                    model="deepseek-v4-flash",
                    endpoint="https://api.deepseek.com:443",
                    data_boundary="external_allowed",
                ),
            ),
        ),
        available_policy_ids=available_policy_ids,
    )
