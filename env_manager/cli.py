"""CLI entry point for env-manager."""
import json
import os
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .store import (
    load_vault, save_vault, list_projects, get_project,
    set_var, delete_var, delete_project, set_description,
    export_dotenv, import_dotenv, copy_project, rename_project,
    VAULT_FILE,
)
from .validators import validate_key, validate_project, ValidationError

console = Console()


def _get_password() -> str:
    """Prompt for vault password (respects ENV_MANAGER_PASSWORD env var)."""
    pwd = os.environ.get("ENV_MANAGER_PASSWORD", "")
    if not pwd:
        pwd = click.prompt("Vault password", hide_input=True)
    return pwd


def _load_or_exit(password: str) -> dict:
    """Load vault or print error and exit."""
    try:
        return load_vault(password)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@click.group()
@click.version_option("1.1.0", prog_name="env-manager")
def cli():
    """env-manager — Encrypted .env vault for multiple projects.

    Set ENV_MANAGER_PASSWORD to skip the password prompt.
    Set ENV_MANAGER_VAULT to use a custom vault file path.
    Set ENV_MANAGER_LOG_LEVEL=DEBUG for verbose logging.
    """


# ─── Projects ────────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--password", "-p", default="", help="Vault password")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def list_cmd(password, as_json):
    """List all projects in the vault."""
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)
    projects = list_projects(vault)

    if as_json:
        result = [
            {
                "name": p,
                "count": len(vault["envs"][p].get("vars", {})),
                "description": vault["envs"][p].get("description", ""),
            }
            for p in projects
        ]
        print(json.dumps(result, indent=2))
        return

    if not projects:
        console.print("[yellow]No projects found. Add one with:[/yellow] env-manager set <project> KEY value")
        return

    table = Table(title="Projects in vault", show_header=True)
    table.add_column("Project", style="cyan", no_wrap=True)
    table.add_column("Variables", justify="right", style="green")
    table.add_column("Description", style="dim")

    for proj in projects:
        data = vault["envs"][proj]
        count = len(data.get("vars", {}))
        desc = data.get("description", "")
        table.add_row(proj, str(count), desc)

    console.print(table)


@cli.command("show")
@click.argument("project")
@click.option("--password", "-p", default="", help="Vault password")
@click.option("--reveal", "-r", is_flag=True, help="Show actual values (default: masked)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (implies --reveal)")
def show_cmd(project, password, reveal, as_json):
    """Show variables for a PROJECT."""
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)

    data = get_project(vault, project)
    if not data:
        console.print(f"[red]Project '{project}' not found.[/red]")
        sys.exit(1)

    vars_dict = data.get("vars", {})

    if as_json:
        print(json.dumps(vars_dict, indent=2))
        return

    if not vars_dict:
        console.print(f"[yellow]Project '{project}' has no variables.[/yellow]")
        return

    table = Table(title=f"[cyan]{project}[/cyan]", show_header=True)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key in sorted(vars_dict.keys()):
        value = vars_dict[key] if reveal else "•" * min(len(vars_dict[key]), 12)
        table.add_row(key, value)

    console.print(table)
    if not reveal:
        console.print("[dim]Use --reveal to show actual values[/dim]")


@cli.command("set")
@click.argument("project")
@click.argument("key")
@click.argument("value")
@click.option("--password", "-p", default="", help="Vault password")
def set_cmd(project, key, value, password):
    """Set a KEY=VALUE in PROJECT."""
    try:
        validate_project(project)
        validate_key(key)
    except ValidationError as e:
        console.print(f"[red]Validation error:[/red] {e}")
        sys.exit(1)
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)
    set_var(vault, project, key, value)
    save_vault(vault, password)
    console.print(f"[green]✓[/green] Set {key} in [cyan]{project}[/cyan]")


@cli.command("get")
@click.argument("project")
@click.argument("key")
@click.option("--password", "-p", default="", help="Vault password")
def get_cmd(project, key, password):
    """Get the value of KEY in PROJECT (prints raw value for scripting)."""
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)

    data = get_project(vault, project)
    if not data:
        console.print(f"[red]Project '{project}' not found.[/red]", file=sys.stderr)
        sys.exit(1)

    value = data.get("vars", {}).get(key)
    if value is None:
        console.print(f"[red]Key '{key}' not found in '{project}'.[/red]", file=sys.stderr)
        sys.exit(1)

    print(value)


@cli.command("delete")
@click.argument("project")
@click.argument("key", required=False)
@click.option("--password", "-p", default="", help="Vault password")
@click.option("--project-only", is_flag=True, help="Delete the entire project")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_cmd(project, key, password, project_only, yes):
    """Delete a KEY from PROJECT, or the entire PROJECT with --project-only."""
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)

    if project_only:
        if not yes:
            click.confirm(f"Delete entire project '{project}'?", abort=True)
        if delete_project(vault, project):
            save_vault(vault, password)
            console.print(f"[green]✓[/green] Project [cyan]{project}[/cyan] deleted")
        else:
            console.print(f"[red]Project '{project}' not found.[/red]")
            sys.exit(1)
    elif key:
        if delete_var(vault, project, key):
            save_vault(vault, password)
            console.print(f"[green]✓[/green] Deleted {key} from [cyan]{project}[/cyan]")
        else:
            console.print(f"[red]Key '{key}' not found in '{project}'.[/red]")
            sys.exit(1)
    else:
        console.print("[red]Provide a KEY to delete, or use --project-only[/red]")
        sys.exit(1)


