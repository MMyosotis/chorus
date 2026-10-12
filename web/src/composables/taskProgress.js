export function visibleComposingUnits(agentType, producedUnits, targetUnits) {
  if (agentType !== 'image' || targetUnits <= 0) return producedUnits
  return Math.min(producedUnits, targetUnits)
}
