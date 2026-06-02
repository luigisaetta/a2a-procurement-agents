"""
Purchase order system integration wrapper.

Author: L. Saetta
Date Last Modified: 2026-06-01
License: MIT
Description:    Encapsulates the future external purchase order system API.
                Supports deterministic fake data and Docker Compose MySQL
                persistence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from purchase_order_agent.config import Settings
from purchase_order_agent.models import (
    CreatePurchaseOrderRequest,
    CreatePurchaseOrderResponse,
    PurchaseOrderError,
    PurchaseOrderRegistration,
)

_EXPECTED_PURCHASE_ORDER_COLUMNS = {
    "purchase_order_id",
    "request_id",
    "offer_id",
    "supplier_id",
    "supplier_name",
    "plant_code",
    "material_code",
    "material_description",
    "quantity",
    "unit_of_measure",
    "unit_price",
    "total_amount",
    "currency",
    "requested_delivery_date",
    "confirmed_delivery_date",
    "status",
    "external_reference",
    "registered_at",
    "created_at",
    "updated_at",
}


class ConnectionFactory(Protocol):  # pylint: disable=too-few-public-methods
    """Callable that returns a DB-API compatible connection."""

    def __call__(self) -> Any:
        """Return a database connection."""


class PurchaseOrderSystemClient:  # pylint: disable=too-few-public-methods,too-many-arguments
    """Client wrapper for the company purchase order system."""

    def __init__(
        self,
        *,
        storage_backend: str = "fake",
        db_host: str = "127.0.0.1",
        db_port: int = 3306,
        db_name: str = "procurement_demo",
        db_user: str = "",
        db_password: str = "",
        connection_factory: ConnectionFactory | None = None,
    ) -> None:  # pylint: disable=too-many-arguments
        """Initialize the purchase order system wrapper.

        Args:
            storage_backend: Backend name, either ``fake`` or ``mysql``.
            db_host: MySQL host used by the ``mysql`` backend.
            db_port: MySQL TCP port used by the ``mysql`` backend.
            db_name: MySQL database name used by the ``mysql`` backend.
            db_user: MySQL user used by the ``mysql`` backend.
            db_password: MySQL password used by the ``mysql`` backend.
            connection_factory: Optional connection factory for tests.
        """

        self._storage_backend = storage_backend
        self._db_host = db_host
        self._db_port = db_port
        self._db_name = db_name
        self._db_user = db_user
        self._db_password = db_password
        self._connection_factory = connection_factory

    @classmethod
    def from_settings(cls, settings: Settings) -> "PurchaseOrderSystemClient":
        """Create a wrapper from validated runtime settings.

        Args:
            settings: Runtime settings.

        Returns:
            Configured purchase order system wrapper.
        """

        return cls(
            storage_backend=settings.purchase_order_storage_backend,
            db_host=settings.db_host,
            db_port=settings.db_port,
            db_name=settings.db_name,
            db_user=settings.db_user,
            db_password=settings.db_password,
        )

    def register_purchase_order(
        self,
        request: CreatePurchaseOrderRequest,
    ) -> CreatePurchaseOrderResponse:
        """Register a purchase order in the company purchase order system.

        The default implementation is a deterministic fake call. When MySQL is
        configured, the wrapper persists the registration in the demo database.
        Future implementations can replace this method with an API, ERP, or
        other enterprise integration without changing the A2A contract.

        Args:
            request: Validated purchase order registration request.

        Returns:
            Structured registration response.
        """

        if self._storage_backend == "mysql":
            return self._register_purchase_order_mysql(request)
        return self._register_purchase_order_fake(request)

    def _register_purchase_order_fake(
        self,
        request: CreatePurchaseOrderRequest,
    ) -> CreatePurchaseOrderResponse:
        """Return a deterministic fake registration response.

        Args:
            request: Validated purchase order registration request.

        Returns:
            Structured registration response.
        """

        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
        registered_at = timestamp.replace("+00:00", "Z")
        purchase_order_id = request.purchase_order_id or _generated_purchase_order_id(1)
        external_reference = f"ERP-{purchase_order_id}"

        return CreatePurchaseOrderResponse(
            request_id=request.request_id,
            status="registered",
            purchase_order=PurchaseOrderRegistration(
                purchase_order_id=purchase_order_id,
                external_reference=external_reference,
                registered_at=registered_at,
            ),
            message=f"Purchase order {purchase_order_id} was registered successfully.",
            error=PurchaseOrderError(code="", message=""),
        )

    def _register_purchase_order_mysql(
        self,
        request: CreatePurchaseOrderRequest,
    ) -> CreatePurchaseOrderResponse:
        """Register and persist a purchase order in MySQL.

        Args:
            request: Validated purchase order registration request.

        Returns:
            Structured registration response.
        """

        connection = None
        try:
            connection = self._connect()
            _ensure_schema(connection)
            existing = _fetch_existing_purchase_order(connection, request)
            if existing:
                if _has_idempotency_conflict(existing, request):
                    connection.rollback()
                    return _failed_response(
                        request,
                        "IDEMPOTENCY_CONFLICT",
                        "A purchase order already exists for this request and offer "
                        "with different content.",
                    )
                connection.commit()
                return _registered_response(
                    request_id=request.request_id,
                    purchase_order_id=str(existing["purchase_order_id"]),
                    external_reference=str(existing["external_reference"]),
                    registered_at=_format_timestamp(existing["registered_at"]),
                )

            sequence_value: int | None = None
            purchase_order_id = request.purchase_order_id
            if not purchase_order_id:
                sequence_value = _next_purchase_order_sequence_value(connection)
                purchase_order_id = _generated_purchase_order_id(sequence_value)

            registered_at = datetime.now(UTC).replace(microsecond=0)
            external_reference = f"ERP-{purchase_order_id}"
            _insert_purchase_order(
                connection,
                request,
                purchase_order_id,
                external_reference,
                registered_at,
            )
            connection.commit()
            return _registered_response(
                request_id=request.request_id,
                purchase_order_id=purchase_order_id,
                external_reference=external_reference,
                registered_at=_format_timestamp(registered_at),
            )
        except Exception as exc:  # pylint: disable=broad-except
            if connection:
                connection.rollback()
            code = "STORAGE_UNAVAILABLE"
            return _failed_response(request, code, str(exc))
        finally:
            if connection:
                connection.close()

    def _connect(self) -> Any:
        """Create a MySQL connection.

        Returns:
            DB-API compatible MySQL connection.
        """

        if self._connection_factory:
            return self._connection_factory()

        import mysql.connector  # pylint: disable=import-outside-toplevel

        return mysql.connector.connect(
            host=self._db_host,
            port=self._db_port,
            database=self._db_name,
            user=self._db_user,
            password=self._db_password,
        )


def _ensure_schema(connection: Any) -> None:
    """Create required persistence tables if they do not exist.

    Args:
        connection: DB-API compatible connection.
    """

    with connection.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_order_sequences (
          sequence_name VARCHAR(64) NOT NULL,
          next_value BIGINT NOT NULL,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (sequence_name)
        )
        """)

    existing_columns = _purchase_order_table_columns(connection)
    if not existing_columns:
        _create_purchase_orders_table(connection)
    elif not _EXPECTED_PURCHASE_ORDER_COLUMNS.issubset(existing_columns):
        if not _purchase_orders_is_empty(connection):
            raise RuntimeError(
                "Existing purchase_orders table is incompatible with the current "
                "Purchase Order Agent schema and contains data."
            )
        _drop_purchase_orders_table(connection)
        _create_purchase_orders_table(connection)
    _ensure_purchase_order_identifier_lengths(connection)


