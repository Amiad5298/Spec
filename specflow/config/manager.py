"""Configuration manager for SPEC.

This module provides the ConfigManager class for loading, saving, and
managing configuration values with a cascading hierarchy:

    1. Environment Variables (highest priority)
    2. Local Config (.specflow in project/parent directories)
    3. Global Config (~/.specflow-config)
    4. Built-in Defaults (lowest priority)

This enables developers working on multiple projects with different
trackers to have project-specific settings while maintaining global defaults.
"""

import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from specflow.config.settings import CONFIG_FILE, Settings
from specflow.utils.logging import log_message


class ConfigManager:
    """Manages configuration loading and saving with cascading hierarchy.

    Configuration Precedence (highest to lowest):
    1. Environment Variables - CI/CD, temporary overrides
    2. Local Config (.specflow) - Project-specific settings
    3. Global Config (~/.specflow-config) - User defaults
    4. Built-in Defaults - Fallback values

    Security features:
    - Safe line-by-line parsing (no eval/exec)
    - Key name validation
    - Atomic file writes
    - Secure file permissions (600)

    Attributes:
        settings: Current settings instance
        _raw_values: Merged raw key-value pairs from all sources
        _local_config_path: Path to discovered local .specflow file
        _global_config_path: Path to global ~/.specflow-config file
    """

    LOCAL_CONFIG_NAME = ".specflow"
    GLOBAL_CONFIG_NAME = ".specflow-config"

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize the configuration manager.

        Args:
            config_path: Optional custom path to override global config file.
                         If provided, only this file is used (legacy behavior).
        """
        self._legacy_mode = config_path is not None
        self._global_config_path = config_path or CONFIG_FILE
        self._local_config_path: Optional[Path] = None
        self.settings = Settings()
        self._raw_values: dict[str, str] = {}
        # Track source of each config value for debugging
        self._config_sources: dict[str, str] = {}

    @property
    def config_path(self) -> Path:
        """Return the primary config path (for backward compatibility)."""
        return self._global_config_path

    @config_path.setter
    def config_path(self, value: Path) -> None:
        """Set the global config path."""
        self._global_config_path = value

    def load(self) -> Settings:
        """Load configuration from all sources with cascading precedence.

        Loading order (later sources override earlier ones):
        1. Built-in defaults (from Settings dataclass)
        2. Global config (~/.specflow-config)
        3. Local config (.specflow in project/parent directories)
        4. Environment variables (highest priority)

        Security: Uses safe line-by-line parsing instead of eval/exec.
        Only reads KEY=VALUE or KEY="VALUE" pairs.

        Returns:
            Settings instance with loaded values
        """
        self._raw_values = {}
        self._config_sources = {}

        # Step 1: Start with built-in defaults (from Settings dataclass)
        # The Settings dataclass already has defaults, nothing to do here

        # Step 2: Load global config (~/.specflow-config) - lowest file-based priority
        if self._global_config_path.exists():
            log_message(f"Loading global configuration from {self._global_config_path}")
            self._load_file(self._global_config_path, source="global")
        else:
            log_message(f"No global configuration file found at {self._global_config_path}")

        # Step 3: Load local config (.specflow) - higher priority, unless in legacy mode
        if not self._legacy_mode:
            local_path = self._find_local_config()
            if local_path:
                self._local_config_path = local_path
                log_message(f"Loading local configuration from {local_path}")
                self._load_file(local_path, source=f"local ({local_path})")

        # Step 4: Environment variables override everything
        self._load_environment()

        # Apply all values to settings
        for key, value in self._raw_values.items():
            self._apply_value_to_settings(key, value)

        log_message(f"Configuration loaded successfully ({len(self._raw_values)} keys)")
        return self.settings

    def _find_local_config(self) -> Optional[Path]:
        """Find local .specflow config by traversing up from CWD.

        Starts from current working directory and traverses parent
        directories until:
        - A .specflow file is found
        - A .git directory is found (repository root)
        - The filesystem root is reached

        Returns:
            Path to local config file, or None if not found
        """
        current = Path.cwd()
        while True:
            config_path = current / self.LOCAL_CONFIG_NAME
            if config_path.exists():
                return config_path

            # Stop at repository root
            if (current / ".git").exists():
                break

            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent

        return None

    def _load_file(self, path: Path, source: str = "file") -> None:
        """Load key=value pairs from a config file.

        Args:
            path: Path to the config file
            source: Source identifier for debugging
        """
        pattern = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$")

        with path.open() as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                match = pattern.match(line)
                if match:
                    key, value = match.groups()

                    # Remove surrounding quotes
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]

                    self._raw_values[key] = value
                    self._config_sources[key] = source

    def _load_environment(self) -> None:
        """Override config with environment variables.

        Only loads environment variables for known config keys
        to avoid polluting the configuration with unrelated env vars.
        """
        known_keys = Settings.get_config_keys()
        for key in known_keys:
            env_value = os.environ.get(key)
            if env_value is not None:
                self._raw_values[key] = env_value
                self._config_sources[key] = "environment"

    def _apply_value_to_settings(self, key: str, value: str) -> None:
        """Apply a raw config value to the settings object.

        Args:
            key: Configuration key
            value: Raw string value from file
        """
        attr = self.settings.get_attribute_for_key(key)
        if attr is None:
            return  # Unknown key, ignore

        # Get the expected type from the settings dataclass
        current_value = getattr(self.settings, attr)

        if isinstance(current_value, bool):
            # Parse boolean values
            setattr(self.settings, attr, value.lower() in ("true", "1", "yes"))
        elif isinstance(current_value, int):
            # Parse integer values
            try:
                setattr(self.settings, attr, int(value))
            except ValueError:
                pass  # Keep default on parse error
        else:
            # String values - extract model ID for model-related keys
            if key in ("DEFAULT_MODEL", "PLANNING_MODEL", "IMPLEMENTATION_MODEL"):
                from specflow.integrations.auggie import extract_model_id
                value = extract_model_id(value)
            setattr(self.settings, attr, value)

    def save(self, key: str, value: str) -> None:
        """Save a configuration value to file.

        Security: Validates key name, uses atomic file replacement.

        Args:
            key: Configuration key (alphanumeric + underscore)
            value: Configuration value

        Raises:
            ValueError: If key name is invalid
        """
        # Validate key name
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
            raise ValueError(f"Invalid config key: {key}")

        # Update in-memory values
        self._raw_values[key] = value
        self._apply_value_to_settings(key, value)

        # Read existing file content
        existing_lines: list[str] = []
        if self.config_path.exists():
            existing_lines = self.config_path.read_text().splitlines()

        # Build new file content
        new_lines: list[str] = []
        written_keys: set[str] = set()
        key_pattern = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)=")

        for line in existing_lines:
            # Preserve comments and empty lines
            if not line.strip() or line.strip().startswith("#"):
                new_lines.append(line)
                continue

            match = key_pattern.match(line)
            if match:
                existing_key = match.group(1)
                if existing_key in self._raw_values:
                    # Write updated value
                    new_lines.append(f'{existing_key}="{self._raw_values[existing_key]}"')
                    written_keys.add(existing_key)
                else:
                    # Preserve unknown keys
                    new_lines.append(line)
            else:
                # Preserve malformed lines
                new_lines.append(line)

        # Add new keys not in file
        for k, v in self._raw_values.items():
            if k not in written_keys:
                new_lines.append(f'{k}="{v}"')

        # Atomic write using temp file
        self._atomic_write(new_lines)
        log_message(f"Configuration saved: {key}={value}")

    def _atomic_write(self, lines: list[str]) -> None:
        """Atomically write lines to config file.

        Args:
            lines: Lines to write
        """
        # Create temp file in same directory for atomic move
        fd, temp_path = tempfile.mkstemp(
            dir=self.config_path.parent,
            prefix=".specflow-config-",
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write("\n".join(lines))
                if lines:
                    f.write("\n")

            # Set secure permissions before moving
            os.chmod(temp_path, 0o600)

            # Atomic replace
            Path(temp_path).replace(self.config_path)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def get(self, key: str, default: str = "") -> str:
        """Get a configuration value.

        Args:
            key: Configuration key to retrieve
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._raw_values.get(key, default)

    def get_config_source(self, key: str) -> str:
        """Return the source of a configuration value (for debugging).

        Args:
            key: Configuration key

        Returns:
            Source identifier: "environment", "local (/path)", "global (/path)",
            or "default" if the value comes from built-in defaults.
        """
        if key in self._config_sources:
            return self._config_sources[key]
        return "default"

    def get_local_config_path(self) -> Optional[Path]:
        """Return the discovered local config path, if any."""
        return self._local_config_path

    def get_global_config_path(self) -> Path:
        """Return the global config path."""
        return self._global_config_path

    def show(self) -> None:
        """Display current configuration using Rich formatting."""
        from specflow.utils.console import console, print_header, print_info

        print_header("Current Configuration")

        # Show config file locations
        print_info(f"Global config: {self._global_config_path}")
        if self._local_config_path:
            print_info(f"Local config:  {self._local_config_path}")
        else:
            print_info("Local config:  (not found)")
        console.print()

        s = self.settings
        console.print(f"  Default Model (Legacy): {s.default_model or '(not set)'}")
        console.print(f"  Planning Model: {s.planning_model or '(not set)'}")
        console.print(f"  Implementation Model: {s.implementation_model or '(not set)'}")
        console.print(f"  Default Jira Project: {s.default_jira_project or '(not set)'}")
        console.print(f"  Auto-open Files: {s.auto_open_files}")
        console.print(f"  Preferred Editor: {s.preferred_editor or '(auto-detect)'}")
        console.print(f"  Skip Clarification: {s.skip_clarification}")
        console.print(f"  Squash Commits at End: {s.squash_at_end}")
        console.print()
        console.print("  [bold]Parallel Execution:[/bold]")
        console.print(f"    Enabled: {s.parallel_execution_enabled}")
        console.print(f"    Max Parallel Tasks: {s.max_parallel_tasks}")
        console.print(f"    Fail Fast: {s.fail_fast}")
        console.print()
        console.print("  [bold]Subagents:[/bold]")
        console.print(f"    Planner: {s.subagent_planner}")
        console.print(f"    Tasklist: {s.subagent_tasklist}")
        console.print(f"    Implementer: {s.subagent_implementer}")
        console.print(f"    Reviewer: {s.subagent_reviewer}")
        console.print()


__all__ = [
    "ConfigManager",
]

