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
# sql query for catalogs in a context:
#    select id, json_object_keys(stored_data::json->'mapConfig'->'catalogServices'->'services')
#    from mapstore.gs_stored_data where id in (select id from mapstore.gs_resource where category_id='8');
# sql query for catalogs in a map:
#    select id, json_object_keys(stored_data::json->'catalogServices'->'services')
#    from mapstore.gs_stored_data where id in (select id from mapstore.gs_resource where category_id='1');
# todo: dashoards -> iterate widgets, find map where widgetType == map

import argparse
import sys
import json
import psycopg2


def read_config(name):
    print(f"reading config from {name}")
    with open(name) as f:
        return json.load(f)


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
    # print(f"list of catalogs in {filename}: " + str(catalogs.keys()))
    for f in catalogs:
        if f in config["catalogs_to_process"].keys():
            cp = config["catalogs_to_process"][f]
            c = catalogs[f]
            if cp["action"] == "drop":
                if args.dryrun or not canupdate:
                    print(
                        f'catalog {f} should be removed in {filename}, drop the following section: "{c}"'
                    )
                to_drop.append(f)
                modified = True
            elif cp["action"] == "rename":
                if cp["with"] in catalogs.keys():
                    print(
                        f"can't rename catalog {f} to "
                        + cp["with"]
                        + " as a catalog already exists with this key"
                    )
                    continue
                if args.dryrun or not canupdate:
                    print(
                        f"catalog {f} should be renamed to "
                        + cp["with"]
                        + f" in {filename}:"
                    )
                to_rename[f] = cp["with"]
                modified = True
            elif cp["action"] == "replace":
                if c["url"] == cp["by"]["url"] and (
                    "title" not in cp["by"]
                    or ("title" in cp["by"] and c["title"] == cp["by"]["title"])
                ):
                    continue
                msg = f"catalog {f} should be updated in {filename}:"
                if "title" in cp["by"]:
                    msg += (
                        " replace url by '"
                        + cp["by"]["url"]
                        + "' and title by '"
                        + cp["by"]["title"]
                        + f"' in {c}"
                    )
                    c["title"] = cp["by"]["title"]
                else:
                    msg += " replace url by '" + cp["by"]["url"] + f"' in {c}"
                if args.dryrun or not canupdate:
                    print(msg)
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
        # print(lu, l["name"])
        if lu in config["layers_to_process"].keys():
            lp = config["layers_to_process"][lu]
            if lp["action"] == "drop":
                if "layername" in lp and lp["layername"] != l["name"]:
                    continue
                if args.dryrun or not canupdate:
                    print(
                        f"layer with url {lu} and name "
                        + l["name"]
                        + f" should be removed in {filename}, drop the following section:\n{l}"
                    )
                to_drop.append(l)
                modified = True
            elif lp["action"] == "replace":
                if "layername" in lp and lp["layername"] != l["name"]:
                    continue
                if args.dryrun or not canupdate:
                    print(
                        f"layer with url {lu} should be updated in {filename}: "
                        + "replace url by '"
                        + lp["by"]["url"]
                        + "' in the layer with title '"
                        + l["title"]
                        + "' and name '"
                        + l["name"]
                        + "'"
                    )
                l["url"] = lp["by"]["url"]
                if "capabilitiesURL" in l and l["capabilitiesURL"] != lp["by"]["url"]:
                    l["capabilitiesURL"] = lp["by"]["url"]
                modified = True
    for l in to_drop:
        layers.remove(l)
    return modified


def check_sources(sources, filename, canupdate):
    modified = False
    to_drop = list()
    to_replace = dict()
    for s in sources.keys():
        if s in config["layers_to_process"].keys():
            lp = config["layers_to_process"][s]
            if lp["action"] == "drop":
                if "layername" in lp:
                    # not dropping source, as we don't know if several layers might use it
                    continue
                if args.dryrun or not canupdate:
                    print(
                        f"source with url '{s}' should be removed in {filename}, drop corresponding section"
                    )
                to_drop.append(s)
                modified = True
            elif lp["action"] == "replace":
                if args.dryrun or not canupdate:
                    print(
                        f"source with url '{s}' should be updated in {filename}: replace '{s}' by '"
                        + lp["by"]["url"]
                        + "'"
                    )
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


def check_map(mapconfig, mapname, canupdate=False):
    layers = mapconfig["map"]["layers"]
    layers_modified = check_layers(layers, mapname, canupdate)
    if "sources" in mapconfig["map"]:
        sources = mapconfig["map"]["sources"]
        sources_modified = check_sources(sources, mapname, canupdate)
        return layers_modified or sources_modified
    else:
        return layers_modified


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
        "WHERE cat.name in ('MAP','TEMPLATE')"
    )
    records = curs.fetchall()
    for record in records:
        rid = record[0]
        name = record[1]
        try:
            mapconfig = json.loads(record[2])
        except TypeError:
            print(f"map {rid} ({name}) has no content ?")
            continue
        map_modified = check_map(
            mapconfig, f"db map with id {rid} and name {name}", True
        )
        catalogs = mapconfig["catalogServices"]["services"]
        catalogs_modified = check_catalogs(
            catalogs, f"db map with id {rid} and name {name}", True
        )
        if map_modified or catalogs_modified:
            if args.dryrun:
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
                    curs.execute(
                        "UPDATE mapstore.gs_resource SET lastupdate=now() AT TIME ZONE 'utc' WHERE id=%(rid)s",
                        {
                            "rid": rid,
                        },
                    )
                    db.commit()
                except psycopg2.Error as e:
                    print(f"failed updating map {rid} ! {e}")
                else:
                    print(f"updated map {rid} ({name})")
                    modified = True
        else:
            print(f"nothing to fix in map {rid} ({name})")

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
        try:
            mapconfig = json.loads(record[2])
        except TypeError:
            print(f"context {rid} ({name}) has no content ?")
            continue
        if 'map' not in mapconfig["mapConfig"]:
            print(f"context {rid} ({name}) has no map ? skipping")
            continue
        map_modified = check_map(
            mapconfig["mapConfig"], f"db context with id {rid} and name {name}", True
        )
        catalogs = mapconfig["mapConfig"]["catalogServices"]["services"]
        catalogs_modified = check_catalogs(
            catalogs, f"db context with id {rid} and name {name}", True
        )
        if map_modified or catalogs_modified:
            if args.dryrun:
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
                    curs.execute(
                        "UPDATE mapstore.gs_resource SET lastupdate=now() AT TIME ZONE 'utc' WHERE id=%(rid)s",
                        {
                            "rid": rid,
                        },
                    )
                    db.commit()
                except psycopg2.Error as e:
                    print(f"failed updating context {rid} ! {e}")
                else:
                    print(f"updated context {rid} ({name})")
                    modified = True
        else:
            print(f"nothing to fix in context {rid} ({name})")

    db.close()
    if not modified:
        print(f"nothing to update in the database !")


# main

parser = argparse.ArgumentParser(
    description="Process mapstore configs, maps & contexts."
)
parser.add_argument("-d", "--dryrun", action="store_true", help="dry-run mode")
parser.add_argument(
    "-c",
    "--config",
    default="config.json",
    help="json configuration file (defaults to config.json)",
)
args = parser.parse_args()
config = read_config(args.config)
check_localConfig()
for filetype in ["new", "config"]:
    with open(f"/etc/georchestra/mapstore/configs/{filetype}.json") as file:
        s = file.read()
        mapconfig = json.loads(s)
        check_map(mapconfig, filetype + ".json")
check_db_storeddata()
