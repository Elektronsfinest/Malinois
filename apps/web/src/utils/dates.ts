export type DeadlineUrgency = "overdue" | "due_soon" | "safe" | "none";

export function getTodayWarsawIso(now: Date = new Date()): string {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Warsaw",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(now);
}

export function formatPolishDate(isoDate: string | null): string {
  if (!isoDate) {
    return "Brak terminu";
  }
  const [year, month, day] = isoDate.split("-");
  if (!year || !month || !day) {
    return isoDate;
  }
  return `${day}.${month}.${year}`;
}

function parseIsoDayUtc(isoDate: string): number {
  const [y, m, d] = isoDate.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

export function getDeadlineUrgency(
  deadline: string | null,
  thresholdDays = 7,
  todayIso: string = getTodayWarsawIso()
): { urgency: DeadlineUrgency; label: string; daysDiff: number | null } {
  if (!deadline) {
    return { urgency: "none", label: "Brak terminu", daysDiff: null };
  }

  const diffMs = parseIsoDayUtc(deadline) - parseIsoDayUtc(todayIso);
  const daysDiff = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (daysDiff < 0) {
    return { urgency: "overdue", label: "ZALEGŁE", daysDiff };
  }
  if (daysDiff === 0) {
    return { urgency: "due_soon", label: "Dziś", daysDiff: 0 };
  }
  if (daysDiff <= thresholdDays) {
    const unit = daysDiff === 1 ? "dzień" : "dni";
    return { urgency: "due_soon", label: `Za ${daysDiff} ${unit}`, daysDiff };
  }
  return { urgency: "safe", label: "W terminie", daysDiff };
}
