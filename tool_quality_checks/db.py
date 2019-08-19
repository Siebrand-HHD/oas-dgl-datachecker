# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
# -*- coding: utf-8 -*-

import psycopg2

# from psycopg2.extras import RealDictCursor
import logging
import sql_checks
import sql_views
import os

logger = logging.getLogger(__name__)


class ThreediDatabase(object):
    """
    Connects to a database using python's psycopg2 module.
    """

    def __init__(self, settings):
        """ Establishes the db connection. """
        credentials = {
            "dbname": settings.database,
            "host": settings.host,
            "user": settings.username,
            "password": settings.password,
        }
        try:
            self.db = psycopg2.connect(**credentials)
        except psycopg2.Error as e:
            logger.exception(e)
            raise

    def initialize_db(self):
        """ Initialize database for checks """
        self.create_schema(schema_name="chk")
        for schema, table in [
            ["public", "v2_1d_boundary_conditions_view"],
            ["public", "v2_pumpstation_point_view"],
            ["public", "v2_1d_lateral_view"],
            ["public", "v2_cross_section_definition_rio_view"],
            ["chk", "v2_pipe_view_left_join"],
            ["chk", "v2_orifice_view_left_join"],
            ["chk", "v2_weir_view_left_join"],
        ]:
            self.create_view(view_table=table, view_schema=schema)

        # install all functions out of folder "sql_functions"
        sql_reldir = "sql_functions"
        sql_absdir = os.path.join(os.path.dirname(__file__), sql_reldir)
        self.execute_sql_dir(sql_absdir)

    def get_count(self, table_name, schema="public"):
        """
        :param table:
        :return:
        """
        statement = "SELECT COUNT(*) from {schema}.{table_name:s}".format(
            table_name=table_name, schema=schema
        )
        result = self.execute_sql_statement(statement, fetch=True)
        return result[0][0]

    def execute_sql_statement(self, sql_statement, fetch=True):
        """
        :param sql_statement: custom sql statement

        makes use of the existing database connection to run a custom query
        """
        with self.db:
            with self.db.cursor() as cur:
                cur.execute(sql_statement)
                if fetch is True:
                    return cur.fetchall()
                self.db.commit()
                logger.debug(
                    "[+] Successfully executed statement {}".format(sql_statement)
                )

    def select_table_names(self, search_table_name, schema="public"):

        statement = """
        SELECT table_name
        FROM   information_schema.tables
        WHERE  table_schema = '{schema}'
        AND    table_name LIKE '{search_table_name}'
        AND    table_type = 'BASE TABLE';
        """.format(
            schema=schema, search_table_name=search_table_name
        )
        return [i[0] for i in self.execute_sql_statement(statement, fetch=True)]

    def create_schema(self, schema_name, drop_schema=False):
        """create a schema"""
        if drop_schema == True:
            drop_schema = """DROP SCHEMA IF EXISTS {schema_name} CASCADE;""".format(
                schema_name=schema_name
            )
            self.execute_sql_statement(drop_schema, fetch=False)
        create_schema_statement = """
        CREATE SCHEMA IF NOT EXISTS {schema_name}
        ;""".format(
            schema_name=schema_name
        )
        self.execute_sql_statement(sql_statement=create_schema_statement, fetch=False)

    def populate_geometry_columns(self):
        """Populate geometry columns"""
        populate_geometry_columns_statement = """
        SELECT Populate_Geometry_Columns();"""
        self.execute_sql_statement(
            sql_statement=populate_geometry_columns_statement, fetch=False
        )

    def perform_checks_with_sql(self, settings, check_table, check_type):
        """
        Performs quality checks on postgres DB

        :param check_table - list of one or more structure tables (e.g. v2_manhole)
        :param check_type - select type of check: completeness, quality
        """
        check_table = check_table.replace("v2_", "")
        sql_template_name = "sql_" + check_type + "_" + check_table
        if sql_template_name in sql_checks.sql_checks:
            statement = sql_checks.sql_checks[sql_template_name].format(
                **settings.__dict__
            )
            self.execute_sql_statement(sql_statement=statement, fetch=False)

    def create_view(self, view_table, view_schema, drop_view=True):
        """
        Creates a view with a join to v2_connection_nodes table
        
        :param view_table - table of which the view is created
        """
        if drop_view == True:
            drop_statement = """DROP VIEW IF EXISTS {view_table};""".format(
                view_table=view_table
            )
            self.execute_sql_statement(drop_statement, fetch=False)
        create_statement = sql_views.sql_views[view_table].format(schema=view_schema)
        self.execute_sql_statement(sql_statement=create_statement, fetch=False)

    def execute_sql_file(self, filename):
        # Open and read the file as a single buffer
        sql_file = open(filename, "r").read()
        self.execute_sql_statement(sql_statement=sql_file, fetch=False)
        logger.info("Execute sql file with function:" + filename)

    def execute_sql_dir(self, dirname):
        for root, subdirs, files in sorted(os.walk(dirname)):
            for f in sorted(files):
                file_path = os.path.join(root, f)
                if file_path.endswith(".sql"):
                    self.execute_sql_file(file_path)
