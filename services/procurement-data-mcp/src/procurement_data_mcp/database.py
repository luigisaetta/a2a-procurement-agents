"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    MySQL data access layer for the Procurement Data MCP Server.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

import mysql.connector

from procurement_data_mcp.config import Settings


class ProcurementDataRepository:
    """Read-only repository backed by the procurement demo MySQL schema."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the repository.

        Args:
            settings: Database connection settings.
        """

        self._settings = settings

    def _connect(self) -> mysql.connector.MySQLConnection:
        """Create a MySQL connection.

        Returns:
            MySQL connection.
        """

        return mysql.connector.connect(
            host=self._settings.db_host,
            port=self._settings.db_port,
            database=self._settings.db_name,
            user=self._settings.db_user,
            password=self._settings.db_password,
        )

    def _fetch_all(
        self, query: str, params: Iterable[Any] = ()
    ) -> list[dict[str, Any]]:
        """Run a read query and return normalized rows.

        Args:
            query: SQL query.
            params: Query parameters.

        Returns:
            List of row dictionaries.
        """

        with self._connect() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        return [_normalize_row(row) for row in rows]

    def _fetch_one(
        self, query: str, params: Iterable[Any] = ()
    ) -> dict[str, Any] | None:
        """Run a read query and return one normalized row.

        Args:
            query: SQL query.
            params: Query parameters.

        Returns:
            Row dictionary, or None when no row exists.
        """

        rows = self._fetch_all(query, params)
        return rows[0] if rows else None

    def list_plants(
        self, *, limit: int, offset: int, active_only: bool
    ) -> list[dict[str, Any]]:
        """List plants."""

        where = "WHERE is_active = TRUE" if active_only else ""
        return self._fetch_all(
            f"""
            SELECT plant_id, plant_code, plant_name, country_code, country_name,
                   city, address, is_active
            FROM plants
            {where}
            ORDER BY plant_id
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )

    def get_plant(
        self, *, plant_id: str | None = None, plant_code: str | None = None
    ) -> dict[str, Any] | None:
        """Return one plant."""

        column = "plant_id" if plant_id else "plant_code"
        value = plant_id or plant_code
        return self._fetch_one(
            f"""
            SELECT plant_id, plant_code, plant_name, country_code, country_name,
                   city, address, is_active
            FROM plants
            WHERE {column} = %s
            """,
            (value,),
        )

    def list_parts(
        self, *, category: str | None, limit: int, offset: int, active_only: bool
    ) -> list[dict[str, Any]]:
        """List parts."""

        clauses: list[str] = []
        params: list[Any] = []
        if category:
            clauses.append("category = %s")
            params.append(category)
        if active_only:
            clauses.append("is_active = TRUE")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        return self._fetch_all(
            f"""
            SELECT part_id, part_code, part_name, description, category,
                   unit_of_measure, is_active
            FROM parts
            {where}
            ORDER BY part_id
            LIMIT %s OFFSET %s
            """,
            params,
        )

    def get_part(
        self, *, part_id: str | None = None, part_code: str | None = None
    ) -> dict[str, Any] | None:
        """Return one part."""

        column = "part_id" if part_id else "part_code"
        value = part_id or part_code
        return self._fetch_one(
            f"""
            SELECT part_id, part_code, part_name, description, category,
                   unit_of_measure, is_active
            FROM parts
            WHERE {column} = %s
            """,
            (value,),
        )

    def list_suppliers(
        self, *, limit: int, offset: int, active_only: bool
    ) -> list[dict[str, Any]]:
        """List suppliers."""

        where = "WHERE is_active = TRUE" if active_only else ""
        return self._fetch_all(
            f"""
            SELECT supplier_id, supplier_name, country_code, country_name,
                   contact_endpoint, currency, quality_score, reliability_score,
                   is_active
            FROM suppliers
            {where}
            ORDER BY supplier_id
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )

    def get_supplier(self, *, supplier_id: str) -> dict[str, Any] | None:
        """Return one supplier."""

        return self._fetch_one(
            """
            SELECT supplier_id, supplier_name, country_code, country_name,
                   contact_endpoint, currency, quality_score, reliability_score,
                   is_active
            FROM suppliers
            WHERE supplier_id = %s
            """,
            (supplier_id,),
        )

    def list_suppliers_for_part(
        self, *, part_id: str, active_only: bool
    ) -> list[dict[str, Any]]:
        """List supplier candidates for a part."""

        filters = ["sp.part_id = %s"]
        if active_only:
            filters.extend(["sp.is_active = TRUE", "s.is_active = TRUE"])
        where = " AND ".join(filters)
        return self._fetch_all(
            f"""
            SELECT sp.supplier_part_id, s.supplier_id, s.supplier_name,
                   s.country_code, s.country_name, s.contact_endpoint,
                   s.currency, s.quality_score, s.reliability_score, sp.lead_time_days,
                   sp.min_order_quantity, sp.is_preferred
            FROM supplier_parts sp
            JOIN suppliers s ON s.supplier_id = sp.supplier_id
            WHERE {where}
            ORDER BY sp.is_preferred DESC, s.reliability_score DESC,
                     s.quality_score DESC, sp.lead_time_days ASC, s.supplier_id ASC
            """,
            (part_id,),
        )

    def list_parts_for_supplier(
        self, *, supplier_id: str, active_only: bool
    ) -> list[dict[str, Any]]:
        """List parts a supplier can provide."""

        filters = ["sp.supplier_id = %s"]
        if active_only:
            filters.extend(["sp.is_active = TRUE", "p.is_active = TRUE"])
        where = " AND ".join(filters)
        return self._fetch_all(
            f"""
            SELECT sp.supplier_part_id, p.part_id, p.part_code, p.part_name,
                   p.category, p.unit_of_measure, sp.lead_time_days,
                   sp.min_order_quantity, sp.is_preferred
            FROM supplier_parts sp
            JOIN parts p ON p.part_id = sp.part_id
            WHERE {where}
            ORDER BY sp.is_preferred DESC, p.part_id ASC
            """,
            (supplier_id,),
        )


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert MySQL values into JSON-compatible values.

    Args:
        row: Raw row dictionary.

    Returns:
        Normalized row dictionary.
    """

    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            normalized[key] = (
                int(value) if value == value.to_integral() else float(value)
            )
        elif isinstance(value, bytes):
            normalized[key] = value.decode()
        elif key.startswith("is_"):
            normalized[key] = bool(value)
        else:
            normalized[key] = value
    return normalized
