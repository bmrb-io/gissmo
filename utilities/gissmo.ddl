--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET search_path = public, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: chemical_shifts; Type: TABLE; Schema: public; Owner: web; Tablespace: 
--

CREATE TABLE chemical_shifts (
    bmrb_id text,
    simulation_id text,
    frequency integer,
    peak_type text,
    ppm numeric,
    amplitude double precision
);


ALTER TABLE public.chemical_shifts OWNER TO web;

--
-- Name: chemical_shifts_tmp_frequency_peak_type_ppm_idx1; Type: INDEX; Schema: public; Owner: web; Tablespace: 
--

CREATE INDEX chemical_shifts_tmp_frequency_peak_type_ppm_idx1 ON chemical_shifts USING btree (frequency, peak_type, ppm);


--
-- Name: public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

