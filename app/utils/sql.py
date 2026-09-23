"""Dialect-aware SQL helpers portable between SQLite and PostgreSQL."""
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.sql import sqltypes


class month_key(FunctionElement):
    """Renders 'YYYY-MM' for a date/timestamp column in any dialect."""

    type = sqltypes.String(7)
    coerce_arguments = False
    inherit_cache = True


@compiles(month_key)
def _month_key_sqlite(element, compiler, **kw):
    arg = compiler.process(element.clauses.clauses[0], **kw)
    return f"strftime('%Y-%m', {arg})"


@compiles(month_key, "postgresql")
def _month_key_pg(element, compiler, **kw):
    arg = compiler.process(element.clauses.clauses[0], **kw)
    return f"to_char({arg}, 'YYYY-MM')"
