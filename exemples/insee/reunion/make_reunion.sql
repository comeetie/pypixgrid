create table geom_bounds as select id, ST_XMAX(wkb_geometry) as x_max, ST_XMIN(wkb_geometry) as x_min, ST_YMAX(wkb_geometry) as y_max, ST_YMIN(wkb_geometry) as y_min from car_r04;
create table geom_clean as select id, x_min/200 as col, y_max/200 as row, ST_GeomFromText('Polygon(('||x_min||' '|| y_max||','||x_min||' '||y_min||','||x_max||' '||y_min||','||x_max||' '||y_max||','||x_min||' '||y_max||'))',32740) as wkb_geometry from geom_bounds;
create table carpop as select cg.id, row as i,col as j, wkb_geometry, ind_c,idk from geom_clean as cg, carreaux as c where c.id=cg.id;
create table car_data as select id, i, j, wkb_geometry, ind_c as pop,ind_srf/ind_r as mrev, (ind_r-ind_age6)*ind_c/ind_r as m25ans, ind_age7*ind_c/ind_r as p65ans, Men_basr*ind_c/ind_r as Men_basr, Men*ind_c/ind_r as Men , Men_coll*ind_c/ind_r as Men_coll, Men_prop*ind_c/ind_r as Men_prop from carpop as c, rect_r04 as r where c.idk=r.idk;


