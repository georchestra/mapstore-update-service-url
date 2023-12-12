# mapstore-update-service-url

python script to update service urls in a mapstore instance, when your service
is renamed or moved to a new server, or a layer is migrated to another service,
such as the french geoplateforme migration, cf
https://geoservices.ign.fr/bascule-vers-la-geoplateforme

it can also remove no longer available services from all maps.
## configuration

the script needs a list of service definitions mappings, from a previous url to
a new url, or to nothing if the service is removed.  currently it is hardcoded
in the script, and should look like this:
```
# for catalog entries
catalogs_to_process = {
    "ignrasterwms": { "action": "replace", "by": {"url": "https://data.geopf.fr/wms-r/wms", "title": "Géoplateforme RASTER"}},
    "igndecouvertewmts": { "action": "drop" }}
# for layers & sources
layers_to_process = {
    "https://wxs.ign.fr/essentiels/geoportail/wmts": {"action": "replace", "by": { "url": "https://data.geopf.fr/wmts" }},
    "https://wxs.ign.fr/decouverte/geoportail/wmts": {"action": "drop" }}
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

## usage

the script accepts the `-d` argument in which case it wont modify anything, but
will tell you what it has found needing modifications.

## example

in the below example, a previous run already cleaned up all the entries in the
database, but there are still entries to remove in `localConfig.json` - the
script won't change those but will warn as long as they're here !
```
landry@build.fluela:~/scratch/mapstore-update-service-url $python3 process.py
catalog ignvectorwms should be updated in localConfig.json:
replace url by 'https://data.geopf.fr/wms-v/wms' and title by 'Géoplateforme VECTOR' in {'url': 'https://wxs.ign.fr/essentiels/geoportail/v/wms', 'type': 'wms', 'title': 'IGN essentiels VECTOR', 'autoload': True}
catalog igncartovectowms should be removed in localConfig.json, drop the following section:
{'url': 'https://wxs.ign.fr/cartovecto/geoportail/v/wms', 'type': 'wms', 'title': 'IGN carto vectorielle', 'autoload': True}
catalog ignadministratifwms should be removed in localConfig.json, drop the following section:
{'url': 'https://wxs.ign.fr/administratif/geoportail/r/wms', 'type': 'wms', 'title': 'IGN administratif', 'autoload': True}
catalog ignadressewms should be removed in localConfig.json, drop the following section:
{'url': 'https://wxs.ign.fr/adresse/geoportail/v/wms', 'type': 'wms', 'title': 'IGN adresse', 'autoload': True}
catalog ignagriculturewms should be removed in localConfig.json, drop the following section:
{'url': 'https://wxs.ign.fr/agriculture/geoportail/r/wms', 'type': 'wms', 'title': 'IGN agriculture', 'autoload': True}
catalog ignaltimetriewmts should be removed in localConfig.json, drop the following section:
{'url': 'https://wxs.ign.fr/altimetrie/geoportail/wmts', 'type': 'wmts', 'title': 'IGN altimetrie WMTS', 'autoload': True}
catalog ifremer should be removed in localConfig.json, drop the following section:
{'NOTE': 'NOT WORKING, requires login. This is configured on the current viewer but do not provide any response', 'url': 'http://www.ifremer.fr/geonetwork/srv/fre/csw', 'type': 'csw', 'title': "le catalogue de l'Ifremer", 'autoload': True}
connected to user=georchestra password=xxx dbname=georchestra host=localhost port=5432
nothing to update in the database !
```
