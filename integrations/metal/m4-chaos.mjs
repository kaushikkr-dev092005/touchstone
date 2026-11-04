import { createHash } from 'node:crypto';

function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${stable(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
}

export function scenario(raw) {
  const plan = JSON.parse(raw);
  if (plan.version !== 1 || !plan.faults || Array.isArray(plan.faults) ||
      Object.keys(plan).some(k => !['version', 'faults'].includes(k)) || Object.keys(plan.faults).length > 2000) throw Error('Invalid M4 schedule');
  for (const [id, faults] of Object.entries(plan.faults)) {
    if (!/^M4-\d+-\d+-[0-3]$/.test(id) || !faults || typeof faults !== 'object' || Array.isArray(faults) ||
        Object.entries(faults).some(([provider, fault]) => !['local-gpu', 'hosted-premium'].includes(provider) ||
          !['outage', 'quality-drop'].includes(fault))) throw Error('Invalid M4 fault binding');
  }
  const sha256 = createHash('sha256').update(stable(plan)).digest('hex');
  return { sha256, fault: (taskId, providerId) => plan.faults[taskId]?.[providerId] || 'none' };
}
