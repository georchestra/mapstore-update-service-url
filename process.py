#!/bin/env python3
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et

# jq paths for the list of catalogs in localConfig.json : cat /etc/georchestra/mapstore/configs/localConfig.json | jq .initialState.defaultState.catalog.default.services
# other jq paths:
# - in a context:
#   - for catalogs: .mapConfig.catalogServices.services
#   - for layers: .mapConfig.map.layers
#   - for sources: .mapConfig.map.sources
# - in a map:
#   - for catalogs: .catalogServices.services
#   - for layers: .map.layers
#   - for sources: .map.sources
# technically, in a a context, .mapConfig is a map.
# todo: dashoards -> iterate widgets, find map where widgetType == map

import sys
import json
import psycopg2

# for catalog entries
catalogs_to_process = {
    "sadre": { "action": "rename", "with": "sandre" },
    "ignrasterwms": {
        "action": "replace",
        "by": {
            "url": "https://data.geopf.fr/wms-r/wms",
            "title": "Géoplateforme RASTER",
        },
    },
    "igndecouvertewmts": {"action": "drop"},
}
# for layers
layers_to_process = {
    "https://wxs.ign.fr/essentiels/geoportail/wmts": {
        "action": "replace",
        "by": {"url": "https://data.geopf.fr/wmts"},
    },
    "https://wxs.ign.fr/decouverte/geoportail/wmts": {"action": "drop"},
}


def get_db_url():
    with open("/etc/georchestra/default.properties") as myfile:
        psqlconf = dict()
        for line in myfile:
            if line[:5] == "pgsql":
                name, var = line.partition("=")[::2]
                psqlconf[name.strip()] = var
    return f"dbname={psqlconf['pgsqlDatabase']} user={psqlconf['pgsqlUser']} port={psqlconf['pgsqlPort']} host={psqlconf['pgsqlHost']} password={psqlconf['pgsqlPassword']}"


def check_catalogs(catalogs, filename, canupdate=False):
    modified = False
    to_drop = list()
    to_rename = dict()
    for f in catalogs:
        if f in catalogs_to_process.keys():
            cp = catalogs_to_process[f]
            c = catalogs[f]
            if cp["action"] == "drop":
                print(
                    f"catalog {f} should be removed in {filename}, drop the following section:\n{c}"
                )
                to_drop.append(f)
                modified = True
            elif cp["action"] == "rename":
                if cp["with"] in catalogs.keys():
                    print(f"can't rename catalog {f} to " + cp["with"] + " as a catalog already exists with this key")
                    continue
                print(f"catalog {f} should be renamed to " + cp["with"] + f" in {filename}:")
                to_rename[f] = cp["with"]
                modified = True
            elif cp["action"] == "replace":
                if c["url"] == cp["by"]["url"] and ("title" not in cp["by"] or ("title" in cp["by"] and c["title"] == cp["by"]["title"])):
                    continue
                print(f"catalog {f} should be updated in {filename}:")
                if "title" in cp["by"]:
                    print(
                        "replace url by '"
                        + cp["by"]["url"]
                        + "' and title by '"
                        + cp["by"]["title"]
                        + f"' in {c}"
                    )
                    c["title"] = cp["by"]["title"]
                else:
                    print("replace url by '" + cp["by"]["url"] + f"' in {c}")
                c["url"] = cp["by"]["url"]
                modified = True
    for c in to_drop:
        del catalogs[c]
    for c in to_rename:
        catalogs[to_rename[c]] = catalogs.pop(c)
    return modified


def check_layers(layers, filename, canupdate):
    modified = False
    to_drop = list()
    for l in layers:
        if "url" not in l:
            continue
        lu = l["url"]
        if lu in layers_to_process.keys():
            lp = layers_to_process[lu]
            if lp["action"] == "drop":
                print(
                    f"layer with url {lu} should be removed in {filename}, drop the following section:\n{l}"
                )
                to_drop.append(l)
                modified = True
            elif lp["action"] == "replace":
                print(f"layer with url {lu} should be updated in {filename}:")
                print(
                    "replace url by '"
                    + lp["by"]["url"]
                    + "' in the layer with title '"
                    + l["title"]
                    + "' and name '"
                    + l["name"]
                    + "'"
                )
                l["url"] = lp["by"]["url"]
                modified = True
    for l in to_drop:
        layers.remove(l)
    return modified