def _create_purchase_orders_table(connection: Any) -> None:
    """Create the current purchase order persistence table."""

    with connection.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
          purchase_order_id VARCHAR(32) NOT NULL,
          request_id VARCHAR(64) NOT NULL,
          offer_id VARCHAR(128) NOT NULL,
          supplier_id VARCHAR(32) NOT NULL,
          supplier_name VARCHAR(128) NOT NULL,
          plant_code VARCHAR(32) NOT NULL,
          material_code VARCHAR(64) NOT NULL,
          material_description VARCHAR(255) NOT NULL,
          quantity DECIMAL(18,4) NOT NULL,
          unit_of_measure VARCHAR(16) NOT NULL,
          unit_price DECIMAL(18,2) NOT NULL,
          total_amount DECIMAL(18,2) NOT NULL,
          currency CHAR(3) NOT NULL,
          requested_delivery_date DATE NOT NULL,
          confirmed_delivery_date DATE NOT NULL,
          status ENUM('registered', 'failed', 'cancelled') NOT NULL,
          external_reference VARCHAR(128) NOT NULL,
          registered_at TIMESTAMP NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (purchase_order_id),
          UNIQUE KEY uq_purchase_orders_request_offer (request_id, offer_id)
        )
        """)


def _ensure_purchase_order_identifier_lengths(connection: Any) -> None:
    """Ensure persisted identifiers fit generated workflow identifiers."""

    with connection.cursor() as cursor:
        cursor.execute("""
            ALTER TABLE purchase_orders
              MODIFY request_id VARCHAR(64) NOT NULL,
              MODIFY offer_id VARCHAR(128) NOT NULL
            """)


def _purchase_order_table_columns(connection: Any) -> set[str]:
    """Return existing ``purchase_orders`` column names."""

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'purchase_orders'
            """)
        rows = cursor.fetchall()
    return {str(row[0]) for row in rows}


