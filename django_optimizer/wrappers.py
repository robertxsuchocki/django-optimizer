# -*- coding: utf-8 -*-
"""
Wrappers module contains wrappers to both django object instances modified by an application
"""
import types

from django.core.exceptions import FieldDoesNotExist
from django.db import models

from django_optimizer.iterables import LoggingModelIterable
from django_optimizer.location import ObjectLocation
from django_optimizer.query import SelectiveQuerySet


def selective_query_set_wrapper(model):
    """
    Adds SelectiveQuerySet mixin to queryset instance and modifies queryset objects behaviour

    :param model: model instance which specifies created queryset instance
    :return: wrapped queryset object
    """
    queryset = model.objects.all()

    if not isinstance(queryset, SelectiveQuerySet):
        queryset.__class__ = type(
            'DjangoSelective' + type(queryset).__name__,
            (SelectiveQuerySet, type(queryset)),
            {}
        )
        # __init__ instructions have to be run explicitly
        queryset._location = ObjectLocation(queryset.model.__name__)
        queryset._iterable_class = LoggingModelIterable

    return queryset


def logging_model_wrapper(model):
    """
    Adds modified `__getattribute__` and `refresh_from_db` definitions to model instance

    :param model: input model instance
    :return: wrapped object
    """
    def _add_select_field(obj, field_obj):
        to_one = field_obj.one_to_one or field_obj.many_to_one
        no_cache = not hasattr(obj, field_obj.get_cache_name())
        if to_one and no_cache:
            obj._queryset._add_select(field_obj.name)

    def _add_prefetch_field(obj, field_obj):
        to_many = field_obj.one_to_many or field_obj.many_to_many
        prefetch_lookup_names = [
            getattr(lookup, 'prefetch_through', str(lookup))
            for lookup in obj._queryset._prefetch_related_lookups
        ]
        no_name = field_obj.name not in prefetch_lookup_names
        if to_many and no_name:
            obj._queryset._add_prefetch(field_obj.name)

    def _add_related_field(obj, field_obj, item):
        is_relation = field_obj.is_relation
        is_field_colname = item == field_obj.get_attname()
        if is_relation and not is_field_colname:
            _add_select_field(obj, field_obj)
            _add_prefetch_field(obj, field_obj)

    def _add_value_field(obj, item):
        if obj._queryset._without_only:
            obj._queryset._add_only(item)

    def instance_getattribute(self, item):
        if item != 'id' and not item.startswith('_'):
            try:
                field = self._meta.get_field(item)
                if isinstance(field, models.Field):
                    _add_value_field(self, item)
                    _add_related_field(self, field, item)
            except FieldDoesNotExist:
                pass
        return object.__getattribute__(self, item)

    def refresh_from_db(self, using=None, fields=None):
        if fields:
            for field in fields:
                self._queryset._add_only(field)
        super(type(self), self).refresh_from_db(using, fields)

    if not isinstance(model, dict):
        model.instance_getattribute = types.MethodType(instance_getattribute, model)
        model.refresh_from_db = types.MethodType(refresh_from_db, model)

    return model
