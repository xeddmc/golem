# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods
from golem import model

SCHEMA_VERSION = 17


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'income',
        value_received=model.HexIntegerField(default=0),
    )


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('income', 'value_received')