def _purchase_orders_is_empty(connection: Any) -> bool:
    """Return whether the existing ``purchase_orders`` table has no rows."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM purchase_orders")
        row = cursor.fetchone()
    if not row:
        return True
    return int(row[0]) == 0


def _drop_purchase_orders_table(connection: Any) -> None:
    """Drop an empty incompatible purchase order persistence table."""

    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE purchase_orders")


def _fetch_existing_purchase_order(
    connection: Any,
    request: CreatePurchaseOrderRequest,
) -> dict[str, Any] | None:
    """Fetch an existing persisted purchase order for the idempotency key.

    Args:
        connection: DB-API compatible connection.
        request: Purchase order request.

    Returns:
        Existing purchase order row, or ``None``.
    """

    with connection.cursor(dictionary=True) as cursor:
        cursor.execute(
            """
            SELECT purchase_order_id, request_id, offer_id, supplier_id,
                   supplier_name, plant_code, material_code,
                   material_description, quantity, unit_of_measure, unit_price,
                   total_amount, currency, requested_delivery_date,
                   confirmed_delivery_date, external_reference, registered_at
            FROM purchase_orders
            WHERE request_id = %s AND offer_id = %s
            """,
            (request.request_id, request.source_offer.offer_id),
        )
        return cursor.fetchone()


def _next_purchase_order_sequence_value(connection: Any) -> int:
    """Allocate the next database-backed purchase order sequence value.

    Args:
        connection: DB-API compatible connection.

    Returns:
        Allocated sequence value.
    """

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO purchase_order_sequences (sequence_name, next_value)
            VALUES ('purchase_order', 0)
            ON DUPLICATE KEY UPDATE sequence_name = sequence_name
            """)
        cursor.execute("""
            UPDATE purchase_order_sequences
            SET next_value = LAST_INSERT_ID(next_value + 1)
            WHERE sequence_name = 'purchase_order'
            """)
        cursor.execute("SELECT LAST_INSERT_ID()")
        row = cursor.fetchone()
    if not row:
        raise RuntimeError("MySQL did not return a purchase order sequence value.")
    return int(row[0])


