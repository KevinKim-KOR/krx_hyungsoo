import bucketThemeJson from "./bucket_theme.json";

type BucketThemeItem = {
  name: string;
  color: string;
};

type BucketTheme = {
  buckets: Record<string, BucketThemeItem>;
};

const bucketTheme = bucketThemeJson as BucketTheme;

export const BUCKET_THEME = bucketTheme.buckets;

export const BUCKET_OPTIONS = [1, 2, 3, 4].map((id) => ({
  id,
  name: BUCKET_THEME[String(id)].name,
}));

export const BUCKET_NAME_MAP: Record<number, string> = Object.fromEntries(
  Object.entries(BUCKET_THEME).map(([id, value]) => [Number(id), value.name]),
) as Record<number, string>;

export const BUCKET_COLORS = [1, 2, 3, 4, 5].map((id) => BUCKET_THEME[String(id)].color);

export function buildBucketCssVariables(): string {
  const lines = Object.entries(BUCKET_THEME).map(
    ([id, value]) => `--bucket-${id}: ${value.color};`,
  );
  return `:root { ${lines.join(" ")} }`;
}
