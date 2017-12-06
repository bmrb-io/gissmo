-- Create terms table
DROP TABLE IF EXISTS chemical_shifts_tmp;
CREATE TABLE chemical_shifts_tmp (
    bmrb_id text,
    simulation_ID text,
    frequency integer,
    peak_type text,
    ppm float,
    amplitude float);

\COPY chemical_shifts_tmp FROM '/websites/gissmo/DB/peak_list_GSD.csv' WITH (FORMAT csv);
\COPY chemical_shifts_tmp FROM '/websites/gissmo/DB/peak_list_standard.csv' WITH (FORMAT csv);

-- create index: potentially combine these two based on usage
CREATE INDEX ON chemical_shifts_tmp (ppm);
CREATE INDEX ON chemical_shifts_tmp (frequence);

-- Move the new table into place
ALTER TABLE IF EXISTS chemical_shifts RENAME TO chemical_shifts_old;
ALTER TABLE chemical_shifts_tmp RENAME TO chemical_shifts;
DROP TABLE IF EXISTS chemical_shifts_old;