def _insert_purchase_order(
    connection: Any,
    request: CreatePurchaseOrderRequest,
    purchase_order_id: str,
    external_reference: str,
    registered_at: datetime,
) -> None:
    """Persist a registered purchase order row.

    Args:
        connection: DB-API compatible connection.
        request: Purchase order request.
        purchase_order_id: Allocated or supplied purchase order identifier.
        external_reference: Backend external reference.
        registered_at: Registration timestamp.
    """

    line_item = request.line_items[0]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO purchase_orders (
              purchase_order_id, request_id, offer_id, supplier_id,
              supplier_name, plant_code, material_code, material_description,
              quantity, unit_of_measure, unit_price, total_amount, currency,
              requested_delivery_date, confirmed_delivery_date, status,
              external_reference, registered_at
            )
            VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
              'registered', %s, %s
            )
            """,
            (
                purchase_order_id,
                request.request_id,
                request.source_offer.offer_id,
                request.supplier.supplier_id,
                request.supplier.supplier_name,
                request.plant_code,
                line_item.material_code,
                line_item.material_description,
                line_item.quantity,
                line_item.unit_of_measure,
                line_item.unit_price,
                request.source_offer.price,
                request.source_offer.currency,
                line_item.requested_delivery_date,
                line_item.confirmed_delivery_date,
                external_reference,
                registered_at,
            ),
        )


def _has_idempotency_conflict(
    existing: dict[str, Any],
    request: CreatePurchaseOrderRequest,
) -> bool:
    """Return whether an existing row conflicts with the new request.

    Args:
        existing: Existing purchase order row.
        request: New purchase order request.

    Returns:
        ``True`` when materially different fields are present.
    """

    line_item = request.line_items[0]
    comparisons = (
        (existing["supplier_id"], request.supplier.supplier_id),
        (existing["supplier_name"], request.supplier.supplier_name),
        (existing["plant_code"], request.plant_code),
        (existing["material_code"], line_item.material_code),
        (existing["material_description"], line_item.material_description),
        (existing["unit_of_measure"], line_item.unit_of_measure),
        (existing["currency"], request.source_offer.currency),
        (existing["requested_delivery_date"], line_item.requested_delivery_date),
        (existing["confirmed_delivery_date"], line_item.confirmed_delivery_date),
    )
    if any(str(left) != str(right) for left, right in comparisons):
        return True
    numeric_comparisons = (
        (existing["quantity"], line_item.quantity),
        (existing["unit_price"], line_item.unit_price),
        (existing["total_amount"], request.source_offer.price),
    )
    return any(
        Decimal(str(left)).quantize(Decimal("0.0001"))
        != Decimal(str(right)).quantize(Decimal("0.0001"))
        for left, right in numeric_comparisons
    )


def _registered_response(
    *,
    request_id: str,
    purchase_order_id: str,
    external_reference: str,
    registered_at: str,
) -> CreatePurchaseOrderResponse:
    """Build a successful registration response."""

    return CreatePurchaseOrderResponse(
        request_id=request_id,
        status="registered",
        purchase_order=PurchaseOrderRegistration(
            purchase_order_id=purchase_order_id,
            external_reference=external_reference,
            registered_at=registered_at,
        ),
        message=f"Purchase order {purchase_order_id} was registered successfully.",
        error=PurchaseOrderError(code="", message=""),
    )


def _failed_response(
    request: CreatePurchaseOrderRequest,
    code: str,
    message: str,
) -> CreatePurchaseOrderResponse:
    """Build a failed registration response."""

    return CreatePurchaseOrderResponse(
        request_id=request.request_id,
        status="failed",
        purchase_order=PurchaseOrderRegistration(
            purchase_order_id=request.purchase_order_id or "",
            external_reference="",
            registered_at="",
        ),
        message="Purchase order registration failed.",
        error=PurchaseOrderError(code=code, message=message),
    )


def _format_timestamp(value: Any) -> str:
    """Format a timestamp as an ISO 8601 UTC string."""

    if isinstance(value, datetime):
        timestamp = value
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return (
            timestamp.astimezone(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return str(value)


def _generated_purchase_order_id(sequence_value: int) -> str:
    """Return the purchase order identifier for a sequence value."""

    year = datetime.now(UTC).year
    return f"PO-{year}-{sequence_value:06d}"
