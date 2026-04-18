# env-manager

![Python](https://img.shields.io/badge/python-3.10+-blue) ![Encryption](https://img.shields.io/badge/encryption-AES--128-green) ![Tests](https://img.shields.io/badge/tests-52%20passing-brightgreen) ![License](https://img.shields.io/badge/license-MIT-orange)

CLI para gestionar variables de entorno entre proyectos con encriptación AES (Fernet). Guarda todas las `.env` de tus proyectos en un vault cifrado con contraseña. Exporta, importa y accede a cada variable de forma segura.

## Instalacion en 3 comandos

```bash
git clone https://github.com/Quesillo27/env-manager
cd env-manager
pip install -e .
```

## Uso rapido

```bash
# Agregar variables al vault
env-manager set myapp DB_HOST localhost
env-manager set myapp DB_PASSWORD s3cr3t

# Ver proyectos guardados
env-manager list

# Mostrar variables de un proyecto
env-manager show myapp

# Mostrar valores reales (por defecto quedan ocultos)
env-manager show myapp --reveal

# Exportar a archivo .env
env-manager export myapp -o .env

# Importar desde .env existente
env-manager import myapp .env.production

# Ejecutar un comando con las vars inyectadas
env-manager run myapp -- python manage.py migrate
```

## Comandos disponibles

| Comando | Descripcion |
|---------|-------------|
| `list` | Lista todos los proyectos (`--json` para scripting) |
| `show <project>` | Muestra variables (`--reveal` para ver valores, `--json` para scripting) |
| `set <project> KEY value` | Agrega/actualiza una variable |
| `get <project> KEY` | Obtiene valor raw (para scripting) |
| `delete <project> KEY` | Elimina una variable |
| `delete <project> --project-only` | Elimina el proyecto completo (pide confirmacion) |
| `describe <project> <text>` | Agrega descripcion al proyecto |
| `copy <source> <dest>` | Copia todas las vars de un proyecto a otro |
| `rename <old> <new>` | Renombra un proyecto |
| `run <project> -- <cmd>` | Ejecuta comando con las vars inyectadas como env |
| `export <project>` | Exporta a formato .env (`-o file` para guardar a archivo) |
| `import <project> <file>` | Importa desde archivo .env (soporta formato `export KEY=val`) |
| `info` | Muestra ubicacion y estado del vault |
| `verify` | Verifica integridad del vault y password |

## Ejemplo de flujo

```bash
$ env-manager set api JWT_SECRET my-super-secret
Vault password:
✓ Set JWT_SECRET in api

$ env-manager list --json
[
  {
    "name": "api",
    "count": 1,
    "description": ""
  }
]

$ env-manager copy api api-staging
✓ Copied 1 variable(s) from api to api-staging

$ env-manager run api -- node server.js
# El proceso corre con JWT_SECRET en su entorno
```

## Variables de entorno del CLI

| Variable | Descripcion |
|----------|-------------|
| `ENV_MANAGER_PASSWORD` | Password del vault (evita el prompt interactivo) |
| `ENV_MANAGER_VAULT` | Ruta personalizada del archivo vault (default: `~/.env-manager/vault.enc`) |
| `ENV_MANAGER_LOG_LEVEL` | Nivel de logging: `DEBUG`, `INFO`, `WARNING` (default: `WARNING`) |

## Validacion

Las keys deben seguir el formato de variables de entorno: `[A-Z_][A-Z0-9_]*` (mayusculas, digitos y guion bajo). El CLI rechaza keys invalidas antes de cifrar.

## Seguridad

- Encriptacion: **Fernet (AES-128-CBC + HMAC-SHA256)**
- KDF: **PBKDF2-HMAC-SHA256** con 390,000 iteraciones + sal aleatoria de 16 bytes
- Vault en: `~/.env-manager/vault.enc` (permisos 600, directorio 700)
- Los valores nunca se muestran en texto plano salvo con `--reveal`
- Keys invalidas (minusculas, espacios) son rechazadas en la entrada

## Tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## Roadmap

- Vault remoto (S3, GCS) para backup automatico
- Team sharing con claves publicas por miembro
- Integracion con `git-secrets` para pre-commit hooks
- Rotacion de password del vault sin re-encriptar manualmente
- Soporte para multiples vaults (perfiles)
