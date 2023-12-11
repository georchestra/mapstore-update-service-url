## mapstore-update-service-url

python script to update service urls in a mapstore instance, when your service
is renamed or moved to a new server, or a layer is migrated to another service,
such as the french geoplateforme migration, cf
https://geoservices.ign.fr/bascule-vers-la-geoplateforme

it can also remove no longer available services from all maps.
# configuration

the script needs a list of service definitions mappings, from a previous url to
a new url, or to nothing if the service is removed.  currently it is hardcoded
in the script, and should look like this:
```
# for catalog entries
servicename: ignrasterwms, action: replace, by: {url: https://data.geopf.fr/wms-r/wms, title: "Géoplateforme RASTER"}
servicename: igndecouvertewmts, action: drop
# for layers
serviceurl: https://wxs.ign.fr/essentiels/geoportail/wmts, action: replace, by: { url: https://data.geopf.fr/wmts }
serviceurl: https://wxs.ign.fr/decouverte/geoportail/wmts, action: drop
```

it will process (but only warn !) the following files:
- `/etc/georchestra/mapstore/configs/localConfig.json`
- `/etc/georchestra/mapstore/configs/new.json`
- `/etc/georchestra/mapstore/configs/config.json`

and it will process (and update !) all entries in the mapstore schema found in
the database pointed at by `/etc/georchestra/default.properties`

it will replace usage of layers pointing at the old url to the new
url/servicename, and it will also update the list of catalogs available in the
map.

# usage

the script accepts the `-d` argument in which case it wont modify anything, but
will tell you what it has found needing modifications.
