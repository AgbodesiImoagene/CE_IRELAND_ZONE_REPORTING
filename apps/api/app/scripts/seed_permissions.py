from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, Set
from uuid import UUID, uuid4

from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from app.common.db import SessionLocal
from app.common.models import Permission, Role, RolePermission

CSV_FILENAME = "permissions_matrix.csv"

CSV_CANDIDATE_PATHS = [
    # app/resources (primary)
    Path(__file__).resolve().parent.parent / "resources" / CSV_FILENAME,
    # optional copied (legacy)
    Path(__file__).resolve().parents[1] / "seed_data" / CSV_FILENAME,
]


def find_csv_path() -> Path:
    override = os.getenv("PERMISSIONS_CSV_PATH")
    if override:
        p = Path(override)
        if p.exists():
            return p
    for p in CSV_CANDIDATE_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"{CSV_FILENAME} not found. Set PERMISSIONS_CSV_PATH env var "
        "or place it in app/resources/, or app/seed_data/"
    )


def load_matrix(csv_path: Path) -> Dict[str, Dict[str, bool]]:
    role_to_perms: Dict[str, Dict[str, bool]] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            role = row["role_name"].strip()
            perm = row["permission"].strip()
            granted = row["default_granted"].strip().upper() in {"TRUE", "1", "YES"}
            role_to_perms.setdefault(role, {})[perm] = granted
    return role_to_perms


def ensure_permissions(db: Session, permissions: Set[str]) -> None:
    existing = {p.code for p in db.execute(select(Permission)).scalars().all()}
    to_create = permissions - existing
    if to_create:
        db.execute(
            insert(Permission),
            [
                {"id": uuid4(), "code": code, "description": None}
                for code in sorted(to_create)
            ],
        )


def ensure_roles(db: Session, tenant_id: str, roles: Set[str]) -> Dict[str, str]:
    tenant_uuid = UUID(tenant_id)
    existing_rows = db.execute(
        select(Role.name, Role.id).where(Role.tenant_id == tenant_uuid)
    ).all()
    existing = {name: str(id_) for name, id_ in existing_rows}
    created: Dict[str, str] = {}
    for name in sorted(roles):
        if name in existing:
            continue
        rid = uuid4()
        db.add(Role(id=rid, tenant_id=tenant_uuid, name=name))
        created[name] = str(rid)
    db.flush()
    # refresh mapping
    rows = db.execute(
        select(Role.name, Role.id).where(Role.tenant_id == tenant_uuid)
    ).all()
    return {name: str(id_) for name, id_ in rows}


def ensure_role_permissions(
    db: Session,
    role_name_to_id: Dict[str, str],
    role_to_perms: Dict[str, Dict[str, bool]],
):
    # Fetch permission id map
    perm_rows = db.execute(select(Permission.code, Permission.id)).all()
    perm_code_to_id = {code: str(pid) for code, pid in perm_rows}

    # Build desired assignments (only where granted==True)
    desired = set()
    for role_name, perms in role_to_perms.items():
        for code, granted in perms.items():
            if granted:
                rid = role_name_to_id.get(role_name)
                pid = perm_code_to_id.get(code)
                if rid and pid:
                    desired.add((rid, pid))

    # Load existing
    existing_rows = db.execute(
        select(RolePermission.role_id, RolePermission.permission_id)
    ).all()
    existing = {(str(rid), str(pid)) for rid, pid in existing_rows}

    to_add = desired - existing
    if to_add:
        db.execute(
            insert(RolePermission),
            [
                {"role_id": UUID(rid), "permission_id": UUID(pid)}
                for rid, pid in sorted(to_add)
            ],
        )


def main():
    tenant_id = os.getenv("TENANT_ID")
    if not tenant_id:
        raise RuntimeError("TENANT_ID env var is required")

    csv_path = find_csv_path()
    matrix = load_matrix(csv_path)

    all_perms = {perm for perms in matrix.values() for perm in perms.keys()}
    role_names = set(matrix.keys())

    with SessionLocal() as db:
        db.begin()
        ensure_permissions(db, all_perms)
        role_name_to_id = ensure_roles(db, tenant_id, role_names)
        ensure_role_permissions(db, role_name_to_id, matrix)
        db.commit()
    print(
        f"Seeded {len(role_names)} roles and {len(all_perms)} permissions from {csv_path}"
    )


if __name__ == "__main__":
    main()
