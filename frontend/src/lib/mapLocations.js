// Which map dots an item gets. Kept separate from NERMap so it can be checked on its own.

// Names that cover a whole state or country rather than one place.
export const AREA_NAMES = new Set([
  "Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura",
  "Nagaland", "Sikkim", "West Bengal", "Bihar", "Bangladesh", "Myanmar",
  "Bhutan", "Nepal", "China", "Tibet", "India", "NER", "North East",
  "Northeast", "Northeast India", "North East India",
]);

// A story naming this many states or countries is about the whole region.
export const REGION_WIDE_MIN_AREAS = 4;

function matchKeys(loc, coords) {
  if (coords[loc]) return [loc];
  const l = loc.toLowerCase();
  return Object.keys(coords).filter((k) => {
    const kl = k.toLowerCase();
    return l.includes(kl) || kl.includes(l);
  });
}

/**
 * Dots go on the specific towns a story names. Only when it names no known
 * town does it fall back to one dot in its main state, so a region-wide story
 * does not paint a dot in every state it mentions.
 */
export function mapLocationsFor(item, coords) {
  const locs = (item.entities?.locations || []).filter(Boolean);
  const areas = new Set(locs.filter((l) => AREA_NAMES.has(l)));
  if (item.state) areas.add(item.state);

  const places = new Set();
  locs.filter((l) => !AREA_NAMES.has(l)).forEach((l) => {
    matchKeys(l, coords).forEach((k) => { if (!AREA_NAMES.has(k)) places.add(k); });
  });

  const keys = places.size ? places : new Set(item.state ? matchKeys(item.state, coords) : []);
  return { keys, regionWide: areas.size >= REGION_WIDE_MIN_AREAS };
}
