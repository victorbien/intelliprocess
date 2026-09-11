/**
 * Lightweight structured logger for the frontend.
 *
 * Wraps the console so log calls carry a consistent prefix and can be
 * silenced in production builds. Errors are always emitted.
 */

const isDev = import.meta.env.DEV;

function fmt(scope: string, msg: string): string {
  return `[IntelliProcess:${scope}] ${msg}`;
}

export const logger = {
  debug(scope: string, msg: string, ...args: unknown[]): void {
    if (isDev) console.debug(fmt(scope, msg), ...args);
  },
  info(scope: string, msg: string, ...args: unknown[]): void {
    if (isDev) console.info(fmt(scope, msg), ...args);
  },
  warn(scope: string, msg: string, ...args: unknown[]): void {
    console.warn(fmt(scope, msg), ...args);
  },
  error(scope: string, msg: string, ...args: unknown[]): void {
    console.error(fmt(scope, msg), ...args);
  },
};
