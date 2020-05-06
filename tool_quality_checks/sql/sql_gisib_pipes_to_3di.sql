-------------------------------------------------------------------------------------------
--- GBI TO 3Di (currently manholes and pipes only)
--- Input: Export of GBI (vrijv_leiding.shp and rioolput.shp)
--- Output: 3Di model in work_db
-------------------------------------------------------------------------------------------

-------------------------------------------------
------ Stap 0: Data inladen ---------------------
-------------------------------------------------
/* Used in other scripts
-- import GBI files with ogr2ogr
CREATE SCHEMA gbi;
-- Open OSGEO4W shell and navigate to your folder (cd)
for %f in (*.shp) do (ogr2ogr -overwrite -skipfailures -f "PostgreSQL" PG:"host=<hostname> user=<username> dbname=<databasename> password=<password> port=5432" -lco GEOMETRY_NAME=geom -lco FID="id" -nln gbi.%~nf %f -a_srs EPSG:28992)

-- Error and Answer:
-- UTF8 issues -> resave shapefile with UTF8 encoding on in QGIS

-- CHECK EXPECTED FILES ON CORRECT NUMBER OF PUTTEN EN LEIDINGEN
SELECT * FROM src.putten_gisib LIMIT 10;
SELECT * FROM src.leidingen_gisib LIMIT 10;
SELECT count(*) FROM src.putten_gisib;
SELECT count(*) FROM src.leidingen_gisib;
*/

-------------------------------------------------
-------- Stap 3: Leidingen invoeren -------
-------------------------------------------------

-- CHECK OF AL JOUW materialen, strengtype etc voorkomen!!
DELETE FROM v2_pipe;
INSERT INTO v2_pipe(
            id, display_name, code, sewerage_type,
            invert_level_start_point, invert_level_end_point, cross_section_definition_id,
            material, zoom_category, connection_node_start_id, connection_node_end_id)
SELECT
	a.id 		AS id,
    COALESCE(naam_of_nu,'leeg') as display_name,
	COALESCE(s.naam_of_nu,'0') || '_' || COALESCE(e.naam_of_nu,'0')	AS code,
	CASE
		--We halen strengtype uit std_streng en type water uit std_stelse 
		--strengtype kunstwerken--
        WHEN lower(soort_leid) LIKE '%bergbezink%'		                                     THEN 7 -- BERGBEZINKVOORZIENING
		WHEN lower(soort_leid) LIKE '%zinker%' OR lower(soort_leid) LIKE '%duiker%'     	 THEN 3 -- TRANSPORT

        --std_stelse--
		WHEN lower(soort_afva) LIKE '%gemengd%'	                                             THEN 0	-- GEMENGD
		WHEN lower(soort_afva) LIKE '%hemel%'	                                             THEN 1	-- RWA
		WHEN lower(soort_afva) LIKE '%vuil%'	                                             THEN 2	-- DWA

		WHEN lower(soort_afva) LIKE '%overig%'                                               THEN 10	-- OVERIG
		WHEN lower(soort_afva) IS NOT NULL                                                   THEN 11	-- OVERIG

        ELSE NULL 																						-- onbekend
   
	END AS sewerage_type,
    
	begin_bob AS invert_level_start_point,
	eind_bob AS invert_level_end_point,
	NULL as cross_section_definition_id,
	CASE
		WHEN lower(a.materiaal) LIKE '%beton%' THEN 0
		WHEN lower(a.materiaal) LIKE '%pvc%' THEN 1
		WHEN lower(a.materiaal) LIKE '%gres%' THEN 2
		WHEN lower(a.materiaal) LIKE '%gietijzer%' THEN 3
		WHEN lower(a.materiaal) LIKE '%metselwerk%' THEN 4
		WHEN lower(a.materiaal) LIKE '%PE%' OR lower(a.std_materi) LIKE '%poly%' THEN 5
		WHEN lower(a.materiaal) LIKE '%plaatijzer%' THEN 7
		WHEN lower(a.materiaal) LIKE '%staal%' THEN 8        	    
		WHEN lower(a.materiaal) LIKE '%overig%' THEN 99 --overig
		ELSE NULL
	END AS material,
	2 AS zoom_category,
	s.id AS connection_node_start_id,
	e.id AS connection_node_end_id
	FROM src.leidingen_gisib a
	LEFT JOIN src.putten_gisib s ON begin_knoo = s.id
	LEFT JOIN src.putten_gisib e ON eind_knoop = e.id;
    --where a.aanlegjaar != 9999 or lower(strengtype) NOT LIKE 'volgeschuimd' or lower(strengtype) NOT LIKE 'buiten gebruik';


-----------------------------------------------------------
-------- Stap 4: cross-sections voor pipe toevoegen -------
-----------------------------------------------------------
SELECT afmeting_l, vorm, breedte_le, hoogte_lei, diameter, count(*)
FROM src.leidingen_gisib
GROUP BY afmeting_l, vorm, breedte_le, hoogte_lei, diameter
ORDER BY afmeting_l, vorm, breedte_le, hoogte_lei, diameter
LIMIT 20;

SELECT CASE diameter WHEN 0 then NULL::numeric END as diamter, * FROM src.leidingen_gisib LIMIT 20;
---- ZET IN 1 KEER ALLES OM NAAR LOCATION EN DEFINITION
-- set sequence maximum id
delete from v2_cross_section_definition;
select setval('v2_cross_section_definition_id_seq',1);
--insert cross_section_definition and add definition_id in v2_cross_section_location
with gather_data as (
	SELECT DISTINCT afmeting_l, 
		vorm,
	CASE WHEN vorm ilike '%cirkel%' THEN 2
		WHEN vorm ilike '%ei%' then 3
		when vorm ilike '%vierkant%' THEN 5
		when vorm ilike '%rh%' THEN 5
		ELSE NULL
	END as shape,
	(CASE
		WHEN (string_to_array(vorm,' '))[1] LIKE '%cirkel%' 
			THEN COALESCE(
				CASE diameter WHEN 0 then NULL::numeric ELSE diameter/1000.0 END,
				CASE breedte_le WHEN 0 then NULL::numeric ELSE breedte_le/1000.0 END
			)
		ELSE COALESCE(
				CASE breedte_le WHEN 0 then NULL::numeric ELSE breedte_le/1000.0 END,
				CASE diameter WHEN 0 then NULL::numeric ELSE diameter/1000.0 END
			)
	END) AS width,
	COALESCE(
		CASE hoogte_lei WHEN 0 then NULL::numeric ELSE hoogte_lei/1000.0 END, 
		CASE diameter WHEN 0 then NULL::numeric ELSE diameter/1000.0 END

	) as height
	FROM src.leidingen_gisib
	ORDER BY afmeting_l
),
create_definitions as (
	INSERT INTO v2_cross_section_definition
	SELECT nextval('v2_cross_section_definition_id_seq') as id,
	shape,
	CASE WHEN shape = 5 OR shape = 6 
	THEN width || ' ' || width || ' 0'
	ELSE width::text
	END as width,
	CASE WHEN shape = 5 OR shape = 6 
	THEN  '0 ' || height || ' ' || height
	ELSE height::text
	END as height,
	COALESCE(afmeting_l,'leeg') as code
	FROM gather_data
	ORDER BY id
	RETURNING *
)
UPDATE v2_pipe
SET cross_section_definition_id = b.id
FROM create_definitions b, src.leidingen_gisib c
WHERE v2_pipe.id = c.id AND b.code = c.afmeting_l
