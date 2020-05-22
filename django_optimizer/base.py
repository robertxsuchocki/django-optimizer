# -*- coding: utf-8 -*-
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from django_optimizer.registry import field_registry


class OptimizerModel(models.Model):
    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(OptimizerModel, self).__init__(*args, **kwargs)

    def __getattribute__(self, item):
        if item not in ['_meta', '__dict__']:
            try:
                field = self._meta.get_field(item)
                is_relation = field.is_relation
                is_field_colname = isinstance(field, models.Field) and item == field.get_attname()
                if is_relation and not is_field_colname:
                    self._add_select_field(field)
                    self._add_prefetch_field(field)
            except FieldDoesNotExist:
                pass
        return super(OptimizerModel, self).__getattribute__(item)

    def _add_select_field(self, field):
        has_qs = hasattr(self, '_qs_location')
        to_one = field.one_to_one or field.many_to_one
        no_cache = not hasattr(self, field.get_cache_name())
        if has_qs and to_one and no_cache:
            field_registry.set_select(self._qs_location, field.name)

    def _add_prefetch_field(self, field):
        has_qs = hasattr(self, '_qs_location')
        to_many = field.one_to_many or field.many_to_many
        no_name = hasattr(self, '_prefetch_lookup_names') and field.name not in self._prefetch_lookup_names
        if has_qs and to_many and no_name:
            field_registry.set_prefetch(self._qs_location, field.name)

    def refresh_from_db(self, using=None, fields=None):
        missing_fields = [field for field in fields if not hasattr(self.__dict__, field)]
        if missing_fields:
            field_registry.set_only(self._qs_location, *missing_fields)
        super(OptimizerModel, self).refresh_from_db(using, fields)
