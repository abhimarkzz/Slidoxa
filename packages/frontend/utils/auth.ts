export function isTruthyAuthValue(value?: string | null): boolean {
  const raw = value?.trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
}

export function getDisableAuthValue(): string | undefined {
  if (typeof window !== "undefined") {
    return window.env?.DISABLE_AUTH;
  }

  if (typeof process !== "undefined") {
    return process.env.DISABLE_AUTH;
  }

  return undefined;
}

export function isPresentonElectronDesktop(): boolean {
  if (typeof window !== "undefined") {
    return window.env?.PRESENTON_ELECTRON === "true";
  }

  return (
    typeof process !== "undefined" &&
    process.env.PRESENTON_ELECTRON === "true"
  );
}

export function isAuthDisabled(): boolean {
  return (
    isPresentonElectronDesktop() &&
    isTruthyAuthValue(getDisableAuthValue())
  );
}