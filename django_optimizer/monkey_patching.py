# -*- coding: utf-8 -*-
"""
Monkey patching module needed to overload logging model instance's __getattribute__ method
"""
from django.db import models


def instance_getattribute(self, key):
    try:
        getter = object.__getattribute__(self, 'instance_getattribute')
        return getter(key)
    except AttributeError:
        return object.__getattribute__(self, key)


models.Model.__getattribute__ = instance_getattribute
