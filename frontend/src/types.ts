export interface Polygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface Scene {
  id: string;
  stac_id: string;
  satellite: string;
  sensing_time: string;
  cloud_cover: number;
  bbox: Polygon;
  bands: Record<string, string>;
  processing_status: string;
}

export interface DetectionProperties {
  id: string;
  scene_id: string;
  severity: "low" | "moderate" | "high";
  dnbr_mean: number;
  area_ha: number;
  confidence: number;
  detected_at: string;
}

export interface DetectionFeature {
  type: "Feature";
  geometry: Polygon;
  properties: DetectionProperties;
}

export interface DetectionFeatureCollection {
  type: "FeatureCollection";
  features: DetectionFeature[];
}
