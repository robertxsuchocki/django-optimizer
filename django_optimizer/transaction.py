# -*- coding: utf-8 -*-
"""
Transaction module storing DeferredAtomic context manager,
which delays db saves and tries to perform them later in bulk operations
"""
import copy

from django.db import DEFAULT_DB_ALIAS, models, router, transaction
from django.utils.functional import partition
from django_bulk_update.helper import bulk_update

from django_optimizer.query import DeferredQuerySet
from django_optimizer.registry import model_registry


def get_db_instance(obj, *args):
    obj = copy.copy(obj)
    for attr in ('_queryset', 'instance_getattribute', 'refresh_from_db') + args:
        obj.__dict__.pop(attr, None)
    return obj


def perform_deferred_db_queries(model=None):
    key = model_registry.get_key_from_model(model)
    if not key or model_registry.has_key(key):
        pairs = model_registry.pop_pair(key) if key else model_registry.pop_all()
        for model, objects in pairs:
            to_update, to_create = partition(lambda obj: obj._state.adding, objects)
            model.objects.bulk_create(to_create)
            bulk_update(to_update)


class DeferredPK(object):
    """
    A wrapper for a deferred pk

    When object's save() is deferred and its pk is accessed before usual bulk create,
    then the insertion query is executed immediately and its pk gets returned
    """
    def __init__(self, instance, *args, **kwargs):
        self.instance = instance
        self.field_name = instance._meta.pk.attname
        super(DeferredPK, self).__init__(*args, **kwargs)

    def _save_and_retrieve_pk(self):
        model = self.instance._meta.model
        db_instance = get_db_instance(self.instance, self.field_name)
        db_instance.pk = None
        db_row = model.objects.bulk_create([db_instance])[0]
        model_registry.delete(db_instance)

        if not hasattr(db_row, self.field_name):
            field_names = [f.name for f in self.instance._meta.get_fields()]
            db_row = model.objects.filter(
                **{field: self.instance.__dict__[field] for field in self.instance.__dict__ if field in field_names}
            ).last()

        field_value = getattr(db_row, self.field_name)
        setattr(self.instance, self.field_name, field_value)

        return field_value

    def get_value(self):
        data = self.instance.__dict__
        if isinstance(data.get(self.field_name, self), DeferredPK):
            data[self.field_name] = self._save_and_retrieve_pk()
        return data[self.field_name]


class DeferredAtomic(transaction.Atomic):
    """
    Atomic block that additionally gathers objects meant to be created/updated
    and tries to minimize amount of sql queries used for that

    All db operations are done on atomic exit (for now)
    """
    @staticmethod
    def _deferred_save(obj, **kwargs):
        def _get_signal_params(obj, **kwargs):
            return {
                'sender': obj.__class__,
                'instance': obj,
                'created': obj._state.adding,
                'update_fields': kwargs.get('update_fields'),
                'raw': kwargs.get('raw', False),
                'using': kwargs.get('using', router.db_for_write(obj.__class__, instance=obj))
            }
        if not isinstance(obj._meta.model.objects.none(), DeferredQuerySet):
            obj._default_save(**kwargs)
        else:
            models.signals.pre_save.send(**_get_signal_params(obj, **kwargs))
            model_registry.add(get_db_instance(obj))
            setattr(obj, obj._meta.pk.attname, DeferredPK(obj))
            models.signals.post_save.send(**_get_signal_params(obj, **kwargs))

    @classmethod
    def _replace_save_method(cls):
        models.Model._default_save = models.Model.save
        models.Model.save = cls._deferred_save

    @classmethod
    def _rollback_save_method(cls):
        models.Model.save = models.Model._default_save
        del models.Model._default_save

    def __enter__(self):
        self._replace_save_method()
        super(DeferredAtomic, self).__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        super(DeferredAtomic, self).__exit__(exc_type, exc_value, traceback)
        self._rollback_save_method()
        perform_deferred_db_queries()


def deferred_atomic(using=None, savepoint=True):
    if callable(using):
        return DeferredAtomic(DEFAULT_DB_ALIAS, savepoint)(using)
    else:
        return DeferredAtomic(using, savepoint)
