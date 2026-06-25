import type { ServiceType } from '../types/onboarding';
import type { Package } from '../types/packages';

const STORAGE_KEY = 'zealsync_package_service_types';

type PackageServiceTypeMap = Record<string, ServiceType>;

function readMap(): PackageServiceTypeMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as PackageServiceTypeMap) : {};
  } catch {
    return {};
  }
}

/** Persist service type client-side until backend stores package_type. */
export function savePackageServiceType(packageId: string, serviceType: ServiceType): void {
  const map = readMap();
  map[packageId] = serviceType;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

/** Resolve badge/filter type: API field → localStorage → hotspot default. */
export function resolvePackageServiceType(pkg: Package): ServiceType {
  if (pkg.service_type === 'pppoe' || pkg.service_type === 'hotspot') {
    return pkg.service_type;
  }
  return readMap()[pkg.id] ?? 'hotspot';
}
