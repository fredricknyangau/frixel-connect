import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, parseISO } from "date-fns"
import { toZonedTime } from "date-fns-tz"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Returns "KES 1,500" for 1500
 * Never shows decimal places for whole amounts
 */
export function formatKES(amount: number): string {
  return new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency: 'KES',
    minimumFractionDigits: amount % 1 === 0 ? 0 : 2,
    maximumFractionDigits: amount % 1 === 0 ? 0 : 2,
  }).format(amount);
}

/**
 * Accepts "254712345678"
 * Returns "0712 345 678"
 */
export function formatPhone(phone: string): string {
  if (!phone) return phone;
  // If it's already local but without spaces, or Daraja format
  const numeric = phone.replace(/\D/g, '');
  if (numeric.startsWith('254') && numeric.length === 12) {
    const local = '0' + numeric.substring(3);
    return `${local.substring(0, 4)} ${local.substring(4, 7)} ${local.substring(7)}`;
  }
  if (numeric.startsWith('0') && numeric.length === 10) {
    return `${numeric.substring(0, 4)} ${numeric.substring(4, 7)} ${numeric.substring(7)}`;
  }
  return phone;
}

/**
 * Accepts UTC ISO string from API ("2026-06-17T10:30:00Z")
 * Returns "17 Jun 2026, 1:30 PM" in Africa/Nairobi timezone
 *
 * WHY timezone matters: an ISP owner in Nairobi seeing "2:30 AM" 
 * instead of "5:30 AM" for a transaction will not trust the system.
 */
export function formatNairobiDate(isoString: string): string {
  if (!isoString) return '';
  const date = parseISO(isoString);
  const nairobiTime = toZonedTime(date, 'Africa/Nairobi');
  return format(nairobiTime, "d MMM yyyy, h:mm a");
}

/**
 * Converts bytes to human-readable format
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
