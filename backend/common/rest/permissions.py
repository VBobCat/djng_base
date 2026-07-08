from copy import deepcopy

from rest_framework import permissions


class AlwaysDenied(permissions.BasePermission):
    def has_permission(self, request, view):
        return False

    def has_object_permission(self, request, view, obj):
        return False


class UserAuthLinkSettings(permissions.IsAuthenticated):
    message = 'Usuário sem permissões específicas para esta ação.'

    @staticmethod
    def _check_auth_link_settings(request, view):
        user_settings = request.user.auth_link.get_settings()
        view_settings = getattr(view, 'user_auth_link_settings', {})
        if all(user_settings.get(k) == v for k, v in view_settings.items()):
            action = getattr(view, 'action', request.method.lower())
            view_action_settings = view_settings.get(action, {})
            return all(user_settings.get(k) == v for k, v in view_action_settings.items())
        return False

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return self._check_auth_link_settings(request, view)
        return False

    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return self._check_auth_link_settings(request, view)
        return False


class DjangoModelCustomPermissions(permissions.DjangoModelPermissions):

    @classmethod
    def with_permissions(cls, name: str, perms_map: dict, merge: bool = False):
        new_perms_map = {k: list(v) for k, v in cls.perms_map.items()}
        for k, v in perms_map.items():
            if merge:
                # Exigirá a permissão original E a nova
                new_perms_map[k] = list(set(new_perms_map.setdefault(k, []) + v))
            else:
                # Substituirá a permissão original pela nova
                new_perms_map[k] = v

        return type(
            f'DjangoModel{name.capitalize()}Permissions',
            (cls,),
            {'perms_map': new_perms_map},
        )


class HasPermissions(permissions.BasePermission):
    required_permissions = []

    def has_permission(self, request, view):
        if not self.required_permissions:
            return True
        return hasattr(request.user, 'has_perms') and request.user.has_perms(self.required_permissions)

    @classmethod
    def to(cls, *perms: str):
        suffix = ''.join(p.replace('.', '_').title().replace('_', '') for p in perms)
        return type(
            f'HasPermissionsTo{suffix}',
            (cls,),
            {'required_permissions': list(perms)},
        )
