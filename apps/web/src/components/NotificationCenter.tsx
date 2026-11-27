import { useCallback, useEffect, useRef, useState } from "react";
import { updateCaseRequest } from "../api/cases";
import {
  dismissNotificationRequest,
  fetchNotificationsRequest,
  type NotificationItem,
} from "../api/notifications";
import { useAuth } from "../context/useAuth";
import { formatPolishDate } from "../utils/dates";
import {
  getDesktopNotificationPermission,
  requestDesktopNotificationPermission,
  showWindowsNotification,
  type DesktopNotifPermission,
} from "../utils/desktopNotifications";

const POLL_INTERVAL_MS = 60_000;

function formatDaysLabel(item: NotificationItem): string {
  if (item.urgency === "overdue") {
    const overdueDays = Math.abs(item.days_remaining);
    return `ZALEGŁE (${overdueDays} ${overdueDays === 1 ? "dzień" : "dni"} po terminie)`;
  }
  if (item.days_remaining === 0) {
    return "Termin dzisiaj";
  }
  const unit = item.days_remaining === 1 ? "dzień" : "dni";
  return `Za ${item.days_remaining} ${unit}`;
}

function itemKey(item: NotificationItem): string {
  return `${item.case_id}:${item.deadline}:${item.urgency}`;
}

export function NotificationCenter() {
  const { token, user } = useAuth();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [panelOpen, setPanelOpen] = useState(false);
  const [popupOpen, setPopupOpen] = useState(false);
  const [busyCaseId, setBusyCaseId] = useState<number | null>(null);
  const [desktopPerm, setDesktopPerm] = useState<DesktopNotifPermission>(() =>
    getDesktopNotificationPermission()
  );

  const seenKeysRef = useRef<Set<string>>(new Set());
  const initialLoadedRef = useRef(false);

  const loadNotifications = useCallback(
    async (isInitial: boolean) => {
      if (!token) {
        return;
      }
      try {
        const fetched = await fetchNotificationsRequest(token);
        setItems(fetched);

        const nextKeys = new Set(fetched.map(itemKey));
        const hasNewOrEscalated = fetched.some((item) => !seenKeysRef.current.has(itemKey(item)));
        seenKeysRef.current = nextKeys;

        if (fetched.length === 0) {
          setPopupOpen(false);
        } else if (isInitial || hasNewOrEscalated) {
          setPopupOpen(true);
          showWindowsNotification(fetched);
        }
      } catch {
        // Degrade silently on poll failure or unmocked test endpoints
      }
    },
    [token]
  );

  useEffect(() => {
    if (!token || !user) {
      return;
    }
    const isInitial = !initialLoadedRef.current;
    initialLoadedRef.current = true;
    void loadNotifications(isInitial);

    const timer = window.setInterval(() => {
      void loadNotifications(false);
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [token, user, loadNotifications]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setPopupOpen(false);
        setPanelOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  if (!user || !token) {
    return null;
  }

  const showAssignee = user.role === "admin" || user.role === "supervisor";

  async function handleEnableWindowsNotifications() {
    const result = await requestDesktopNotificationPermission();
    setDesktopPerm(result);
    if (result === "granted" && items.length > 0) {
      showWindowsNotification(items);
    }
  }

  async function handleDismiss(item: NotificationItem) {
    if (!token) {
      return;
    }
    setBusyCaseId(item.case_id);
    try {
      await dismissNotificationRequest(token, item.case_id);
      setItems((prev) => {
        const remaining = prev.filter((x) => x.case_id !== item.case_id);
        if (remaining.length === 0) {
          setPopupOpen(false);
        }
        return remaining;
      });
    } catch {
      // Handled gracefully
    } finally {
      setBusyCaseId(null);
    }
  }

  async function handleCloseCase(item: NotificationItem) {
    if (!token) {
      return;
    }
    setBusyCaseId(item.case_id);
    try {
      await updateCaseRequest(token, item.case_id, {
        version: item.version,
        status: "closed",
      });
      setItems((prev) => {
        const remaining = prev.filter((x) => x.case_id !== item.case_id);
        if (remaining.length === 0) {
          setPopupOpen(false);
        }
        return remaining;
      });
    } catch {
      // Refresh if conflict occurred
      void loadNotifications(false);
    } finally {
      setBusyCaseId(null);
    }
  }

  function renderNotificationList() {
    if (items.length === 0) {
      return <p className="notif-empty">Brak pilnych powiadomień o terminach.</p>;
    }

    return (
      <ul className="notif-list">
        {items.map((item) => (
          <li
            key={itemKey(item)}
            className={`notif-item notif-item-${item.urgency}`}
          >
            <div className="notif-item-top">
              <strong>{item.case_title}</strong>
              <span
                className={`urgency-badge ${
                  item.urgency === "overdue" ? "urgency-overdue" : "urgency-due_soon"
                }`}
              >
                {formatDaysLabel(item)}
              </span>
            </div>
            <p className="notif-item-meta">
              Klient: {item.client_name} · Termin: {formatPolishDate(item.deadline)}
              {showAssignee ? ` · ${item.assigned_to_email}` : ""}
            </p>
            <div className="notif-item-actions">
              <button
                className="row-btn"
                type="button"
                disabled={busyCaseId === item.case_id}
                onClick={() => void handleDismiss(item)}
              >
                Zamknij
              </button>
              <button
                className="row-btn row-btn-complete"
                type="button"
                disabled={busyCaseId === item.case_id}
                onClick={() => void handleCloseCase(item)}
              >
                Zakończ sprawę
              </button>
            </div>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="notif-wrapper">
      <button
        className="notif-bell-btn"
        type="button"
        aria-label={`Powiadomienia o terminach (${items.length})`}
        aria-expanded={panelOpen}
        onClick={() => setPanelOpen((open) => !open)}
      >
        <span aria-hidden="true">🔔</span>
        {items.length > 0 && <span className="notif-count-badge">{items.length}</span>}
      </button>

      {panelOpen && (
        <section className="notif-dropdown" aria-label="Panel powiadomień">
          <div className="notif-dropdown-header">
            <h3>Powiadomienia ({items.length})</h3>
            {desktopPerm === "default" && (
              <button
                className="row-btn"
                type="button"
                onClick={() => void handleEnableWindowsNotifications()}
              >
                Włącz powiadomienia Windows
              </button>
            )}
          </div>
          {renderNotificationList()}
        </section>
      )}

      {popupOpen && items.length > 0 && (
        <div className="modal-backdrop">
          <div
            className="modal-card modal-notifications"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="notif-popup-heading"
          >
            <div className="editor-header">
              <h2 id="notif-popup-heading">
                Pilne terminy spraw ({items.length})
              </h2>
              {desktopPerm === "default" && (
                <button
                  className="row-btn"
                  type="button"
                  onClick={() => void handleEnableWindowsNotifications()}
                >
                  Włącz powiadomienia Windows
                </button>
              )}
            </div>
            <p className="cases-subtitle">
              Poniższe sprawy wymagają uwagi. Możesz odrzucić powiadomienie lub od razu oznaczyć
              sprawę jako zakończoną.
            </p>
            <div className="notif-popup-scroll">{renderNotificationList()}</div>
            <div className="editor-actions">
              <button
                className="secondary-btn"
                type="button"
                onClick={() => setPopupOpen(false)}
              >
                Ukryj na teraz
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
