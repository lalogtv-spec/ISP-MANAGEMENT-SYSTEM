"""Project startup compatibility hooks."""

from copy import copy as _copy


def _patch_django_context_copy():
    """
    Django 4.2's BaseContext.__copy__ is not compatible with the Python 3.14
    test environment used here. Patch it with a direct object copy so the test
    client can safely snapshot template contexts.
    """
    try:
        from django.template.context import BaseContext, Context
    except Exception:
        return

    def _safe_base_context_copy(self):
        duplicate = object.__new__(self.__class__)
        if hasattr(self, '__dict__'):
            duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    def _safe_context_copy(self):
        duplicate = _safe_base_context_copy(self)
        duplicate.render_context = _copy(self.render_context)
        return duplicate

    BaseContext.__copy__ = _safe_base_context_copy
    Context.__copy__ = _safe_context_copy


_patch_django_context_copy()
