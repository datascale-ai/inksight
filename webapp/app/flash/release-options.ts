export type FirmwareBuild = {
  chipFamily: string;
  parts: Array<{
    path: string;
    offset: number;
  }>;
};

export type FirmwareReleaseOption = {
  version: string;
  asset_name?: string;
  manifest: {
    builds: FirmwareBuild[];
  };
};

export function buildReleaseKey(release: Pick<FirmwareReleaseOption, "version" | "asset_name">): string {
  return `${release.version}::${release.asset_name || ""}`;
}

export function buildReleaseLabel(release: Pick<FirmwareReleaseOption, "version" | "asset_name">): string {
  const assetStem = (release.asset_name || "").replace(/\.bin$/i, "");
  return assetStem ? `v${release.version}(${assetStem})` : `v${release.version}`;
}

export function getPreferredBuild(release: FirmwareReleaseOption): FirmwareBuild | null {
  return release.manifest.builds[0] || null;
}
