"""Tests for env-manager: crypto, store, and CLI smoke tests."""
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from env_manager.crypto import encrypt, decrypt
from env_manager import store
from env_manager.store import (
    _empty_vault, load_vault, save_vault, list_projects, get_project,
    set_var, delete_var, delete_project, export_dotenv, import_dotenv,
)


PASSWORD = "test_password_123"


# ─── Crypto tests ────────────────────────────────────────────────────────────

class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        original = "hello world"
        encrypted = encrypt(original, PASSWORD)
        result = decrypt(encrypted, PASSWORD)
        assert result == original

    def test_encrypt_produces_different_bytes_each_time(self):
        """Each encryption uses a random salt → different output."""
        enc1 = encrypt("same", PASSWORD)
        enc2 = encrypt("same", PASSWORD)
        assert enc1 != enc2

    def test_decrypt_wrong_password_raises(self):
        encrypted = encrypt("secret", PASSWORD)
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt(encrypted, "wrong_password")

    def test_encrypt_unicode(self):
        original = "clave=contraseña_especial_ñoño 🔑"
        encrypted = encrypt(original, PASSWORD)
        result = decrypt(encrypted, PASSWORD)
        assert result == original

    def test_encrypt_empty_string(self):
        encrypted = encrypt("", PASSWORD)
        result = decrypt(encrypted, PASSWORD)
        assert result == ""


# ─── Store tests ─────────────────────────────────────────────────────────────

class TestStore:
    def setup_method(self):
        """Use a temp vault file for each test."""
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = mock.patch.object(store, 'VAULT_FILE', Path(self.tmpdir) / 'vault.enc')
        self.patcher.start()
        # Also patch VAULT_DIR
        self.dir_patcher = mock.patch.object(store, 'VAULT_DIR', Path(self.tmpdir))
        self.dir_patcher.start()

    def teardown_method(self):
        self.patcher.stop()
        self.dir_patcher.stop()

    def test_new_vault_is_empty(self):
        vault = load_vault(PASSWORD)
        assert vault == _empty_vault()

    def test_save_and_load_roundtrip(self):
        vault = _empty_vault()
        set_var(vault, "myapp", "DB_HOST", "localhost")
        set_var(vault, "myapp", "DB_PORT", "5432")
        save_vault(vault, PASSWORD)

        loaded = load_vault(PASSWORD)
        assert loaded["envs"]["myapp"]["vars"]["DB_HOST"] == "localhost"
        assert loaded["envs"]["myapp"]["vars"]["DB_PORT"] == "5432"

    def test_list_projects(self):
        vault = _empty_vault()
        set_var(vault, "proj_a", "KEY", "val")
        set_var(vault, "proj_b", "KEY", "val")
        assert list_projects(vault) == ["proj_a", "proj_b"]

    def test_delete_var(self):
        vault = _empty_vault()
        set_var(vault, "app", "TO_DELETE", "value")
        set_var(vault, "app", "KEEP", "this")
        result = delete_var(vault, "app", "TO_DELETE")
        assert result is True
        assert "TO_DELETE" not in vault["envs"]["app"]["vars"]
        assert vault["envs"]["app"]["vars"]["KEEP"] == "this"

    def test_delete_nonexistent_var_returns_false(self):
        vault = _empty_vault()
        set_var(vault, "app", "REAL", "val")
        result = delete_var(vault, "app", "NONEXISTENT")
        assert result is False

    def test_delete_project(self):
        vault = _empty_vault()
        set_var(vault, "proj", "K", "v")
        result = delete_project(vault, "proj")
        assert result is True
        assert "proj" not in vault["envs"]

    def test_delete_nonexistent_project_returns_false(self):
        vault = _empty_vault()
        result = delete_project(vault, "ghost")
        assert result is False

    def test_export_dotenv(self):
        vault = _empty_vault()
        set_var(vault, "app", "KEY_A", "value_a")
        set_var(vault, "app", "KEY_B", "value with spaces")
        content = export_dotenv(vault, "app")
        assert "KEY_A=value_a" in content
        assert 'KEY_B="value with spaces"' in content

    def test_import_dotenv(self):
        vault = _empty_vault()
        env_content = """
# Comment
KEY1=value1
KEY2="value with spaces"
KEY3='single_quotes'
EMPTY=
"""
        count = import_dotenv(vault, "app", env_content)
        assert count == 4
        assert vault["envs"]["app"]["vars"]["KEY1"] == "value1"
        assert vault["envs"]["app"]["vars"]["KEY2"] == "value with spaces"
        assert vault["envs"]["app"]["vars"]["KEY3"] == "single_quotes"
        assert vault["envs"]["app"]["vars"]["EMPTY"] == ""

    def test_import_ignores_comments_and_blank_lines(self):
        vault = _empty_vault()
        env_content = "# comment\n\nVALID=yes\n# another comment"
        count = import_dotenv(vault, "app", env_content)
        assert count == 1

    def test_wrong_password_on_load_raises(self):
        vault = _empty_vault()
        set_var(vault, "app", "K", "v")
        save_vault(vault, PASSWORD)
        with pytest.raises(ValueError):
            load_vault("wrong_password")


# ─── CLI smoke test ──────────────────────────────────────────────────────────

class TestCLISmoke:
    """Smoke tests: verify CLI can be imported and basic commands work."""

    def test_module_imports(self):
        from env_manager import cli
        assert callable(cli.main)

    def test_cli_has_expected_commands(self):
        from env_manager.cli import cli as cli_group
        commands = set(cli_group.commands.keys())
        expected = {"list", "show", "set", "get", "delete", "describe", "export", "import", "info"}
        assert expected.issubset(commands), f"Missing commands: {expected - commands}"

    def test_env_manager_entry_point(self):
        """Verify setup.py entry point function exists."""
        from env_manager.cli import main
        assert callable(main)
