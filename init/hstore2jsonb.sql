

ALTER TABLE ONLY node_node ALTER COLUMN date SET DEFAULT CURRENT_DATE ;

ALTER TABLE ONLY node_node ALTER COLUMN metadata DROP NOT NULL ;

ALTER TABLE ONLY node_node ALTER COLUMN metadata DROP DEFAULT ;

ALTER TABLE ONLY node_node ALTER COLUMN metadata TYPE JSONB USING hstore_to_json(metadata)::jsonb ;

ALTER TABLE ONLY node_node ALTER COLUMN metadata SET DEFAULT '{}'::jsonb ;

ALTER TABLE ONLY node_node ALTER COLUMN metadata SET NOT NULL ;

