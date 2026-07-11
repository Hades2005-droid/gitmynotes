#!/usr/bin/env python3
"""
Bootstrap script for NWW Asana Connector.
Creates workspace, portfolios, projects, and custom fields in Asana.

Usage:
    python bootstrap.py --token <ASANA_TOKEN> --workspace <WORKSPACE_ID>
"""

import argparse
import sys
import os
from typing import Optional
from .client import AsanaClient
from .config import AsanaConfig
from .portfolio_manager import PortfolioManager


def bootstrap_asana_workspace(
    api_token: str,
    workspace_id: str,
    verbose: bool = True,
) -> dict:
    """
    Bootstrap the complete NWW Asana setup.

    Args:
        api_token: Asana Personal Access Token
        workspace_id: Workspace GID
        verbose: Print progress

    Returns:
        Configuration dict with all created resource IDs
    """
    if verbose:
        print("🔮 Initializing NWW Asana Connector Bootstrap...")
        print(f"   Workspace: {workspace_id}\n")

    try:
        # Test connection
        client = AsanaClient(api_token, workspace_id)
        if not client.test_connection():
            print("❌ Connection test failed. Check API token and workspace ID.")
            sys.exit(1)

        if verbose:
            print("✅ Connected to Asana\n")

        # Initialize portfolio manager
        manager = PortfolioManager(client)

        # Create portfolio hierarchy
        if verbose:
            print("Creating portfolio hierarchy...")
        portfolio_ids = manager.create_nww_portfolio_hierarchy()
        if verbose:
            print(f"✅ Created {len(portfolio_ids)} portfolios\n")

        # Create projects
        if verbose:
            print("Creating projects...")
        project_ids = manager.create_nww_projects()
        if verbose:
            print(f"✅ Created {len(project_ids)} projects\n")

        # Create custom fields
        if verbose:
            print("Creating custom fields...")
        field_ids = manager.create_custom_fields()
        if verbose:
            print(f"✅ Created {len(field_ids)} custom fields\n")

        # Export configuration
        config = manager.export_configuration(portfolio_ids, project_ids, field_ids)

        if verbose:
            manager.print_setup_summary(portfolio_ids, project_ids, field_ids)

        return config

    except Exception as e:
        print(f"❌ Bootstrap failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def save_config(config: dict, output_file: str):
    """Save configuration to a file."""
    import json
    with open(output_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"📄 Configuration saved to {output_file}")


def main():
    """CLI entry point for bootstrap."""
    parser = argparse.ArgumentParser(
        description="Bootstrap NWW Asana Connector workspace"
    )
    parser.add_argument(
        "--token",
        help="Asana Personal Access Token (or set ASANA_API_TOKEN env var)",
        default=os.getenv("ASANA_API_TOKEN"),
    )
    parser.add_argument(
        "--workspace",
        help="Asana Workspace ID/GID (or set ASANA_WORKSPACE_ID env var)",
        default=os.getenv("ASANA_WORKSPACE_ID"),
    )
    parser.add_argument(
        "--output",
        help="Save config to JSON file",
        default=None,
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Validate required args
    if not args.token:
        print("❌ Error: --token required or set ASANA_API_TOKEN env var")
        sys.exit(1)

    if not args.workspace:
        print("❌ Error: --workspace required or set ASANA_WORKSPACE_ID env var")
        sys.exit(1)

    # Run bootstrap
    config = bootstrap_asana_workspace(
        api_token=args.token,
        workspace_id=args.workspace,
        verbose=not args.quiet,
    )

    # Save config if requested
    if args.output:
        save_config(config, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
