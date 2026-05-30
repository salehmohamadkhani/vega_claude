"""Tests for Agent Council V2 artifact contracts."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.artifact_contracts import (
    ArtifactValidationError,
    ContractRegistry,
    load_default_contracts,
)
from core.ralph.agent_council.registry import load_default_registry


class TestDefaultContracts:
    @pytest.fixture
    def contracts(self):
        return load_default_contracts()

    def test_loads_without_error(self, contracts):
        assert contracts is not None
        assert contracts.contract_count >= 20

    def test_all_contracts_have_required_fields(self, contracts):
        for c in contracts.list_all():
            assert len(c.required_fields) > 0, f"{c.artifact_id} has no required_fields"
            assert len(c.consumers) > 0, f"{c.artifact_id} has no consumers"
            assert c.validation_method, f"{c.artifact_id} has no validation_method"
            assert len(c.pass_criteria) > 0, f"{c.artifact_id} has no pass_criteria"
            assert len(c.fail_criteria) > 0, f"{c.artifact_id} has no fail_criteria"

    def test_20_core_contracts_present(self, contracts):
        expected = [
            "business_brief",
            "strategic_direction",
            "market_research_report",
            "competitor_map",
            "target_personas",
            "user_journey_maps",
            "product_requirements_doc",
            "user_stories",
            "acceptance_criteria",
            "brand_strategy",
            "brand_book",
            "UX_flow_map",
            "design_system",
            "UI_spec",
            "architecture_spec",
            "API_contract",
            "database_schema_spec",
            "security_requirements",
            "test_plan",
            "QA_report",
            "deployment_plan",
            "release_readiness_report",
            "final_arbiter_decision",
        ]
        for eid in expected:
            c = contracts.get_optional(eid)
            assert c is not None, f"Missing contract: {eid}"

    def test_all_pass_validation(self, contracts):
        errors = contracts.validate_all()
        assert errors == {}, f"Validation errors: {errors}"

    def test_lookup_by_owner(self, contracts):
        owned = contracts.list_by_owner("qa_verification_agent")
        assert len(owned) >= 2
        owned_ids = {c.artifact_id for c in owned}
        assert "test_plan" in owned_ids
        assert "QA_report" in owned_ids

    def test_lookup_missing_raises(self, contracts):
        with pytest.raises(KeyError):
            contracts.get("nonexistent_artifact")

    def test_lookup_optional_returns_none(self, contracts):
        assert contracts.get_optional("nonexistent") is None

    def test_contract_count(self, contracts):
        assert contracts.contract_count >= 23

    def test_artifact_ids(self, contracts):
        ids = contracts.artifact_ids
        assert isinstance(ids, tuple)
        assert "business_brief" in ids
        assert "final_arbiter_decision" in ids


class TestContractValidation:
    def test_empty_required_fields_fails_validation(self):
        from core.ralph.agent_council.models import ArtifactContract

        contracts = ContractRegistry(contracts=(
            ArtifactContract(
                artifact_id="bad",
                name="Bad Contract",
                owner_agent="x",
                required_fields=(),  # empty!
                consumers=("y",),
                validation_method="check",
                pass_criteria=("pass",),
                fail_criteria=("fail",),
            ),
        ))
        errors = contracts.validate_all()
        assert "bad" in errors

    def test_empty_consumers_fails_validation(self):
        from core.ralph.agent_council.models import ArtifactContract

        contracts = ContractRegistry(contracts=(
            ArtifactContract(
                artifact_id="no_consumers",
                name="No Consumers",
                owner_agent="x",
                required_fields=("a",),
                consumers=(),  # empty!
                validation_method="check",
                pass_criteria=("pass",),
                fail_criteria=("fail",),
            ),
        ))
        errors = contracts.validate_all()
        assert "no_consumers" in errors

    def test_empty_pass_criteria_fails(self):
        from core.ralph.agent_council.models import ArtifactContract

        contracts = ContractRegistry(contracts=(
            ArtifactContract(
                artifact_id="no_pass",
                name="No Pass",
                owner_agent="x",
                required_fields=("a",),
                consumers=("y",),
                validation_method="check",
                pass_criteria=(),  # empty!
                fail_criteria=("fail",),
            ),
        ))
        errors = contracts.validate_all()
        assert "no_pass" in errors


class TestContractRegistryWithAgents:
    def test_validates_against_agent_registry(self):
        registry = load_default_registry()
        contracts = load_default_contracts(agent_registry=registry)
        assert contracts.contract_count >= 23

    def test_unknown_owner_raises(self):
        from core.ralph.agent_council.models import ArtifactContract

        registry = load_default_registry()
        with pytest.raises(ArtifactValidationError, match="not found"):
            ContractRegistry(
                contracts=(
                    ArtifactContract(
                        artifact_id="bad_owner",
                        name="Bad Owner",
                        owner_agent="nonexistent_owner_xyz",
                        required_fields=("a",),
                        consumers=("executive_vision_agent",),
                        validation_method="check",
                        pass_criteria=("pass",),
                        fail_criteria=("fail",),
                    ),
                ),
                agent_registry=registry,
            )
