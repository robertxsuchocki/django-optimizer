# -*- coding: utf-8 -*-
"""
Transaction module storing DelayedAtomic context manager,
which delays db saves and tries to perform them later in bulk operations
"""
import copy

from django.db import DEFAULT_DB_ALIAS, models, router, transaction
from django.utils.functional import partition
from django_bulk_update.helper import bulk_update

from django_optimizer.query import OptimizerQuerySet
from django_optimizer.registry import model_registry


def _get_signal_params(obj, **kwargs):
    params = {
        'sender': obj.__class__,
        'instance': obj,
        'created': obj._state.adding,
        'update_fields': kwargs.get('update_fields'),
        'raw': kwargs.get('raw', False),
        'using': kwargs.get('using', router.db_for_write(obj.__class__, instance=obj))
    }

    return params


def replace_save_method():
    def _delayed_save(self, **kwargs):
        def _get_db_copy(obj):
            copy_obj = copy.copy(obj)
            for attr in ('_queryset', 'instance_getattribute', 'refresh_from_db'):
                copy_obj.__dict__.pop(attr, None)
            return copy_obj

        if not isinstance(self._meta.model.objects.none(), OptimizerQuerySet):
            self._default_save(**kwargs)
        else:
            models.signals.pre_save.send(**_get_signal_params(self, **kwargs))
            model_registry.add(_get_db_copy(self))
            models.signals.post_save.send(**_get_signal_params(self, **kwargs))

    models.Model._default_save = models.Model.save
    models.Model.save = _delayed_save


def rollback_save_method():
    models.Model.save = models.Model._default_save
    del models.Model._default_save


def perform_delayed_db_queries(key=None):
    if not key or model_registry.has_key(key):
        pairs = model_registry.pop_pair(key) if key else model_registry.pop_all()
        for model, objects in pairs:
            to_update, to_create = partition(lambda obj: obj._state.adding, objects)
            model.objects.bulk_create(to_create)
            bulk_update(to_update)


class DelayedAtomic(transaction.Atomic):
    """
    Atomic block that additionally gathers objects meant to be created/updated
    and tries to minimize amount of sql queries used for that

    All db operations are done on atomic exit (for now)
    """

    def __init__(self, *args, **kwargs):
        super(DelayedAtomic, self).__init__(*args, **kwargs)

    def __enter__(self):
        replace_save_method()
        super(DelayedAtomic, self).__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        super(DelayedAtomic, self).__exit__(exc_type, exc_value, traceback)
        rollback_save_method()
        perform_delayed_db_queries()


def delayed_atomic(using=None, savepoint=True):
    if callable(using):
        return DelayedAtomic(DEFAULT_DB_ALIAS, savepoint)(using)
    else:
        return DelayedAtomic(using, savepoint)
