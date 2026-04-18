"""Tests for env-manager: crypto, store, validators, and CLI."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from env_manager.crypto import encrypt, decrypt
from env_manager import store
from env_manager.store import (
    _empty_vault, load_vault, save_vault, list_projects, get_project,
    set_var, delete_var, delete_project, export_dotenv, import_dotenv,
    copy_project, rename_project, set_description,
)
from env_manager.validators import validate_key, validate_project, ValidationError
from env_manager.cli import cli


PASSWORD = "test_password_123"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_vault(tmp_path):
    """Redirect vault to a temp directory for every test."""
    vault_file = tmp_path / "vault.enc"
    vault_dir = tmp_path
    with (
        mock.patch.object(store, "VAULT_FILE", vault_file),
        mock.patch.object(store, "VAULT_DIR", vault_dir),
    ):
        yield vault_file


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def vault_with_data(isolated_vault):
    """Pre-populated vault saved to disk."""
    vault = _empty_vault()
    set_var(vault, "myapp", "DB_HOST", "localhost")
    set_var(vault, "myapp", "DB_PORT", "5432")
    set_var(vault, "myapp", "SECRET", "topsecret")
    set_var(vault, "staging", "DB_HOST", "staging.host")
    set_description(vault, "myapp", "Production app")
    save_vault(vault, PASSWORD)
    return vault


# ─── Crypto ──────────────────────────────────────────────────────────────────

class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        result = decrypt(encrypt("hello world", PASSWORD), PASSWORD)
        assert result == "hello world"

    def test_encrypt_produces_unique_bytes_per_call(self):
        enc1 = encrypt("same", PASSWORD)
        enc2 = encrypt("same", PASSWORD)
        assert enc1 != enc2

    def test_decrypt_wrong_password_raises_value_error(self):
        encrypted = encrypt("secret", PASSWORD)
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt(encrypted, "wrong_password")

    def test_encrypt_decrypt_unicode(self):
        original = "contraseña_ñoño 🔑 \u4e2d\u6587"
        assert decrypt(encrypt(original, PASSWORD), PASSWORD) == original

    def test_encrypt_empty_string(self):
        assert decrypt(encrypt("", PASSWORD), PASSWORD) == ""

    def test_decrypt_truncated_data_raises(self):
        raw = encrypt("data", PASSWORD)
        with pytest.raises(ValueError):
            decrypt(raw[:5], PASSWORD)


# ─── Store — CRUD ────────────────────────────────────────────────────────────

class TestStore:
    def test_new_vault_is_empty(self):
        vault = load_vault(PASSWORD)
        assert vault == _empty_vault()

    def test_save_and_load_roundtrip(self):
        vault = _empty_vault()
        set_var(vault, "myapp", "DB_HOST", "localhost")
        save_vault(vault, PASSWORD)
        loaded = load_vault(PASSWORD)
        assert loaded["envs"]["myapp"]["vars"]["DB_HOST"] == "localhost"

    def test_list_projects_sorted(self):
        vault = _empty_vault()
        set_var(vault, "zebra", "K", "v")
        set_var(vault, "alpha", "K", "v")
        assert list_projects(vault) == ["alpha", "zebra"]

    def test_get_project_returns_none_for_missing(self):
        vault = _empty_vault()
        assert get_project(vault, "ghost") is None

    def test_delete_var_removes_key(self):
        vault = _empty_vault()
        set_var(vault, "app", "TO_DELETE", "v")
        set_var(vault, "app", "KEEP", "this")
        assert delete_var(vault, "app", "TO_DELETE") is True
        assert "TO_DELETE" not in vault["envs"]["app"]["vars"]
        assert vault["envs"]["app"]["vars"]["KEEP"] == "this"

    def test_delete_nonexistent_var_returns_false(self):
        vault = _empty_vault()
        set_var(vault, "app", "REAL", "val")
        assert delete_var(vault, "app", "NONEXISTENT") is False

    def test_delete_project_removes_it(self):
        vault = _empty_vault()
        set_var(vault, "proj", "K", "v")
        assert delete_project(vault, "proj") is True
        assert "proj" not in vault["envs"]

    def test_delete_nonexistent_project_returns_false(self):
        vault = _empty_vault()
        assert delete_project(vault, "ghost") is False

    def test_wrong_password_raises_on_load(self):
        vault = _empty_vault()
        set_var(vault, "app", "K", "v")
        save_vault(vault, PASSWORD)
        with pytest.raises(ValueError):
            load_vault("wrong_password")

    def test_empty_vault_file_raises_helpful_error(self, isolated_vault):
        isolated_vault.write_bytes(b"")
        with pytest.raises(ValueError, match="empty or corrupted"):
            load_vault(PASSWORD)

    def test_copy_project_copies_all_vars(self):
        vault = _empty_vault()
        set_var(vault, "src", "A", "1")
        set_var(vault, "src", "B", "2")
        count = copy_project(vault, "src", "dst")
        assert count == 2
        assert vault["envs"]["dst"]["vars"] == {"A": "1", "B": "2"}

    def test_copy_project_source_missing_raises(self):
        vault = _empty_vault()
        with pytest.raises(KeyError, match="not found"):
            copy_project(vault, "ghost", "dst")

    def test_rename_project(self):
        vault = _empty_vault()
        set_var(vault, "old", "K", "v")
        rename_project(vault, "old", "new")
        assert "old" not in vault["envs"]
        assert vault["envs"]["new"]["vars"]["K"] == "v"

    def test_rename_project_missing_source_raises(self):
        vault = _empty_vault()
        with pytest.raises(KeyError):
            rename_project(vault, "ghost", "new")

    def test_rename_project_dest_exists_raises(self):
        vault = _empty_vault()
        set_var(vault, "a", "K", "v")
        set_var(vault, "b", "K", "v")
        with pytest.raises(ValueError, match="already exists"):
            rename_project(vault, "a", "b")


# ─── Store — Import / Export ──────────────────────────────────────────────────

class TestImportExport:
    def test_export_simple_values(self):
        vault = _empty_vault()
        set_var(vault, "app", "KEY_A", "value_a")
        content = export_dotenv(vault, "app")
        assert "KEY_A=value_a" in content

    def test_export_quotes_values_with_spaces(self):
        vault = _empty_vault()
        set_var(vault, "app", "KEY_B", "value with spaces")
        content = export_dotenv(vault, "app")
        assert 'KEY_B="value with spaces"' in content

    def test_export_nonexistent_project_returns_empty(self):
        vault = _empty_vault()
        assert export_dotenv(vault, "ghost") == ""

    def test_import_basic_dotenv(self):
        vault = _empty_vault()
        count = import_dotenv(vault, "app", "KEY1=value1\nKEY2=value2\n")
        assert count == 2
        assert vault["envs"]["app"]["vars"]["KEY1"] == "value1"

    def test_import_double_quoted_values(self):
        vault = _empty_vault()
        import_dotenv(vault, "app", 'KEY="value with spaces"')
        assert vault["envs"]["app"]["vars"]["KEY"] == "value with spaces"

    def test_import_single_quoted_values(self):
        vault = _empty_vault()
        import_dotenv(vault, "app", "KEY='single quoted'")
        assert vault["envs"]["app"]["vars"]["KEY"] == "single quoted"

    def test_import_ignores_comments_and_blank_lines(self):
        vault = _empty_vault()
        content = "# comment\n\nVALID=yes\n# another comment"
        count = import_dotenv(vault, "app", content)
        assert count == 1

    def test_import_export_format(self):
        """'export KEY=value' shell format is parsed correctly."""
        vault = _empty_vault()
        count = import_dotenv(vault, "app", "export DB_URL=postgres://localhost/db")
        assert count == 1
        assert vault["envs"]["app"]["vars"]["DB_URL"] == "postgres://localhost/db"

    def test_import_empty_value(self):
        vault = _empty_vault()
        import_dotenv(vault, "app", "EMPTY=")
        assert vault["envs"]["app"]["vars"]["EMPTY"] == ""

    def test_roundtrip_export_then_import(self):
        vault = _empty_vault()
        set_var(vault, "orig", "HOST", "localhost")
        set_var(vault, "orig", "PORT", "5432")
        content = export_dotenv(vault, "orig")
        vault2 = _empty_vault()
        import_dotenv(vault2, "copy", content)
        assert vault2["envs"]["copy"]["vars"]["HOST"] == "localhost"
        assert vault2["envs"]["copy"]["vars"]["PORT"] == "5432"


# ─── Validators ───────────────────────────────────────────────────────────────

class TestValidators:
    def test_valid_key_passes(self):
        validate_key("DB_HOST")
        validate_key("_PRIVATE")
        validate_key("KEY123")

    def test_lowercase_key_fails(self):
        with pytest.raises(ValidationError, match="Invalid key"):
            validate_key("db_host")

    def test_key_starting_with_digit_fails(self):
        with pytest.raises(ValidationError):
            validate_key("1KEY")

    def test_empty_key_fails(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_key("")

    def test_key_with_spaces_fails(self):
        with pytest.raises(ValidationError):
            validate_key("KEY NAME")

    def test_valid_project_names(self):
        validate_project("myapp")
        validate_project("my-app")
        validate_project("my.app")
        validate_project("my_app_v2")

    def test_empty_project_name_fails(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_project("")

    def test_project_name_too_long_fails(self):
        with pytest.raises(ValidationError, match="64 characters"):
            validate_project("a" * 65)


# ─── CLI Commands ─────────────────────────────────────────────────────────────

class TestCLI:
    def test_cli_has_all_expected_commands(self):
        commands = set(cli.commands.keys())
        expected = {"list", "show", "set", "get", "delete", "describe",
                    "export", "import", "info", "copy", "rename", "run", "verify"}
        assert expected.issubset(commands)

    def test_set_and_get_via_cli(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            result = runner.invoke(cli, ["set", "myapp", "DB_HOST", "localhost"])
            assert result.exit_code == 0
            assert "Set DB_HOST" in result.output

            result = runner.invoke(cli, ["get", "myapp", "DB_HOST"])
            assert result.exit_code == 0
            assert "localhost" in result.output

    def test_list_json_output(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            runner.invoke(cli, ["set", "myapp", "K", "v"])
            result = runner.invoke(cli, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert any(p["name"] == "myapp" for p in data)

    def test_show_json_output(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            runner.invoke(cli, ["set", "myapp", "DB_HOST", "localhost"])
            result = runner.invoke(cli, ["show", "myapp", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["DB_HOST"] == "localhost"

    def test_set_invalid_key_rejected(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            result = runner.invoke(cli, ["set", "myapp", "invalid key", "v"])
        assert result.exit_code != 0
        assert "Validation error" in result.output

    def test_copy_command(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            runner.invoke(cli, ["set", "src", "KEY_A", "val"])
            result = runner.invoke(cli, ["copy", "src", "dst"])
        assert result.exit_code == 0
        assert "Copied 1" in result.output

    def test_rename_command(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            runner.invoke(cli, ["set", "oldname", "K", "v"])
            result = runner.invoke(cli, ["rename", "oldname", "newname"])
        assert result.exit_code == 0
        assert "newname" in result.output

    def test_verify_command_success(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            runner.invoke(cli, ["set", "myapp", "K", "v"])
            result = runner.invoke(cli, ["verify"])
        assert result.exit_code == 0
        assert "Vault OK" in result.output

    def test_verify_command_wrong_password(self, runner, tmp_path):
        vault_path = str(tmp_path / "vault.enc")
        with mock.patch.dict(os.environ, {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": vault_path}):
            runner.invoke(cli, ["set", "myapp", "K", "v"])
        with mock.patch.dict(os.environ, {"ENV_MANAGER_PASSWORD": "wrongpass", "ENV_MANAGER_VAULT": vault_path}):
            result = runner.invoke(cli, ["verify"])
        assert result.exit_code != 0

    def test_info_command_no_password(self, runner):
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "vault" in result.output.lower()

    def test_delete_project_requires_flag(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            runner.invoke(cli, ["set", "myapp", "K", "v"])
            result = runner.invoke(cli, ["delete", "myapp", "--project-only", "--yes"])
        assert result.exit_code == 0
        assert "deleted" in result.output

    def test_get_missing_project_fails(self, runner, tmp_path):
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            result = runner.invoke(cli, ["get", "ghost", "KEY"])
        assert result.exit_code != 0

    def test_export_to_file(self, runner, tmp_path):
        output_file = str(tmp_path / "out.env")
        env = {"ENV_MANAGER_PASSWORD": PASSWORD, "ENV_MANAGER_VAULT": str(tmp_path / "vault.enc")}
        with mock.patch.dict(os.environ, env, clear=False):
            runner.invoke(cli, ["set", "myapp", "KEY_A", "val"])
            result = runner.invoke(cli, ["export", "myapp", "-o", output_file])
        assert result.exit_code == 0
        content = Path(output_file).read_text()
        assert "KEY_A=val" in content
