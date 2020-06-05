# -*- coding: utf-8 -*-
"""
Transaction module storing GatheringAtomic context manager,
which delays db saves and tries to perform them later in bulk operations
"""
from django.db import DEFAULT_DB_ALIAS, models
from django.db.transaction import Atomic

from django_optimizer.registry import model_registry


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
                model_registry.add(obj)

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
