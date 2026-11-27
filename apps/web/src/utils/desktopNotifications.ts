import type { NotificationItem } from "../api/notifications";
import { formatPolishDate } from "./dates";

export type DesktopNotifPermission = "default" | "granted" | "denied" | "unsupported";

export function getDesktopNotificationPermission(): DesktopNotifPermission {
  if (typeof window === "undefined" || typeof window.Notification === "undefined") {
    return "unsupported";
  }
  return window.Notification.permission;
}

export async function requestDesktopNotificationPermission(): Promise<DesktopNotifPermission> {
  if (typeof window === "undefined" || typeof window.Notification === "undefined") {
    return "unsupported";
  }
  try {
    return await window.Notification.requestPermission();
  } catch {
    return "denied";
  }
}

export function showWindowsNotification(items: NotificationItem[]): void {
  if (
    items.length === 0 ||
    typeof window === "undefined" ||
    typeof window.Notification === "undefined" ||
    window.Notification.permission !== "granted"
  ) {
    return;
  }

  const overdueCount = items.filter((i) => i.urgency === "overdue").length;
  const title =
    overdueCount > 0
      ? `Malinois: ${overdueCount} zaległych spraw (${items.length} pilnych)`
      : `Malinois: ${items.length} zbliżających się terminów`;

  const first = items[0];
  const body =
    items.length === 1
      ? `${first.case_title} (${first.client_name}) — termin: ${formatPolishDate(first.deadline)}`
      : `${first.case_title} (${formatPolishDate(first.deadline)}) oraz ${items.length - 1} innych spraw.`;

  try {
    const notif = new window.Notification(title, {
      body,
      tag: "malinois-deadline-alerts",
    });
    notif.onclick = () => {
      window.focus();
      notif.close();
    };
  } catch {
    // Gracefully degrade if OS/browser blocks toast creation
  }
}
