"""Moteur de base de données. SQLite : chaque transaction réserve l'écriture dès le
début (BEGIN IMMEDIATE), ce qui sérialise aussi les écritures entre processus
(site web et commandes), en plus du verrou du journal d'audit."""

from typing import Any

from sqlalchemy import Engine, create_engine, event


def make_engine(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        _immediate_transactions(engine)
    return engine


def _immediate_transactions(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _no_implicit_begin(dbapi_connection: Any, _: Any) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin_immediate(connection: Any) -> None:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
