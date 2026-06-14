"""User domain: roles and the RBAC permission matrix.

This module is pure business logic — it imports no framework. The permission
matrix is the single source of truth driving authorisation (PLAN §3.3); views
check against it via a decorator rather than scattering role checks.
"""
from __future__ import annotations

import enum


class Role(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class Permission(str, enum.Enum):
    # Self-service (all roles)
    CHANGE_OWN_PASSWORD = "change_own_password"
    USE_CHAT = "use_chat"
    MANAGE_OWN_CHATS = "manage_own_chats"

    # Admin tier
    CREATE_USER = "create_user"            # create role=user
    LIST_USERS = "list_users"
    TOGGLE_USER_ACTIVE = "toggle_user_active"        # activate/deactivate role=user

    # Super-admin tier
    CREATE_ADMIN = "create_admin"          # create role=admin
    TOGGLE_ADMIN_ACTIVE = "toggle_admin_active"      # activate/deactivate role=admin
    PROMOTE_USER_TO_ADMIN = "promote_user_to_admin"
    EXPORT_ALL_CHATS = "export_all_chats"


# Single source of truth: Permission -> roles that hold it (PLAN §1.2 matrix).
PERMISSION_MATRIX: dict[Permission, frozenset[Role]] = {
    Permission.CHANGE_OWN_PASSWORD: frozenset({Role.USER, Role.ADMIN, Role.SUPER_ADMIN}),
    Permission.USE_CHAT: frozenset({Role.USER, Role.ADMIN, Role.SUPER_ADMIN}),
    Permission.MANAGE_OWN_CHATS: frozenset({Role.USER, Role.ADMIN, Role.SUPER_ADMIN}),
    Permission.CREATE_USER: frozenset({Role.ADMIN, Role.SUPER_ADMIN}),
    Permission.LIST_USERS: frozenset({Role.ADMIN, Role.SUPER_ADMIN}),
    Permission.TOGGLE_USER_ACTIVE: frozenset({Role.ADMIN, Role.SUPER_ADMIN}),
    Permission.CREATE_ADMIN: frozenset({Role.SUPER_ADMIN}),
    Permission.TOGGLE_ADMIN_ACTIVE: frozenset({Role.SUPER_ADMIN}),
    Permission.PROMOTE_USER_TO_ADMIN: frozenset({Role.SUPER_ADMIN}),
    Permission.EXPORT_ALL_CHATS: frozenset({Role.SUPER_ADMIN}),
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    return role in PERMISSION_MATRIX.get(permission, frozenset())
