export const MARKET_TIME_ZONE = "Europe/Moscow";

export function formatMarketDateInput(value: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: MARKET_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${lookup.year}-${lookup.month}-${lookup.day}`;
}

export function parseMarketDateInput(value: string): number {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return Number.NaN;
  }
  const [, year, month, day] = match;
  return Date.parse(`${year}-${month}-${day}T00:00:00+03:00`);
}
