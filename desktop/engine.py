"""SQLite project and visual-query engine used by DataForge Desktop."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable


IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def qi(name: str) -> str:
    """Quote a SQLite identifier."""
    return '"' + str(name).replace('"', '""') + '"'


def clean_name(value: str, fallback: str = "field") -> str:
    value = re.sub(r"\W+", "_", str(value).strip()).strip("_")
    if not value:
        value = fallback
    if value[0].isdigit():
        value = "_" + value
    return value


def infer_type(values: Iterable[Any]) -> str:
    values = [v for v in values if v not in (None, "")]
    if not values:
        return "TEXT"
    try:
        for v in values:
            int(v)
        return "INTEGER"
    except (TypeError, ValueError):
        pass
    try:
        for v in values:
            float(v)
        return "REAL"
    except (TypeError, ValueError):
        return "TEXT"


@dataclass
class Join:
    table: str
    left: str
    right: str
    kind: str = "LEFT"


@dataclass
class Filter:
    column: str
    operator: str
    value: Any = ""
    conjunction: str = "AND"


@dataclass
class OutputColumn:
    expression: str
    alias: str = ""
    aggregate: str = ""


@dataclass
class QueryPlan:
    name: str = "Untitled Work Table"
    main_table: str = ""
    joins: list[Join] = field(default_factory=list)
    columns: list[OutputColumn] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    order_by: list[tuple[str, str]] = field(default_factory=list)
    distinct: bool = False
    limit: int = 1000

    def sql_and_params(self) -> tuple[str, list[Any]]:
        if not self.main_table:
            raise ValueError("Choose a main table first")
        if self.columns:
            select_parts = []
            for col in self.columns:
                expr = quote_column_ref(col.expression)
                if col.aggregate:
                    agg = col.aggregate.upper()
                    if agg not in {"COUNT", "SUM", "AVG", "MIN", "MAX", "GROUP_CONCAT"}:
                        raise ValueError(f"Unsupported aggregate: {agg}")
                    expr = f"{agg}({expr})"
                if col.alias:
                    expr += " AS " + qi(clean_name(col.alias))
                select_parts.append(expr)
            select = ", ".join(select_parts)
        else:
            select = f"{qi(self.main_table)}.*"
            for join in self.joins:
                select += f", {qi(join.table)}.*"
        sql = "SELECT " + ("DISTINCT " if self.distinct else "") + select
        sql += "\nFROM " + qi(self.main_table)
        for join in self.joins:
            kind = join.kind.upper()
            if kind not in {"INNER", "LEFT", "CROSS"}:
                raise ValueError(f"Unsupported join: {kind}")
            sql += f"\n{kind} JOIN {qi(join.table)}"
            if kind != "CROSS":
                sql += f" ON {quote_column_ref(join.left)} = {quote_column_ref(join.right)}"
        params: list[Any] = []
        clauses = []
        valid_ops = {"=", "!=", "<>", ">", ">=", "<", "<=", "LIKE", "NOT LIKE", "IS NULL", "IS NOT NULL", "IN"}
        for i, f in enumerate(self.filters):
            op = f.operator.upper()
            if op not in valid_ops:
                raise ValueError(f"Unsupported operator: {op}")
            prefix = "" if i == 0 else (" OR " if f.conjunction.upper() == "OR" else " AND ")
            ref = quote_column_ref(f.column)
            if op in {"IS NULL", "IS NOT NULL"}:
                clause = f"{ref} {op}"
            elif op == "IN":
                vals = f.value if isinstance(f.value, list) else [x.strip() for x in str(f.value).split(",")]
                vals = [x for x in vals if x != ""]
                if not vals:
                    clause = "0"
                else:
                    clause = f"{ref} IN ({','.join('?' for _ in vals)})"
                    params.extend(vals)
            else:
                clause = f"{ref} {op} ?"
                params.append(f.value)
            clauses.append(prefix + clause)
        if clauses:
            sql += "\nWHERE " + "".join(clauses)
        if self.group_by:
            sql += "\nGROUP BY " + ", ".join(quote_column_ref(x) for x in self.group_by)
        if self.order_by:
            parts = []
            for ref, direction in self.order_by:
                direction = "DESC" if direction.upper() == "DESC" else "ASC"
                parts.append(f"{quote_column_ref(ref)} {direction}")
            sql += "\nORDER BY " + ", ".join(parts)
        if self.limit > 0:
            sql += "\nLIMIT " + str(int(self.limit))
        return sql, params

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, value: str) -> "QueryPlan":
        d = json.loads(value)
        d["joins"] = [Join(**x) for x in d.get("joins", [])]
        d["filters"] = [Filter(**x) for x in d.get("filters", [])]
        d["columns"] = [OutputColumn(**x) for x in d.get("columns", [])]
        d["order_by"] = [tuple(x) for x in d.get("order_by", [])]
        return cls(**d)


def quote_column_ref(ref: str) -> str:
    ref = str(ref).strip()
    if ref == "*":
        return "*"
    if "." in ref:
        table, column = ref.split(".", 1)
        return f"{qi(table)}.{qi(column)}"
    return qi(ref)


class ProjectDB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS _dataforge_queries(
                name TEXT PRIMARY KEY, plan_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS _dataforge_meta(
                key TEXT PRIMARY KEY, value TEXT
            );
        """)

    def close(self) -> None:
        self.conn.close()

    def tables(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_dataforge_%' ORDER BY name")
        return [r[0] for r in rows]

    def columns(self, table: str) -> list[dict[str, Any]]:
        return [dict(x) for x in self.conn.execute(f"PRAGMA table_info({qi(table)})")]

    def create_table(self, name: str, columns: list[tuple[str, str]], replace: bool = False) -> str:
        name = clean_name(name, "table")
        if replace:
            self.conn.execute(f"DROP TABLE IF EXISTS {qi(name)}")
        if not columns:
            columns = [("id", "INTEGER PRIMARY KEY")]
        allowed = {"TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC", "INTEGER PRIMARY KEY"}
        defs = []
        used = set()
        for raw, typ in columns:
            col = clean_name(raw)
            base, n = col, 2
            while col.lower() in used:
                col = f"{base}_{n}"; n += 1
            used.add(col.lower())
            typ = typ.upper() if typ.upper() in allowed else "TEXT"
            defs.append(f"{qi(col)} {typ}")
        self.conn.execute(f"CREATE TABLE {qi(name)} ({', '.join(defs)})")
        self.conn.commit()
        return name

    def unique_table_name(self, raw: str) -> str:
        base = clean_name(raw, "imported_data")
        existing = set(self.tables())
        name, n = base, 2
        while name in existing:
            name = f"{base}_{n}"; n += 1
        return name

    def import_csv(self, path: str | Path, table: str | None = None) -> tuple[str, int]:
        path = Path(path)
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(65536); fh.seek(0)
            try: dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
            except csv.Error: dialect = csv.excel
            rows = list(csv.DictReader(fh, dialect=dialect))
        return self.import_records(rows, table or path.stem)

    def import_json(self, path: str | Path, table: str | None = None) -> tuple[str, int]:
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            list_value = next((v for v in data.values() if isinstance(v, list)), None)
            data = list_value if list_value is not None else [data]
        if not isinstance(data, list):
            raise ValueError("JSON must contain an object, an array of objects, or an object containing an array")
        records = [x if isinstance(x, dict) else {"value": x} for x in data]
        return self.import_records(records, table or path.stem)

    def import_records(self, records: list[dict[str, Any]], raw_name: str) -> tuple[str, int]:
        if not records:
            raise ValueError("The file contains no records")
        keys: list[str] = []
        for row in records:
            for key in row:
                if key not in keys: keys.append(key)
        mapping: dict[str, str] = {}
        used = set()
        for key in keys:
            name = clean_name(key)
            base, n = name, 2
            while name.lower() in used:
                name = f"{base}_{n}"; n += 1
            mapping[key] = name; used.add(name.lower())
        columns = []
        for key in keys:
            values = [row.get(key) for row in records[:500]]
            columns.append((mapping[key], infer_type(values)))
        name = self.create_table(self.unique_table_name(raw_name), columns)
        col_sql = ",".join(qi(mapping[k]) for k in keys)
        marks = ",".join("?" for _ in keys)
        values = []
        for row in records:
            out = []
            for key in keys:
                v = row.get(key)
                if isinstance(v, (dict, list)): v = json.dumps(v, ensure_ascii=False)
                out.append(v)
            values.append(out)
        self.conn.executemany(f"INSERT INTO {qi(name)} ({col_sql}) VALUES ({marks})", values)
        self.conn.commit()
        return name, len(records)

    def execute_plan(self, plan: QueryPlan) -> tuple[list[str], list[tuple[Any, ...]]]:
        sql, params = plan.sql_and_params()
        cur = self.conn.execute(sql, params)
        return [x[0] for x in cur.description or []], [tuple(x) for x in cur.fetchall()]

    def materialize(self, plan: QueryPlan, raw_name: str, replace: bool = False) -> str:
        name = clean_name(raw_name, "output")
        sql, params = plan.sql_and_params()
        if replace: self.conn.execute(f"DROP TABLE IF EXISTS {qi(name)}")
        elif name in self.tables(): name = self.unique_table_name(name)
        self.conn.execute(f"CREATE TABLE {qi(name)} AS {sql}", params)
        self.conn.commit()
        return name

    def save_plan(self, plan: QueryPlan) -> None:
        self.conn.execute("INSERT INTO _dataforge_queries(name,plan_json,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(name) DO UPDATE SET plan_json=excluded.plan_json,updated_at=CURRENT_TIMESTAMP", (plan.name, plan.to_json()))
        self.conn.commit()

    def saved_plans(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT name FROM _dataforge_queries ORDER BY updated_at DESC")]

    def load_plan(self, name: str) -> QueryPlan:
        row = self.conn.execute("SELECT plan_json FROM _dataforge_queries WHERE name=?", (name,)).fetchone()
        if not row: raise KeyError(name)
        return QueryPlan.from_json(row[0])

    def export_rows(self, columns: list[str], rows: list[tuple[Any, ...]], path: str | Path) -> None:
        path = Path(path)
        if path.suffix.lower() == ".json":
            payload = [dict(zip(columns, row)) for row in rows]
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        else:
            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh); writer.writerow(columns); writer.writerows(rows)
