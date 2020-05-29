# -*- coding: utf-8 -*-
"""
Wrappers module contains wrappers to both django object instances modified by an application
"""
import types

from django.core.exceptions import FieldDoesNotExist
from django.db import models

from django_optimizer.iterables import LoggingModelIterable
from django_optimizer.location import ObjectLocation
from django_optimizer.registry import field_registry
from django_optimizer.query import OptimizerQuerySet


def optimizer_query_set_wrapper(model):
    """
    Adds OptimizerQuerySet mixin to queryset instance and modifies queryset objects behaviour

    :param model: model instance which specifies created queryset instance
    :return: wrapped queryset object
    """
    queryset = model.objects.all()

    if not isinstance(queryset, OptimizerQuerySet):
        queryset.__class__ = type(
            'DjangoOptimizer' + type(queryset).__name__,
            (OptimizerQuerySet, type(queryset)),
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
        has_qs = hasattr(obj, '_qs_location')
        to_one = field_obj.one_to_one or field_obj.many_to_one
        no_cache = not hasattr(obj, field_obj.get_cache_name())
        if has_qs and to_one and no_cache:
            field_registry.set_select(obj._qs_location, field_obj.name)

    def _add_prefetch_field(obj, field_obj):
        has_qs = hasattr(obj, '_qs_location')
        to_many = field_obj.one_to_many or field_obj.many_to_many
        no_name = hasattr(obj, '_prefetch_lookup_names') and field_obj.name not in obj._prefetch_lookup_names
        if has_qs and to_many and no_name:
            field_registry.set_prefetch(obj._qs_location, field_obj.name)

    def instance_getattribute(self, item):
        if item not in ['_meta', '__dict__']:
            try:
                field = self._meta.get_field(item)
                is_relation = field.is_relation
                is_field_colname = isinstance(field, models.Field) and item == field.get_attname()
                if is_relation and not is_field_colname:
                    _add_select_field(self, field)
                    _add_prefetch_field(self, field)
            except FieldDoesNotExist:
                pass
        return object.__getattribute__(self, item)

    def refresh_from_db(self, using=None, fields=None):
        missing_fields = [field for field in fields if not hasattr(self.__dict__, field)]
        if missing_fields:
            field_registry.set_only(self._qs_location, *missing_fields)
        super(type(self), self).refresh_from_db(using, fields)

    if not isinstance(model, dict):
        model.instance_getattribute = types.MethodType(instance_getattribute, model)
        model.refresh_from_db = types.MethodType(refresh_from_db, model)

    return model
