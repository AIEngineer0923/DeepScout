#!/usr/bin/env python3
"""Seed the operator BYOK vault from maintainer env keys (hosted only)."""

from __future__ import annotations

import argparse
import sys

from deepscout_core.settings import Settings
from deepscout_persistence.identity import get_auth_provider_account_id, get_principal
from deepscout_persistence.session import get_session_factory
from deepscout_research.credentials.operator_vault import sync_operator_vault_from_env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--principal-id",
        help="Operator principal UUID. Defaults to lookup via MAINTAINER_VAULT_GITHUB_ID.",
    )
    args = parser.parse_args()
    settings = Settings()
    if not settings.is_hosted():
        print("operator vault sync requires DEEPSCOUT_DEPLOYMENT_MODE=hosted", file=sys.stderr)
        return 1
    maintainer_id = (settings.maintainer_vault_github_id or "").strip()
    if not maintainer_id:
        print("MAINTAINER_VAULT_GITHUB_ID is not set", file=sys.stderr)
        return 1
    session = get_session_factory(settings.database_url)()
    try:
        if args.principal_id:
            from uuid import UUID

            principal_id = UUID(args.principal_id)
            principal = get_principal(session, principal_id)
            if principal is None:
                print(f"principal not found: {principal_id}", file=sys.stderr)
                return 1
            github_id = get_auth_provider_account_id(session, principal_id, "github")
            if github_id != maintainer_id:
                print("principal is not the configured operator github account", file=sys.stderr)
                return 1
        else:
            from deepscout_persistence.models import AuthAccountRow
            from sqlalchemy import select

            principal_id = session.scalar(
                select(AuthAccountRow.principal_id).where(
                    AuthAccountRow.provider == "github",
                    AuthAccountRow.provider_account_id == maintainer_id,
                )
            )
            if principal_id is None:
                print(
                    f"no github principal found for MAINTAINER_VAULT_GITHUB_ID={maintainer_id}",
                    file=sys.stderr,
                )
                return 1
        synced = sync_operator_vault_from_env(session, principal_id, settings)
        session.commit()
        print(f"synced providers: {', '.join(synced) if synced else '(none)'}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
