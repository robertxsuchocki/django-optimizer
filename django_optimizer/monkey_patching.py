# -*- coding: utf-8 -*-
"""
Monkey patching module needed to overload logging model instance's __getattribute__ method
"""
from django.db import models

from django_optimizer.transaction import DeferredPK


def delayed_getattribute(self, item):
    val = object.__getattribute__(self, item)
    if isinstance(val, DeferredPK):
        val = val.get_value()
    return val


def instance_getattribute(self, key):
    try:
        getter = delayed_getattribute(self, 'instance_getattribute')
        return getter(key)
    except AttributeError:
        return delayed_getattribute(self, key)


models.Model.__getattribute__ = instance_getattribute
