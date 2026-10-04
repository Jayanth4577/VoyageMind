/** Free booking deep-links — VoyageMind never takes payments; we hand off
 * to public booking sites pre-filled with the trip context. */

/** yyyy-mm-dd -> dd-mm-yyyy (RedBus format) */
function dmy(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y}`;
}

export function googleFlightsUrl(from: string, to: string, date: string): string {
  const q = encodeURIComponent(`flights from ${from} to ${to} on ${date}`);
  return `https://www.google.com/travel/flights?q=${q}`;
}

export function irctcTrainsUrl(from: string, to: string): string {
  return `https://www.irctc.co.in/nget/train/search?originCity=${encodeURIComponent(from)}&destinationCity=${encodeURIComponent(to)}`;
}

export function redbusUrl(from: string, to: string, date: string): string {
  return `https://www.redbus.in/search?fromCityName=${encodeURIComponent(from)}&toCityName=${encodeURIComponent(to)}&doj=${dmy(date)}`;
}

export function bookingComUrl(
  destination: string,
  checkin: string,
  checkout: string,
  adults: number,
): string {
  return `https://www.booking.com/searchresults.html?ss=${encodeURIComponent(destination)}&checkin=${checkin}&checkout=${checkout}&group_adults=${Math.max(1, adults)}&no_rooms=1`;
}

export function goibiboStaysUrl(destination: string, checkin: string, checkout: string): string {
  return `https://www.goibibo.com/hotels/hotels-in-${encodeURIComponent(destination.toLowerCase().replaceAll(" ", "-"))}-c/?checkin=${checkin}&checkout=${checkout}`;
}

export function osmPlaceUrl(lat: number, lng: number): string {
  return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=13/${lat}/${lng}`;
}
