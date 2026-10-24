import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { fetchRecentPurchaseOrders } from "../lib/api";
import { formatDate } from "../lib/progress";
import type { PurchaseOrderRecord } from "../lib/types";

const RECENT_PURCHASE_ORDERS_LIMIT = 10;

interface RecentPurchaseOrdersProps {
  // Changes when a workflow finishes, so the table reloads and shows the
  // purchase order that the workflow may have created.
  refreshToken: string;
}

export function RecentPurchaseOrders({ refreshToken }: RecentPurchaseOrdersProps) {
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrderRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const loadPurchaseOrders = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetchRecentPurchaseOrders(RECENT_PURCHASE_ORDERS_LIMIT);
      setPurchaseOrders(response.purchase_orders);
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPurchaseOrders();
  }, [loadPurchaseOrders, refreshToken]);

  return (
    <section className="panel">
      <div className="panelHeader inline">
        <div>
          <span className="eyebrow">Purchasing</span>
          <h2>Recent purchase orders</h2>
        </div>
        <button
          className="secondaryButton"
          disabled={loading}
          onClick={() => void loadPurchaseOrders()}
          type="button"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {panelContent(purchaseOrders, loading, loadFailed)}
    </section>
  );
}

function panelContent(
  purchaseOrders: PurchaseOrderRecord[],
  loading: boolean,
  loadFailed: boolean,
): ReactNode {
  if (loadFailed) {
    return <p className="muted">Recent purchase orders could not be loaded.</p>;
  }
  if (purchaseOrders.length === 0) {
    return (
      <p className="muted">{loading ? "Loading purchase orders..." : "No purchase orders yet."}</p>
    );
  }
  return <PurchaseOrdersTable purchaseOrders={purchaseOrders} />;
}

function PurchaseOrdersTable({ purchaseOrders }: { purchaseOrders: PurchaseOrderRecord[] }) {
  return (
    <div className="tableWrapper">
      <table className="ordersTable">
        <thead>
          <tr>
            <th scope="col">Part</th>
            <th className="numeric" scope="col">
              Quantity
            </th>
            <th scope="col">Delivery</th>
            <th scope="col">Plant</th>
            <th scope="col">Supplier</th>
          </tr>
        </thead>
        <tbody>
          {purchaseOrders.map((order) => (
            <tr key={order.purchase_order_id}>
              <td>
                <strong>{order.material_code}</strong>
                <small>{order.material_description}</small>
              </td>
              <td className="numeric">
                {order.quantity} {order.unit_of_measure}
              </td>
              <td>{formatDate(order.confirmed_delivery_date)}</td>
              <td>{order.plant_code}</td>
              <td>{order.supplier_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
