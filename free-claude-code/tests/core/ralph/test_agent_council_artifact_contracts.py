"""Tests for Agent Council V2 artifact contracts — updated for 56-agent registry."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.artifact_contracts import (
    ArtifactValidationError,
    ContractRegistry,
    load_default_contracts,
)
from core.ralph.agent_council.models import ArtifactContract
from core.ralph.agent_council.registry import load_default_registry


@pytest.fixture
def agent_registry():
    return load_default_registry()


@pytest.fixture
def contract_registry(agent_registry):
    return load_default_contracts(agent_registry=agent_registry)


class TestDefaultContracts:
    def test_has_at_least_30_contracts(self, contract_registry):
        assert contract_registry.contract_count >= 30

    def test_all_contracts_validate(self, contract_registry):
        errors = contract_registry.validate_all()
        assert errors == {}, f"Contracts with errors: {list(errors.keys())}"

    def test_core_contracts_exist(self, contract_registry):
        core = [
            "business_brief", "strategic_direction",
            "market_research_report", "competitor_map",
            "target_personas", "user_journey_maps",
            "product_requirements_doc", "user_stories", "acceptance_criteria",
            "brand_strategy", "brand_book",
            "UX_flow_map", "design_system", "UI_spec",
            "architecture_spec", "API_contract", "database_schema_spec",
            "security_requirements",
            "test_plan", "QA_report",
            "deployment_plan", "release_readiness_report",
            "final_arbiter_decision",
        ]
        for art_id in core:
            contract = contract_registry.get(art_id)
            assert contract is not None, f"Missing core contract: {art_id}"

    def test_business_brief_owner_is_chief_vision_officer(self, contract_registry):
        contract = contract_registry.get("business_brief")
        assert contract.owner_agent == "chief_vision_officer"

    def test_api_contract_owner_is_api_architect(self, contract_registry):
        contract = contract_registry.get("API_contract")
        assert contract.owner_agent == "api_architect"

    def test_security_requirements_owner_is_security_engineer(self, contract_registry):
        contract = contract_registry.get("security_requirements")
        assert contract.owner_agent == "security_engineer"

    def test_qa_report_owner_is_qa_engineer(self, contract_registry):
        contract = contract_registry.get("QA_report")
        assert contract.owner_agent == "qa_engineer"

    def test_growth_strategy_exists(self, contract_registry):
        contract = contract_registry.get("growth_strategy")
        assert contract.owner_agent == "growth_analyst"

    def test_observability_spec_exists(self, contract_registry):
        contract = contract_registry.get("observability_spec")
        assert contract.owner_agent == "observability_engineer"

    def test_ethics_audit_report_exists(self, contract_registry):
        contract = contract_registry.get("ethics_audit_report")
        assert contract.owner_agent == "chief_product_ethics_officer"

    def test_compliance_requirements_exists(self, contract_registry):
        contract = contract_registry.get("compliance_requirements")
        assert contract.owner_agent == "legal_compliance_officer"

    def test_pentest_report_exists(self, contract_registry):
        contract = contract_registry.get("pentest_report")
        assert contract.owner_agent == "penetration_tester"

    def test_dependency_audit_report_exists(self, contract_registry):
        contract = contract_registry.get("dependency_audit_report")
        assert contract.owner_agent == "dependency_auditor"

    def test_visual_qa_report_exists(self, contract_registry):
        contract = contract_registry.get("visual_QA_report")
        assert contract.owner_agent == "visual_qa_engineer"

    def test_performance_report_exists(self, contract_registry):
        contract = contract_registry.get("performance_report")
        assert contract.owner_agent == "performance_tester"

    def test_data_architecture_spec_exists(self, contract_registry):
        contract = contract_registry.get("data_architecture_spec")
        assert contract.owner_agent == "data_architect"


class TestContractValidation:
    def test_empty_required_fields_fails(self):
        contract = ArtifactContract(
            artifact_id="test", name="T", owner_agent="o",
            required_fields=(), consumers=("c",),
            validation_method="v", pass_criteria=("p",), fail_criteria=("f",),
        )
        cr = ContractRegistry(contracts=(contract,))
        errors = cr.validate_contract(contract)
        assert any("required_fields" in e for e in errors)

    def test_empty_consumers_fails(self):
        contract = ArtifactContract(
            artifact_id="test", name="T", owner_agent="o",
            required_fields=("a",),
            validation_method="v", pass_criteria=("p",), fail_criteria=("f",),
        )
        cr = ContractRegistry(contracts=(contract,))
        errors = cr.validate_contract(contract)
        assert any("consumers" in e for e in errors)

    def test_empty_pass_criteria_fails(self):
        contract = ArtifactContract(
            artifact_id="test", name="T", owner_agent="o",
            required_fields=("a",), consumers=("c",),
            validation_method="v", fail_criteria=("f",),
        )
        cr = ContractRegistry(contracts=(contract,))
        errors = cr.validate_contract(contract)
        assert any("pass_criteria" in e for e in errors)

    def test_empty_fail_criteria_fails(self):
        contract = ArtifactContract(
            artifact_id="test", name="T", owner_agent="o",
            required_fields=("a",), consumers=("c",),
            validation_method="v", pass_criteria=("p",),
        )
        cr = ContractRegistry(contracts=(contract,))
        errors = cr.validate_contract(contract)
        assert any("fail_criteria" in e for e in errors)

    def test_validation_against_registry_wrong_owner(self, agent_registry):
        contract = ArtifactContract(
            artifact_id="bad_contract", name="Bad", owner_agent="nonexistent",
            required_fields=("x",), consumers=("chief_vision_officer",),
            validation_method="v", pass_criteria=("p",), fail_criteria=("f",),
        )
        with pytest.raises(ArtifactValidationError, match="not found"):
            ContractRegistry(contracts=(contract,), agent_registry=agent_registry)

    def test_validation_against_registry_wrong_consumer(self, agent_registry):
        contract = ArtifactContract(
            artifact_id="bad_contract", name="Bad", owner_agent="chief_vision_officer",
            required_fields=("x",), consumers=("nonexistent",),
            validation_method="v", pass_criteria=("p",), fail_criteria=("f",),
        )
        with pytest.raises(ArtifactValidationError, match="not found"):
            ContractRegistry(contracts=(contract,), agent_registry=agent_registry)


class TestContractLookups:
    @pytest.fixture
    def cr(self, agent_registry):
        return load_default_contracts(agent_registry=agent_registry)

    def test_missing_lookup_raises(self, cr):
        with pytest.raises(KeyError):
            cr.get("nonexistent_artifact")

    def test_list_by_owner(self, cr):
        contracts = cr.list_by_owner("chief_vision_officer")
        assert len(contracts) >= 1
        assert any(c.artifact_id == "business_brief" for c in contracts)

    def test_all_artifact_ids_are_unique(self, cr):
        ids = cr.artifact_ids
        assert len(ids) == len(set(ids))
