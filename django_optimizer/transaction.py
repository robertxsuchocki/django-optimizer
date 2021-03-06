# -*- coding: utf-8 -*-
"""
Transaction module storing DeferredAtomic context manager,
which delays db saves and tries to perform them later in bulk operations
"""
import copy

from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.transaction import get_connection
from django.utils.functional import partition
from django_bulk_update.helper import bulk_update

from django_optimizer.registry import model_registry


def get_db_instance(obj, with_ref=False, *args):
    instance = copy.copy(obj)
    for attr in ('_queryset', 'instance_getattribute', 'refresh_from_db') + args:
        instance.__dict__.pop(attr, None)
    if with_ref:
        instance._deferred_obj = id(obj)
    return instance


def perform_deferred_db_queries(only_model=None):
    def _without_ids(iterable):
        for i in iterable:
            i.id = None
            yield i

    key = model_registry.get_key_from_model(only_model)
    if not key or model_registry.has_key(key):
        pairs = model_registry.pop_pair(key) if key else model_registry.pop_all()
        for model, objects in pairs:
            to_update, to_create = partition(lambda obj: obj._state.adding, objects)
            model.objects.bulk_create(_without_ids(to_create))
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
    connection_attr_name = 'atomic_block_class'

    def __enter__(self):
        setattr(get_connection(self.using), self.connection_attr_name,  self.__class__.__name__)
        super(DeferredAtomic, self).__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        super(DeferredAtomic, self).__exit__(exc_type, exc_value, traceback)
        delattr(get_connection(self.using), self.connection_attr_name)
        perform_deferred_db_queries()


def deferred_atomic(using=None, savepoint=True):
    if callable(using):
        return DeferredAtomic(DEFAULT_DB_ALIAS, savepoint)(using)
    else:
        return DeferredAtomic(using, savepoint)
