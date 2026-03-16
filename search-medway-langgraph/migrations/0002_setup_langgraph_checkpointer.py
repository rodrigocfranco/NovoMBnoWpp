from django.db import migrations
from django.conf import settings
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row


def setup_langgraph_tables(apps, schema_editor):
    """Cria as tabelas necessárias para o PostgresSaver do LangGraph"""
    DB_USER = settings.DATABASES['default']['USER']
    DB_PASSWORD = settings.DATABASES['default']['PASSWORD']
    DB_HOST = settings.DATABASES['default']['HOST']
    DB_PORT = settings.DATABASES['default']['PORT']
    DB_NAME = settings.DATABASES['default']['NAME']
    
    DB_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    pool = ConnectionPool(
        conninfo=DB_URI,
        max_size=10,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "options": "-c search_path=langgraph,public",
        },
    )
    
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    
    pool.close()


def teardown_langgraph_tables(apps, schema_editor):
    """Remove as tabelas do LangGraph (opcional para rollback)"""
    if schema_editor.connection.vendor != 'postgresql':
        return
    
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS langgraph.writes CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS langgraph.checkpoints CASCADE;")
        cursor.execute("DROP SCHEMA IF EXISTS langgraph CASCADE;")


class Migration(migrations.Migration):

    dependencies = [
        ('workflows', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            setup_langgraph_tables,
            reverse_code=teardown_langgraph_tables
        ),
    ]