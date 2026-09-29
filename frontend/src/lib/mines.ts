/**
 * Mapping between map selections and analytics context.
 * The 5-step panel runs per MINE; the exploration zones (Z-*) sit inside
 * the Ukwa block, so they map to the Ukwa mine context.
 */
export const MINE_CTX = {
  defaultMine: 'Balaghat',
  zoneToMine: (zoneId?: string | null, zoneBlock?: string | null): string => {
    if (zoneBlock === 'GUDMA') return 'Ukwa';
    if (zoneId && /^Z-/i.test(zoneId)) return 'Ukwa';
    return 'Balaghat';
  },
};
