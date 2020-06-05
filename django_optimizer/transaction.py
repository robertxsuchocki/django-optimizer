# -*- coding: utf-8 -*-
"""
Transaction module storing GatheringAtomic context manager,
which delays db saves and tries to perform them later in bulk operations
"""
from django.db import DEFAULT_DB_ALIAS, models, router
from django.db.models.signals import pre_save, post_save
from django.db.transaction import Atomic

from django_optimizer.registry import model_registry


def _get_signal_params(obj, **kwargs):
    params = {
        'sender': obj.__class__,
        'instance': obj,
        'created': True,
        'update_fields': kwargs.get('update_fields'),
        'raw': kwargs.get('raw', False),
        'using': kwargs.get('using', router.db_for_write(obj.__class__, instance=obj))
    }

    return params


def _send_pre_save(obj, **params):
    pre_save.send(**_get_signal_params(obj, **params))


def _send_post_save(obj, **params):
    post_save.send(**_get_signal_params(obj, **params))


class GatheringAtomic(Atomic):
    """
    Atomic block that additionally gathers objects meant to be created/updated
    and tries to minimize amount of sql queries used for that

    All db operations are done on atomic exit (for now)
    """

    def __init__(self, *args, **kwargs):
        super(GatheringAtomic, self).__init__(*args, **kwargs)

    def __enter__(self):
        self._replace()
        super(GatheringAtomic, self).__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        super(GatheringAtomic, self).__exit__(exc_type, exc_value, traceback)
        self._rollback()
        self._perform_db_queries()

    @staticmethod
    def _replace():
        def _gathering_save(obj, **kwargs):
            if obj.id is not None:
                obj._default_save(**kwargs)
            else:
                _send_pre_save(obj, **kwargs)
                model_registry.add(obj)
                _send_post_save(obj, **kwargs)

        models.Model._default_save = models.Model.save
        models.Model.save = _gathering_save

    @staticmethod
    def _rollback():
        models.Model.save = models.Model._default_save
        del models.Model._default_save

    @staticmethod
    def _perform_db_queries():
        for model, objects in model_registry.get_all():
            model.objects.bulk_create(objects)


def gathering_atomic(using=None, savepoint=True):
    if callable(using):
        return GatheringAtomic(DEFAULT_DB_ALIAS, savepoint)(using)
    else:
        return GatheringAtomic(using, savepoint)