@cli.command("describe")
@click.argument("project")
@click.argument("description")
@click.option("--password", "-p", default="", help="Vault password")
def describe_cmd(project, description, password):
    """Set a DESCRIPTION for PROJECT."""
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)
    set_description(vault, project, description)
    save_vault(vault, password)
    console.print(f"[green]✓[/green] Description updated for [cyan]{project}[/cyan]")


@cli.command("copy")
@click.argument("source")
@click.argument("dest")
@click.option("--password", "-p", default="", help="Vault password")
def copy_cmd(source, dest, password):
    """Copy all vars from SOURCE project into DEST project."""
    try:
        validate_project(dest)
    except ValidationError as e:
        console.print(f"[red]Validation error:[/red] {e}")
        sys.exit(1)
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)
    try:
        count = copy_project(vault, source, dest)
    except KeyError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    save_vault(vault, password)
    console.print(f"[green]✓[/green] Copied {count} variable(s) from [cyan]{source}[/cyan] to [cyan]{dest}[/cyan]")


@cli.command("rename")
@click.argument("old_name")
@click.argument("new_name")
@click.option("--password", "-p", default="", help="Vault password")
def rename_cmd(old_name, new_name, password):
    """Rename a project from OLD_NAME to NEW_NAME."""
    try:
        validate_project(new_name)
    except ValidationError as e:
        console.print(f"[red]Validation error:[/red] {e}")
        sys.exit(1)
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)
    try:
        rename_project(vault, old_name, new_name)
    except (KeyError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    save_vault(vault, password)
    console.print(f"[green]✓[/green] Renamed [cyan]{old_name}[/cyan] → [cyan]{new_name}[/cyan]")


@cli.command("run")
@click.argument("project")
@click.argument("command", nargs=-1, required=True)
@click.option("--password", "-p", default="", help="Vault password")
def run_cmd(project, command, password):
    """Run COMMAND with PROJECT vars injected as environment variables.

    Example: env-manager run myapp -- python manage.py migrate
    """
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)

    data = get_project(vault, project)
    if not data:
        console.print(f"[red]Project '{project}' not found.[/red]")
        sys.exit(1)

    env = dict(os.environ)
    env.update(data.get("vars", {}))
    result = subprocess.run(list(command), env=env)
    sys.exit(result.returncode)


# ─── Import / Export ─────────────────────────────────────────────────────────

@cli.command("export")
@click.argument("project")
@click.option("--password", "-p", default="", help="Vault password")
@click.option("--output", "-o", default=None, help="Output file (default: stdout)")
def export_cmd(project, password, output):
    """Export PROJECT variables as a .env file."""
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)

    data = get_project(vault, project)
    if not data:
        console.print(f"[red]Project '{project}' not found.[/red]")
        sys.exit(1)

    content = export_dotenv(vault, project)
    if output:
        Path(output).write_text(content)
        console.print(f"[green]✓[/green] Exported {len(data.get('vars', {}))} vars to {output}")
    else:
        print(content, end="")


@cli.command("import")
@click.argument("project")
@click.argument("file", type=click.Path(exists=True))
@click.option("--password", "-p", default="", help="Vault password")
def import_cmd(project, file, password):
    """Import variables from a .env FILE into PROJECT."""
    try:
        validate_project(project)
    except ValidationError as e:
        console.print(f"[red]Validation error:[/red] {e}")
        sys.exit(1)
    if not password:
        password = _get_password()
    vault = _load_or_exit(password)
    content = Path(file).read_text()
    count = import_dotenv(vault, project, content)
    save_vault(vault, password)
    console.print(f"[green]✓[/green] Imported {count} variable(s) into [cyan]{project}[/cyan]")


# ─── Vault management ────────────────────────────────────────────────────────

@cli.command("info")
def info_cmd():
    """Show vault location and status (no password needed)."""
    exists = VAULT_FILE.exists()
    size = VAULT_FILE.stat().st_size if exists else 0
    console.print(Panel.fit(
        f"[bold]Vault path:[/bold] {VAULT_FILE}\n"
        f"[bold]Exists:[/bold] {'[green]Yes[/green]' if exists else '[red]No[/red]'}\n"
        f"[bold]Size:[/bold] {size:,} bytes\n"
        f"[bold]Password env var:[/bold] ENV_MANAGER_PASSWORD\n"
        f"[bold]Vault path env var:[/bold] ENV_MANAGER_VAULT\n"
        f"[bold]Log level env var:[/bold] ENV_MANAGER_LOG_LEVEL",
        title="env-manager vault info",
    ))


@cli.command("verify")
@click.option("--password", "-p", default="", help="Vault password")
def verify_cmd(password):
    """Verify vault integrity and password without showing any data."""
    if not password:
        password = _get_password()
    try:
        vault = load_vault(password)
        project_count = len(vault.get("envs", {}))
        var_count = sum(len(p.get("vars", {})) for p in vault["envs"].values())
        console.print(f"[green]✓[/green] Vault OK — {project_count} project(s), {var_count} total variable(s)")
    except ValueError as e:
        console.print(f"[red]✗ Vault verification failed:[/red] {e}")
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
