-- Run once in the Supabase SQL editor before connecting the backend.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS scan_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(160) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'created',
    started_at timestamptz,
    finished_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    error_message text
);

CREATE TABLE IF NOT EXISTS media_assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES scan_sessions(id) ON DELETE CASCADE,
    media_type varchar(16) NOT NULL,
    storage_path text NOT NULL,
    sha256 varchar(64) NOT NULL,
    size_bytes integer NOT NULL,
    duration_seconds double precision,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_media_assets_session_id ON media_assets(session_id);

CREATE TABLE IF NOT EXISTS route_points (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES scan_sessions(id) ON DELETE CASCADE,
    elapsed_seconds double precision NOT NULL,
    recorded_at timestamptz,
    location geometry(Point, 4326),
    altitude_m double precision,
    speed_mps double precision,
    heading_deg double precision
);
CREATE INDEX IF NOT EXISTS ix_route_points_session_id ON route_points(session_id);
CREATE INDEX IF NOT EXISTS ix_route_points_location_gist ON route_points USING gist(location);

CREATE TABLE IF NOT EXISTS frames (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    media_asset_id uuid NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
    elapsed_seconds double precision NOT NULL,
    storage_path text NOT NULL,
    location geometry(Point, 4326),
    route_point_id uuid REFERENCES route_points(id) ON DELETE SET NULL,
    georeference_status varchar(32) NOT NULL DEFAULT 'unreferenced',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_frames_media_asset_id ON frames(media_asset_id);
CREATE INDEX IF NOT EXISTS ix_frames_location_gist ON frames USING gist(location);

CREATE TABLE IF NOT EXISTS detections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    frame_id uuid NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
    defect_type varchar(48) NOT NULL,
    confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    description text NOT NULL,
    region_json jsonb,
    severity_estimated varchar(16) NOT NULL,
    severity_score double precision NOT NULL,
    severity_version varchar(32) NOT NULL,
    model_name varchar(120) NOT NULL,
    prompt_version varchar(32) NOT NULL,
    raw_output jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_detections_frame_id ON detections(frame_id);
CREATE INDEX IF NOT EXISTS ix_detections_type ON detections(defect_type);

CREATE TABLE IF NOT EXISTS road_defects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES scan_sessions(id) ON DELETE CASCADE,
    defect_type varchar(48) NOT NULL,
    location geometry(Point, 4326),
    severity_estimated varchar(16) NOT NULL,
    severity_score double precision NOT NULL,
    review_status varchar(24) NOT NULL DEFAULT 'pending',
    description text NOT NULL,
    first_observed_at double precision NOT NULL,
    last_observed_at double precision NOT NULL,
    confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence_frame_id uuid NOT NULL REFERENCES frames(id) ON DELETE RESTRICT,
    is_synthetic boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_road_defects_session_id ON road_defects(session_id);
CREATE INDEX IF NOT EXISTS ix_road_defects_type ON road_defects(defect_type);
CREATE INDEX IF NOT EXISTS ix_road_defects_severity ON road_defects(severity_estimated);
CREATE INDEX IF NOT EXISTS ix_road_defects_review_status ON road_defects(review_status);
CREATE INDEX IF NOT EXISTS ix_road_defects_location_gist ON road_defects USING gist(location);

CREATE TABLE IF NOT EXISTS defect_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    road_defect_id uuid NOT NULL REFERENCES road_defects(id) ON DELETE CASCADE,
    detection_id uuid NOT NULL REFERENCES detections(id) ON DELETE CASCADE,
    UNIQUE (road_defect_id, detection_id)
);
CREATE INDEX IF NOT EXISTS ix_defect_observations_road_defect_id ON defect_observations(road_defect_id);
CREATE INDEX IF NOT EXISTS ix_defect_observations_detection_id ON defect_observations(detection_id);
