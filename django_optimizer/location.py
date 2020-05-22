# -*- coding: utf-8 -*-
import inspect

from django.conf import settings as django_settings


class ObjectLocation:
    """
    Class for storing information about object location.
    """
    def __init__(self, name):
        """
        Gets values from source code stack frames (file name, function names)
        and passed name to differentiate between different objects.

        :param name: string indicating a type or name for a located object
        """
        self.source = self.get_source()
        if self.source:
            self.file = self.get_file()
            self.scope = self.get_scope()
            self.name = self.get_name(name)

    def __str__(self):
        """
        Joins all fields retrieved in __init__().

        :return: string representation, uniqueness wrt filename, execution scope and passed name
        """
        if self.source:
            return '/'.join([self.file, self.scope, self.name])
        else:
            return ''

    def __bool__(self):
        """
        Tells whether object has any reasonable location in project source code.

        :return: True if there are any source code stack frames
        """
        return bool(self.source)

    @staticmethod
    def get_source():
        """
        Gets full stack, then ignores frames executing libraries' code and frames executing code
        from a file different to last source code frame.

        :return: list of frame objects that execute latest file of source code existing on traceback
        """
        try:
            latest_file_name = [s[1] for s in inspect.stack() if django_settings.BASE_DIR in s[1]][0]
            return [s for s in inspect.stack() if s[1] == latest_file_name]
        except IndexError:
            return []

    def get_file(self):
        _, filename, _, _, _, _ = self.source[0]
        return filename.replace(django_settings.BASE_DIR + '/', '').replace('.py', '')

    def get_scope(self):
        _, filename, _, _, _, _ = self.source[0]
        return '.'.join(reversed([str(s[3]) for s in self.source if s[1] == filename]))

    @staticmethod
    def get_name(name):
        return str(name).lower()
