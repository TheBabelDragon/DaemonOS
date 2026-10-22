"""Deterministic deployment planner.

Planning never modifies devices or executes strategies.
LLM suggestions cannot bypass validation.
"""

from __future__ import annotations

from daemonos.catalog.models import CompatibilityCatalog, DeploymentStrategy, RuntimeTarget
from daemonos.catalog.loader import load_builtin_catalog
from daemonos.discovery.profile import DeviceCapabilityProfile

from .plan import CandidatePlan, PlanResult, PlanRisk, PlanStatus

_INVASIVENESS_SCORE = {
    "none": 100,
    "low": 80,
    "medium": 50,
    "high": 20,
    "destructive": 5,
}

_INVASIVENESS_RISK = {
    "none": PlanRisk.NONE,
    "low": PlanRisk.LOW,
    "medium": PlanRisk.MEDIUM,
    "high": PlanRisk.HIGH,
    "destructive": PlanRisk.DESTRUCTIVE,
}


class DeploymentPlanner:
    """Evaluate device profiles against a compatibility catalog."""

    def __init__(self, catalog: CompatibilityCatalog | None = None) -> None:
        self.catalog = catalog or load_builtin_catalog()

    def plan(
        self,
        profile: DeviceCapabilityProfile,
        objective: str = "run_agent",
    ) -> PlanResult:
        candidates: list[CandidatePlan] = []

        for strategy in self.catalog.strategies:
            target = self.catalog.target_by_id(strategy.target_id)
            if target is None:
                continue
            candidate = self._evaluate(profile, target, strategy, objective)
            candidates.append(candidate)

        # Deterministic ordering: viable first by score desc, then by strategy_id
        def sort_key(c: CandidatePlan) -> tuple:
            viable = 0 if c.status == PlanStatus.VIABLE else 1 if c.status == PlanStatus.UNCERTAIN else 2
            return (viable, -c.score, c.strategy_id)

        candidates.sort(key=sort_key)

        preferred = None
        for c in candidates:
            if c.status == PlanStatus.VIABLE:
                preferred = c
                break

        unresolved = list(profile.unresolved_questions)
        if preferred is None:
            for c in candidates:
                unresolved.extend(c.recommended_probes)
                unresolved.extend(c.missing_prerequisites)

        # Dedupe unresolved while preserving order
        seen: set[str] = set()
        uniq_unresolved: list[str] = []
        for u in unresolved:
            if u not in seen:
                seen.add(u)
                uniq_unresolved.append(u)

        if preferred is not None:
            overall = PlanStatus.VIABLE
            summary = (
                f"Preferred strategy '{preferred.strategy_id}' for target "
                f"'{preferred.target_id}' (risk={preferred.risk.value}). "
                "Plan is not authorized or executed."
            )
        elif any(c.status == PlanStatus.UNCERTAIN for c in candidates):
            overall = PlanStatus.UNCERTAIN
            summary = (
                "No fully validated viable plan; some candidates need more evidence. "
                "Planning does not execute or authorize actions."
            )
        elif candidates:
            overall = PlanStatus.REJECTED
            summary = (
                "All catalog strategies were rejected for this profile. "
                "See candidate reasons and unmet requirements."
            )
        else:
            overall = PlanStatus.UNSUPPORTED
            summary = "No strategies in catalog; cannot recommend a path."

        return PlanResult(
            catalog_version=self.catalog.catalog_version,
            device_key=profile.device_key,
            objective=objective,
            candidates=candidates,
            preferred=preferred,
            overall_status=overall,
            summary=summary,
            unresolved_questions=uniq_unresolved,
            execution_authorized=False,
            side_effects=[],  # planning never has device side effects
        )

    def _evaluate(
        self,
        profile: DeviceCapabilityProfile,
        target: RuntimeTarget,
        strategy: DeploymentStrategy,
        objective: str,
    ) -> CandidatePlan:
        reasons: list[str] = []
        missing: list[str] = []
        unmet: list[str] = []
        probes: list[str] = []
        evidence: list[str] = []

        hw = profile.hardware
        rt = profile.runtime

        # Architecture
        if target.arch_requirements:
            if hw.arch is None:
                missing.append("architecture unknown")
                probes.append("probe.arch")
            elif hw.arch not in target.arch_requirements and not (
                hw.arch == "aarch64" and "arm64" in target.arch_requirements
            ):
                unmet.append(
                    f"arch {hw.arch} not in {target.arch_requirements}"
                )

        # OS family
        if target.os_families:
            if rt.os_family is None:
                missing.append("os_family unknown")
                probes.append("probe.os")
            elif rt.os_family not in target.os_families:
                unmet.append(
                    f"os_family {rt.os_family} not in {target.os_families}"
                )

        # Android API
        if target.min_android_api is not None:
            if rt.android_api is None:
                if rt.os_family == "android" or rt.os_family is None:
                    missing.append("android_api unknown")
                    probes.append("probe.os")
            elif rt.android_api < target.min_android_api:
                unmet.append(
                    f"android_api {rt.android_api} < min {target.min_android_api}"
                )

        if target.max_android_api is not None and rt.android_api is not None:
            if rt.android_api > target.max_android_api:
                unmet.append(
                    f"android_api {rt.android_api} > max {target.max_android_api}"
                )

        # RAM
        if target.min_ram_mb is not None:
            if hw.ram_mb is None:
                missing.append("ram_mb unknown")
                probes.append("probe.memory")
            elif hw.ram_mb < target.min_ram_mb:
                unmet.append(f"ram_mb {hw.ram_mb} < min {target.min_ram_mb}")

        # Bootloader
        if target.requires_unlocked_bootloader:
            if rt.bootloader_state is None:
                missing.append("bootloader_state unknown")
                probes.append("probe.bootloader")
            elif rt.bootloader_state != "unlocked":
                unmet.append(
                    f"bootloader_state is {rt.bootloader_state}, need unlocked"
                )

        # Family hints (external evidence)
        for fam in self.catalog.device_families:
            model_match = hw.model in fam.match_models if hw.model else False
            id_match = hw.model_id in fam.match_model_ids if hw.model_id else False
            if model_match or id_match:
                if target.id in fam.known_compatible_targets:
                    evidence.append(
                        f"family {fam.id} lists target {target.id} as compatible "
                        f"({fam.verification.value})"
                    )
                    reasons.append(f"device family hint: {fam.id}")
                if target.id in fam.known_incompatible_targets:
                    unmet.append(f"family {fam.id} marks target incompatible")

        # Strategy-level notes
        evidence.append(f"strategy verification={strategy.verification.value}")
        if strategy.evidence_notes:
            evidence.append(strategy.evidence_notes)

        risk = _INVASIVENESS_RISK.get(strategy.invasiveness, PlanRisk.HIGH)
        score = _INVASIVENESS_SCORE.get(strategy.invasiveness, 0)

        # Prefer agent_on_existing_os for run_agent objective
        if objective == "run_agent" and target.kind == "agent_on_existing_os":
            score += 15
        if objective == "run_agent" and target.kind == "linux_native":
            score += 10

        if unmet:
            status = PlanStatus.REJECTED
            reasons.append("hard requirements unmet")
            reasons.extend(unmet)
        elif missing:
            status = PlanStatus.UNCERTAIN
            reasons.append("insufficient evidence")
            reasons.extend(missing)
        else:
            status = PlanStatus.VIABLE
            reasons.append("all hard requirements satisfied with available evidence")

        # Never treat destructive as viable without explicit unlocked + evidence
        if strategy.invasiveness == "destructive" and status == PlanStatus.VIABLE:
            # Still viable only if bootloader unlocked was confirmed — already checked
            reasons.append(
                "destructive strategy; requires explicit authorization before execution"
            )

        return CandidatePlan(
            strategy_id=strategy.id,
            target_id=target.id,
            status=status,
            risk=risk,
            requires_authorization=strategy.requires_authorization,
            invasiveness=strategy.invasiveness,
            score=score if status == PlanStatus.VIABLE else score - 50,
            reasons=reasons,
            missing_prerequisites=missing,
            unmet_hard_requirements=unmet,
            recommended_probes=list(dict.fromkeys(probes)),
            steps_summary=list(strategy.steps_summary),
            evidence_notes=evidence,
        )