def check_sources(sources, filename, canupdate):
    modified = False
    to_drop = list()
    to_replace = dict()
    for s in sources.keys():
        if s in layers_to_process.keys():
            lp = layers_to_process[s]
            if lp["action"] == "drop":
                print(
                    f"source with url '{s}' should be removed in {filename}, drop corresponding section"
                )
                to_drop.append(s)
                modified = True
            elif lp["action"] == "replace":
                print(f"source with url '{s}' should be updated in {filename}:")
                print(f"replace '{s}' by '" + lp["by"]["url"] + "'")
                to_replace[s] = lp["by"]["url"]
                modified = True
    for s in to_drop:
        del sources[s]
    for s in to_replace:
        sources[to_replace[s]] = sources.pop(s)
    return modified


def check_localConfig():
    with open("/etc/georchestra/mapstore/configs/localConfig.json") as file:
        localconfig = json.load(file)
        catalogs = localconfig["initialState"]["defaultState"]["catalog"]["default"][
            "services"
        ]
        check_catalogs(catalogs, "localConfig.json")


def check_map(string, mapname, canupdate=False):
    layers = mapconfig["map"]["layers"]
    layers_modified = check_layers(layers, mapname, canupdate)
    sources = mapconfig["map"]["sources"]
    sources_modified = check_sources(sources, mapname, canupdate)
    return layers_modified or sources_modified


def check_db_storeddata():
    db = psycopg2.connect(get_db_url())
    print(f"connected to {db.dsn}")
    modified = False
    curs = db.cursor()
    # list maps
    curs.execute(
        "SELECT res.id,res.name,sd.stored_data FROM mapstore.gs_resource AS res "
        "LEFT JOIN mapstore.gs_stored_data AS sd ON sd.id=res.id "
        "LEFT JOIN mapstore.gs_category AS cat ON cat.id=res.category_id "
        "WHERE cat.name='MAP'"
    )
    records = curs.fetchall()
    for record in records:
        rid = record[0]
        name = record[1]
        mapconfig = json.loads(record[2])
        map_modified = check_map(
            mapconfig, f"db map with id {rid} and name {name}", True
        )
        catalogs = mapconfig["catalogServices"]["services"]
        catalogs_modified = check_catalogs(
            catalogs, f"db map with id {rid} and name {name}", True
        )
        if map_modified or catalogs_modified:
            if dryrun:
                print(f"map {rid} needs update but not changing anything, dry-run mode")
            else:
                try:
                    curs.execute(
                        "UPDATE mapstore.gs_stored_data SET stored_data=%(jsonstr)s WHERE id=%(rid)s",
                        {
                            "jsonstr": json.dumps(mapconfig, separators=(",", ":")),
                            "rid": rid,
                        },
                    )
                    db.commit()
                except psycopg2.Error as e:
                    print(f"failed updating map {rid} ! {e}")
                else:
                    print(f"updated map {rid} ({name})")
                    modified = True

    # list contexts
    curs.execute(
        "SELECT res.id, res.name, sd.stored_data FROM mapstore.gs_resource AS res "
        "LEFT JOIN mapstore.gs_stored_data AS sd ON sd.id=res.id "
        "LEFT JOIN mapstore.gs_category AS cat ON cat.id=res.category_id "
        "WHERE cat.name='CONTEXT'"
    )
    records = curs.fetchall()
    for record in records:
        rid = record[0]
        name = record[1]
        mapconfig = json.loads(record[2])
        map_modified = check_map(
            mapconfig["mapConfig"], f"db context with id {rid} and name {name}", True
        )
        catalogs = mapconfig["mapConfig"]["catalogServices"]["services"]
        catalogs_modified = check_catalogs(
            catalogs, f"db context with id {rid} and name {name}", True
        )
        if map_modified or catalogs_modified:
            if dryrun:
                print(
                    f"context {rid} needs update but not changing anything, dry-run mode"
                )
            else:
                try:
                    curs.execute(
                        "UPDATE mapstore.gs_stored_data SET stored_data=%(jsonstr)s WHERE id=%(rid)s",
                        {
                            "jsonstr": json.dumps(mapconfig, separators=(",", ":")),
                            "rid": rid,
                        },
                    )
                    db.commit()
                except psycopg2.Error as e:
                    print(f"failed updating context {rid} ! {e}")
                else:
                    print(f"updated context {rid} ({name})")
                    modified = True

    db.close()
    if not modified:
        print(f"nothing to update in the database !")

# main
dryrun = False
if len(sys.argv) > 1 and sys.argv[1] == "-d":
    dryrun = True

check_localConfig()
for filetype in ["new", "config"]:
    with open(f"/etc/georchestra/mapstore/configs/{filetype}.json") as file:
        s = file.read()
        mapconfig = json.loads(s)
        check_map(mapconfig, filetype + ".json")
check_db_storeddata()
