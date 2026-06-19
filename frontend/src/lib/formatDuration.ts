export function formatDuration(minutes: number): string {
  if (minutes % 1440 === 0) {
    const days = minutes / 1440;
    return `${days} Day${days !== 1 ? 's' : ''}`;
  } else if (minutes % 60 === 0) {
    const hours = minutes / 60;
    return `${hours} Hour${hours !== 1 ? 's' : ''}`;
  }
  return `${minutes} Minute${minutes !== 1 ? 's' : ''}`;
}
