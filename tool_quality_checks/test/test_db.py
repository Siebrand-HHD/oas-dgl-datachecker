# -*- coding: utf-8 -*-
"""Tests for db.py"""
import os
import pytest

from OASDGLDatachecker.tool_quality_checks.quality_checks import settingsObject
from OASDGLDatachecker.tool_quality_checks.db import (
    ThreediDatabase,
    create_database,
    drop_database,
)

from unittest import TestCase


_ini_relpath = "data/instellingen_test.ini"
INI_ABSPATH = os.path.join(os.path.dirname(__file__), _ini_relpath)


def test_create_database():
    settings = settingsObject(INI_ABSPATH)
    try:
        drop_database(settings)
    except Exception:
        pass
    create_database(settings)


def test_drop_database():
    settings = settingsObject(INI_ABSPATH)
    drop_database(settings)


def test_init_threedidatabase():
    settings = settingsObject(INI_ABSPATH)
    create_database(settings)
    ThreediDatabase(settings)
    drop_database(settings)


def test_init_threedidatabase_raise():
    settings = settingsObject(INI_ABSPATH)
    settings.database = "unkown"
    with pytest.raises(Exception):
        ThreediDatabase(settings)


class TestCreateDB(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = settingsObject(INI_ABSPATH)
        create_database(cls.settings)
        cls.db = ThreediDatabase(cls.settings)

    @classmethod
    def tearDownClass(cls):
        cls.db.conn.close()
        drop_database(cls.settings)

    def test_01_create_extension(self):
        self.db.create_extension(extension_name="postgis")

    def test_02_initialize_db_threedi(self):
        self.db.initialize_db_threedi()

    def test_03_initialize_db_checks(self):
        self.db.initialize_db_checks()


class TestDB(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = settingsObject(INI_ABSPATH)
        create_database(cls.settings)
        cls.db = ThreediDatabase(cls.settings)
        cls.db.create_extension(extension_name="postgis")
        cls.db.initialize_db_threedi()
        cls.db.initialize_db_checks()

    @classmethod
    def tearDownClass(cls):
        cls.db.conn.close()
        drop_database(cls.settings)

    def test_get_count(self):
        assert self.db.get_count("v2_manhole") >= 0

    def test_get_count_raise(self):
        with pytest.raises(Exception):
            self.db.get_count("unknown")

    def test_execute_sql_statement(self):
        self.db.execute_sql_statement("SELECT * FROM v2_manhole")

    def test_execute_sql_statement_raise(self):
        with pytest.raises(Exception):
            self.db.execute_sql_statement("SELECT * FROM unknown")

    def test_select_table_names(self):
        result = self.db.select_table_names("v2%")
        assert "v2_manhole" in result

    def test_create_schema(self):
        self.db.create_schema(schema_name="chk", drop_schema=True)

    def test_populate_geometry_columns(self):
        self.db.populate_geometry_columns()

    def test_perform_checks_with_sql(self):
        self.db.perform_checks_with_sql(self.settings, "v2_manhole", "completeness")

    def test_perform_checks_with_sql_raise(self):
        ini_relpath_key_missing = "data/instellingen_test_missing_key.ini"
        ini_abspath_key_missing = os.path.join(
            os.path.dirname(__file__), ini_relpath_key_missing
        )
        test_settings = settingsObject(ini_abspath_key_missing)
        with pytest.raises(Exception):
            self.db.perform_checks_with_sql(test_settings, "v2_manhole", "completeness")

    # TODO: add checks for all types in sql.py

    def test_execute_sql_file(self):
        sql_relpath = os.path.join(
            "sql_functions", "function_array_greatest_or_smallest.sql"
        )
        sql_abspath = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), sql_relpath
        )
        self.db.execute_sql_file(sql_abspath)

    def test_execute_sql_dir(self):
        sql_reldir = "sql_functions"
        sql_absdir = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), sql_reldir
        )
        self.db.execute_sql_dir(sql_absdir)
