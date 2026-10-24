import os

import boto3
import pytest
from moto import mock_aws

from bionexus.config import Settings
from bionexus.contracts.errors import InvalidRequest
from bionexus.params import DotEnvSource, Parameters, SsmSource, parse_dotenv, set_parameters
from tests.conftest import DictSource

PREFIX = "/bionexus/prod/"


def test_dotenv_parsing_ignores_comments_and_quotes():
    text = "# comment\nA=1\nB = 'two'\nEMPTY=\nbad line\nC=\"x=y\"\n"
    assert parse_dotenv(text) == {"A": "1", "B": "two", "EMPTY": "", "C": "x=y"}


def test_local_env_file_is_used_and_real_environment_overrides_it(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("BIONEXUS_RUN_BUDGET_USD=3\nOTHER=a\n")
    assert DotEnvSource(env_file, environ={}).load()["BIONEXUS_RUN_BUDGET_USD"] == "3"
    overridden = DotEnvSource(env_file, environ={"OTHER": "b", "UNRELATED": "z"}).load()
    assert overridden["OTHER"] == "b" and "UNRELATED" not in overridden


def test_missing_env_file_is_empty_not_an_error(tmp_path):
    assert DotEnvSource(tmp_path / "nope.env", environ={}).load() == {}


@mock_aws
def test_ssm_source_reads_decrypted_nested_parameters_with_pagination():
    ssm = boto3.client("ssm", region_name="us-east-1")
    ssm.put_parameter(
        Name=PREFIX + "BIONEXUS_DATABASE_URL", Value="postgresql://x", Type="SecureString"
    )
    ssm.put_parameter(Name=PREFIX + "models/EXTRA", Value="v", Type="String")
    for i in range(25):  # more than one page
        ssm.put_parameter(Name=f"{PREFIX}P{i}", Value=str(i), Type="String")
    ssm.put_parameter(Name="/other/prefix/IGNORED", Value="no", Type="String")
    values = SsmSource(PREFIX, "us-east-1").load()
    assert values["BIONEXUS_DATABASE_URL"] == "postgresql://x"  # decrypted
    assert values["models_EXTRA"] == "v" and values["P24"] == "24" and "IGNORED" not in values


@mock_aws
def test_ssm_changes_apply_after_the_refresh_interval_without_restart():
    ssm = boto3.client("ssm", region_name="us-east-1")
    ssm.put_parameter(Name=PREFIX + "BIONEXUS_RUN_BUDGET_USD", Value="10", Type="String")
    now = [0.0]
    params = Parameters(SsmSource(PREFIX, "us-east-1"), ttl=60, clock=lambda: now[0])
    set_parameters(params)
    assert Settings.current().run_budget_usd == 10
    ssm.put_parameter(
        Name=PREFIX + "BIONEXUS_RUN_BUDGET_USD", Value="4", Type="String", Overwrite=True
    )
    assert Settings.current().run_budget_usd == 10  # cached until the interval passes
    now[0] = 61
    assert Settings.current().run_budget_usd == 4


def test_failed_refresh_keeps_last_known_good_values(isolated_parameters):
    source = DictSource({"A": "1"})
    now = [0.0]
    params = Parameters(source, ttl=10, clock=lambda: now[0])
    source.fail = True
    now[0] = 11
    assert params.get("A") == "1"


def test_production_ignores_process_environment_for_settings(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BIONEXUS_DATABASE_URL", "postgresql://from-env-must-be-ignored")
    set_parameters(Parameters(DictSource({})))
    with pytest.raises(InvalidRequest):
        from bionexus.params import parameters

        parameters().require("BIONEXUS_DATABASE_URL")


def test_required_parameter_error_names_the_parameter_not_a_value():
    set_parameters(Parameters(DictSource({})))
    from bionexus.params import parameters

    with pytest.raises(InvalidRequest, match="SOME_PARAMETER"):
        parameters().require("SOME_PARAMETER")


def test_budget_settings_are_live(isolated_parameters):
    isolated_parameters.values["BIONEXUS_RUN_BUDGET_USD"] = "2.5"
    assert Settings.current().run_budget_usd == 2.5
    isolated_parameters.values["BIONEXUS_RUN_BUDGET_USD"] = "7"
    assert Settings.current().run_budget_usd == 7
    assert os.environ.get("APP_ENV") != "production"
